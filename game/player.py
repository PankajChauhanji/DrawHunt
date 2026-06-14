"""
Player model.

Identity rule (the spine of reconnection): a player is identified by
`user_id`, which is generated on the client and persists across reconnects.
`sid` is the Socket.IO transport id and CHANGES every time the socket
reconnects, so it is never used as identity — only to address the current
live connection.
"""
from dataclasses import dataclass


@dataclass
class Player:
    user_id: str
    name: str
    sid: str
    score: int = 0
    has_guessed: bool = False        # this turn — drives the "green" UI later
    is_drawer: bool = False
    connected: bool = True
    disconnected_at: float | None = None   # set when the socket drops; used by the sweeper

    def public(self) -> dict:
        """The view of this player that is safe to send to all clients."""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "score": self.score,
            "has_guessed": self.has_guessed,
            "is_drawer": self.is_drawer,
            "connected": self.connected,
        }