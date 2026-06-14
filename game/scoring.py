"""
Turn scoring (Phase 4 baseline).

Guessers earn points by how early they guessed (rank-based, with a floor).
The drawer earns a bonus scaled by how many players guessed — and nothing if
nobody did, matching the original spec ("if no one guesses, the drawer gets 0").

Phase 5 will refine this (e.g. time-based components) and add the end screen;
the formula lives here and in config so it's easy to tune in one place.
"""
from config import Config


def score_turn(room) -> dict:
    """Apply this turn's points to player scores. Returns {user_id: awarded}."""
    awards: dict[str, int] = {}

    # Guessers, in the order they got it.
    for rank, uid in enumerate(room.guessed_order):
        player = room.players.get(uid)
        if player is None:
            continue
        pts = max(Config.GUESS_MIN, Config.GUESS_BASE - rank * Config.GUESS_DECREMENT)
        player.score += pts
        awards[uid] = pts

    # Drawer bonus, only if at least one person guessed.
    if room.drawer_id and room.guessed_order:
        total_guessers = max(1, len(room.active_guessers()))
        fraction = len(room.guessed_order) / total_guessers
        bonus = round(Config.DRAWER_MAX * fraction)
        drawer = room.players.get(room.drawer_id)
        if drawer is not None:
            drawer.score += bonus
            awards[room.drawer_id] = bonus

    return awards