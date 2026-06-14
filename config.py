"""
Central configuration.

Every tunable constant lives here so game rules are defined in exactly one
place. Read by the Flask app, the room/game models, and the socket handlers.
"""
import os


class Config:
    # ---- Flask ----
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-prod")

    # ---- Socket.IO ----
    # "*" is fine for local dev. In production set CORS_ORIGINS to your real
    # origin, e.g. "https://yourgame.onrender.com".
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

    # ---- Rooms ----
    MAX_PLAYERS = 10
    MIN_PLAYERS = 2                       # a drawer + at least one guesser
    CODE_LENGTH = 4
    # Letters only, dropping I and O so codes are unambiguous when spoken/typed.
    CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    NAME_MAX_LEN = 20

    # ---- Lifecycle / cleanup (sweeper) ----
    DISCONNECT_GRACE = 15                 # s a disconnected player is kept (survives refresh)
    ROOM_EMPTY_GRACE = 60                 # s an empty room is kept before deletion
    SWEEP_INTERVAL = 10                   # s between background cleanup passes

    # ---- Drawing relay (Phase 2) ----
    MAX_POINTS_PER_SEGMENT = 256        # reject oversized segments (abuse guard)
    MAX_HISTORY_POINTS = 300_000        # cap recorded points per room (memory guard)

    # ---- Game rules (used from Phase 4 onward) ----
    # NOTE: "a round" here means one full cycle in which every player draws once.
    DEFAULT_ROUNDS = 3
    ROUND_DURATION = 80                   # seconds a drawer gets per turn
    WORD_CHOICES = 3                      # options offered to the drawer

    # Settings the host may change, with the allowed values (server-enforced).
    ALLOWED_ROUNDS = [1, 2, 3, 4, 5, 6, 7, 8]
    ALLOWED_DURATIONS = [40, 60, 80, 120]