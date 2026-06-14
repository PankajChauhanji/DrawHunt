"""
Turn scoring (Phase 5: time-based).

Guessers earn more for guessing sooner: a guess with the full clock remaining
is worth GUESS_CEIL; one at the buzzer is worth GUESS_FLOOR, scaling linearly
with the fraction of time left when they guessed.

The drawer earns a bonus scaled by how many players guessed — and nothing if
nobody did, matching the original spec ("if no one guesses, the drawer gets 0").

Everything tunable lives in config.py.
"""
from config import Config


def _guess_points(elapsed: float, duration: float) -> int:
    if duration <= 0:
        return Config.GUESS_FLOOR
    fraction_left = max(0.0, min(1.0, (duration - elapsed) / duration))
    spread = Config.GUESS_CEIL - Config.GUESS_FLOOR
    return Config.GUESS_FLOOR + round(spread * fraction_left)


def score_turn(room) -> dict:
    """Apply this turn's points to player scores. Returns {user_id: awarded}."""
    awards: dict[str, int] = {}
    duration = float(room.settings.get("duration", Config.ROUND_DURATION))

    for uid in room.guessed_order:
        player = room.players.get(uid)
        if player is None:
            continue
        pts = _guess_points(room.guess_times.get(uid, duration), duration)
        player.score += pts
        awards[uid] = pts

    if room.drawer_id and room.guessed_order:
        total_guessers = max(1, len(room.active_guessers()))
        fraction = len(room.guessed_order) / total_guessers
        bonus = round(Config.DRAWER_MAX * fraction)
        drawer = room.players.get(room.drawer_id)
        if drawer is not None:
            drawer.score += bonus
            awards[room.drawer_id] = bonus

    return awards