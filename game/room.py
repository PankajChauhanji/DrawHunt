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