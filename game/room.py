"""
Room model.

Holds the roster (keyed by user_id), the host, the editable settings, and the
lobby/game state. Pure data + logic; no Socket.IO here. The socket layer reads
`public_state()` and broadcasts it whenever anything changes.
"""
import time

from config import Config
from .player import Player


class Room:
    def __init__(self, code: str, host_id: str, settings: dict | None = None):
        self.code = code
        self.host_id = host_id
        self.players: dict[str, Player] = {}        # user_id -> Player
        self.state = "LOBBY"                          # LOBBY | STARTING | (game states later)
        self.settings = settings or {
            "rounds": Config.DEFAULT_ROUNDS,
            "duration": Config.ROUND_DURATION,
        }
        self.created_at = time.time()
        # A freshly created room with nobody in it yet is "empty" from birth,
        # so an abandoned room (created but never joined) still gets swept.
        self.empty_since: float | None = self.created_at

        # ---- drawing (Phase 2) ----
        # Ordered list of stroke *segments* (the wire format the client sends).
        # This is the authoritative canvas, replayed to anyone who joins or
        # reconnects mid-draw. Kept here, not on the client, so all canvases agree.
        self.stroke_ops: list[dict] = []
        self._history_points = 0

        # ---- word / guessing (Phase 3) ----
        # The secret word lives ONLY on the server and is never put in any
        # broadcast. Guessers receive a masked pattern; the drawer is told the
        # real word privately.
        self.current_word: str | None = None
        self.drawer_id: str | None = None
        self.guessed_order: list[str] = []   # user_ids in the order they guessed (for Phase 5 scoring)

    # ---------- roster ----------
    def add_player(self, user_id: str, name: str, sid: str) -> Player:
        """Add a new player or re-attach an existing one (reconnect)."""
        player = self.players.get(user_id)
        if player is None:
            player = Player(user_id=user_id, name=name, sid=sid)
            self.players[user_id] = player
        else:
            player.sid = sid
            if name:
                player.name = name
            player.connected = True
            player.disconnected_at = None
        self.empty_since = None
        return player

    def remove_player(self, user_id: str) -> None:
        self.players.pop(user_id, None)
        self._refresh_empty()

    def get_player(self, user_id: str) -> Player | None:
        return self.players.get(user_id)

    def mark_disconnected(self, user_id: str, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        player = self.players.get(user_id)
        if player is None:
            return
        player.connected = False
        player.disconnected_at = now
        self._refresh_empty(now)

    def _refresh_empty(self, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        if self.has_connected():
            self.empty_since = None
        elif self.empty_since is None:
            self.empty_since = now

    # ---------- queries ----------
    def player_count(self) -> int:
        return len(self.players)

    def connected_count(self) -> int:
        return sum(1 for p in self.players.values() if p.connected)

    def has_connected(self) -> bool:
        return any(p.connected for p in self.players.values())

    def is_full(self) -> bool:
        return len(self.players) >= Config.MAX_PLAYERS

    def is_host(self, user_id: str) -> bool:
        return user_id == self.host_id

    def reassign_host(self) -> str | None:
        """Promote the first connected player to host. Returns new host id."""
        for player in self.players.values():
            if player.connected:
                self.host_id = player.user_id
                return player.user_id
        return None

    # ---------- drawing ----------
    def add_stroke_segment(self, seg: dict) -> bool:
        """Record one drawn segment for replay. Returns False if the history
        cap is hit (we then stop recording but the live relay still works, so
        the only loss is that very-late joiners miss the overflow)."""
        from config import Config
        n = len(seg.get("points", []))
        if self._history_points + n > Config.MAX_HISTORY_POINTS:
            return False
        self.stroke_ops.append(seg)
        self._history_points += n
        return True

    def clear_strokes(self) -> None:
        self.stroke_ops = []
        self._history_points = 0

    def undo_last_stroke(self) -> str | None:
        """Remove every segment belonging to the most recently drawn stroke.
        Matching by stroke id removes the whole stroke even if segments from
        different drawers interleaved (only possible on the shared Phase 2
        board; in-game only one person draws at a time). Returns the removed
        stroke id, or None if there was nothing to undo."""
        if not self.stroke_ops:
            return None
        last_id = self.stroke_ops[-1].get("strokeId")
        self.stroke_ops = [op for op in self.stroke_ops if op.get("strokeId") != last_id]
        self._history_points = sum(len(op.get("points", [])) for op in self.stroke_ops)
        return last_id

    # ---------- word / guessing ----------
    def set_word(self, word: str, drawer_id: str) -> None:
        """Begin a turn: set the secret word and the drawer, reset who's guessed."""
        self.current_word = word
        self.drawer_id = drawer_id
        self.guessed_order = []
        for p in self.players.values():
            p.has_guessed = False
            p.is_drawer = (p.user_id == drawer_id)

    def clear_word(self) -> None:
        self.current_word = None
        self.drawer_id = None
        self.guessed_order = []
        for p in self.players.values():
            p.has_guessed = False
            p.is_drawer = False

    def register_correct_guess(self, user_id: str) -> bool:
        """Mark a player as having guessed. Returns False if they already had
        (so a duplicate correct message can't be scored or announced twice)."""
        p = self.players.get(user_id)
        if p is None or p.has_guessed or p.is_drawer:
            return False
        p.has_guessed = True
        self.guessed_order.append(user_id)
        return True

    def masked_word(self) -> str:
        """Underscore pattern for guessers, preserving word boundaries."""
        if not self.current_word:
            return ""
        return "   ".join("_ " * len(part) for part in self.current_word.split()).strip()

    def active_guessers(self) -> list:
        """Connected players who are expected to guess (everyone but the drawer)."""
        return [p for p in self.players.values() if p.connected and not p.is_drawer]

    def all_guessed(self) -> bool:
        guessers = self.active_guessers()
        return len(guessers) > 0 and all(p.has_guessed for p in guessers)

    # ---------- serialization ----------
    def public_state(self) -> dict:
        """Full room snapshot broadcast to clients. The single source of truth
        the UI renders from, so there is no client/server state to drift."""
        return {
            "code": self.code,
            "host_id": self.host_id,
            "state": self.state,
            "settings": self.settings,
            "players": [p.public() for p in self.players.values()],
        }