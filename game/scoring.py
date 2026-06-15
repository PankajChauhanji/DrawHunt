"""
Turn scoring.

Guesser score  = rank_bonus + time_bonus + difficulty_bonus  (floor: SCORE_FLOOR)
Non-guesser    = SCORE_FLOOR
Drawer score   = DRAWER_GUESSED if anyone guessed, else DRAWER_FLOOR

Rank bonus
----------
Rewards guessing before others. Formula per guesser:
    raw  = (RANK_BONUS_MAX / total_players) * (players_not_yet_guessed + 1)
    rounded up to the nearest 10.
First guesser always gets RANK_BONUS_MAX (100). Each later guesser gets less.
Scales naturally with room size.

Time bonus
----------
Rewards guessing quickly:
    raw  = TIME_BONUS_MAX * (time_remaining / duration)
    rounded up to nearest 10.
No explicit floor — the overall SCORE_FLOOR covers it.

Difficulty bonus
----------------
Longer words score more. Based on letter count (spaces excluded):
    tier  = ceil(letters / DIFFICULTY_TIER_SIZE)          # 1-3 → 1, 4-6 → 2 …
    bonus = tier * DIFFICULTY_STEP                         # tier 1=15, 2=30, 3=45 …
Same bonus for every guesser who guessed correctly on this turn.

Drawer score
------------
Flat DRAWER_GUESSED (50) if at least one player guessed, else DRAWER_FLOOR (10).
Simple and fair: rewards making anyone guess, avoids unfair speed/difficulty bias.
"""
import math
from config import Config


# ---- helpers ----

def _ceil10(value: float) -> int:
    """Round up to the nearest 10."""
    return math.ceil(value / 10) * 10


def _difficulty_bonus(word: str) -> int:
    letters = sum(1 for ch in word if ch != " ")
    if letters == 0:
        return 0
    tier = math.ceil(letters / Config.DIFFICULTY_TIER_SIZE)
    return tier * Config.DIFFICULTY_STEP


def _rank_bonus(rank: int, total_players: int, total_guessers: int) -> int:
    """rank is 0-based (0 = first to guess).
    players_not_yet_guessed at the moment of this guess = total_guessers - rank.
    raw = (RANK_BONUS_MAX / total_players) * (not_yet_guessed + 1)
    """
    not_yet = total_guessers - rank          # still includes this guesser's slot
    raw = (Config.RANK_BONUS_MAX / total_players) * (not_yet + 1)
    return _ceil10(raw)


def _time_bonus(elapsed: float, duration: float) -> int:
    if duration <= 0:
        return 0
    remaining = max(0.0, duration - elapsed)
    raw = Config.TIME_BONUS_MAX * (remaining / duration)
    return _ceil10(raw)


# ---- public API ----

def score_turn(room) -> dict:
    """Apply this turn's points to every player's score.
    Returns {user_id: points_awarded_this_turn}.
    """
    awards: dict[str, int] = {}
    duration = float(room.settings.get("duration", Config.ROUND_DURATION))
    word = room.current_word or ""
    diff_bonus = _difficulty_bonus(word)

    total_players = max(1, room.player_count())
    total_guessers = len(room.guessed_order)

    # ---- guessers (in the order they guessed) ----
    for rank, uid in enumerate(room.guessed_order):
        player = room.players.get(uid)
        if player is None:
            continue
        rb = _rank_bonus(rank, total_players, total_guessers)
        tb = _time_bonus(room.guess_times.get(uid, duration), duration)
        pts = max(Config.SCORE_FLOOR, rb + tb + diff_bonus)
        player.score += pts
        awards[uid] = pts

    # ---- non-guessers (connected, not the drawer) ----
    for uid, player in room.players.items():
        if uid in room.guessed_order:
            continue
        if uid == room.drawer_id:
            continue
        if not player.connected:
            continue
        player.score += Config.SCORE_FLOOR
        awards[uid] = Config.SCORE_FLOOR

    # ---- drawer ----
    if room.drawer_id:
        drawer = room.players.get(room.drawer_id)
        if drawer is not None:
            pts = Config.DRAWER_GUESSED if room.guessed_order else Config.DRAWER_FLOOR
            drawer.score += pts
            awards[room.drawer_id] = pts

    return awards