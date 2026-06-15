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

    CHOOSE_DURATION = 10                  # seconds the drawer has to pick a word (auto-picks after)
    ROUND_END_PAUSE = 6                   # seconds the word-reveal screen shows
    DRAWER_DISCONNECT_GRACE = 4           # seconds a drawer can drop before the turn ends

    # ---- Hints: progressively reveal letters to guessers as time passes ----
    HINT_FRACTION = 0.3                   # max letters revealed ~= 30% of the word
    HINT_MAX = 5                          # absolute cap on hints per turn

    # ---- Scoring ----
    # Guessers: rank bonus + time bonus + difficulty bonus, floor 10.
    RANK_BONUS_MAX = 100          # divided by player count, scaled by remaining rank
    TIME_BONUS_MAX = 100          # 100 * (time_remaining / duration)
    SCORE_FLOOR = 10              # minimum any player gets per turn (even non-guessers)

    # Difficulty bonus by letter count (spaces excluded): ceil(letters/3) * 15
    DIFFICULTY_STEP = 15          # points per difficulty tier
    DIFFICULTY_TIER_SIZE = 3      # letters per tier

    # Drawer: flat reward, capped, floor.
    DRAWER_GUESSED = 50           # flat score if at least one person guessed
    DRAWER_FLOOR = 10             # score if nobody guessed

    # Settings the host may change, with the allowed values (server-enforced).
    ALLOWED_ROUNDS = [1, 2, 3, 4, 5, 6, 7, 8]
    ALLOWED_DURATIONS = [40, 60, 80, 120]
    # Word source: "auto" = offer 3 random words; "own" = drawer types their own.
    ALLOWED_WORD_MODES = ["auto", "own"]
    DEFAULT_WORD_MODE = "auto"

    # "You're close!" nudge: max edit distance that still counts as close.
    CLOSE_DISTANCE_SHORT = 1   # for words up to 4 letters
    CLOSE_DISTANCE_LONG = 2    # for longer words