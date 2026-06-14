"""
RoomManager: the in-memory registry of all rooms.

A single shared instance (`room_manager`) holds every room for this process.
This is why the server must run as a SINGLE worker (`gunicorn -w 1`): a second
worker would have its own empty registry and players would land in different
copies of the same room.

Also owns the sid -> (code, user_id) index, which is how a bare disconnect
event (which only carries a sid) is mapped back to a player identity.

Concurrency note: under eventlet, handlers are cooperatively scheduled green
threads, so plain dict operations here are effectively atomic between yield
points. No locks are needed at this scale / single process.
"""
import random
import time

from config import Config
from .room import Room


class RoomManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self._sid_index: dict[str, tuple[str, str]] = {}   # sid -> (code, user_id)

    # ---------- codes ----------
    def _generate_code(self) -> str:
        while True:
            code = "".join(
                random.choice(Config.CODE_ALPHABET) for _ in range(Config.CODE_LENGTH)
            )
            if code not in self.rooms:
                return code

    # ---------- rooms ----------
    def create_room(self, host_id: str) -> Room:
        code = self._generate_code()
        room = Room(code=code, host_id=host_id)
        self.rooms[code] = room
        return room

    def get_room(self, code: str) -> Room | None:
        return self.rooms.get((code or "").upper())

    def delete_room(self, code: str) -> None:
        self.rooms.pop(code, None)

    # ---------- sid index ----------
    def bind_sid(self, sid: str, code: str, user_id: str) -> None:
        self._sid_index[sid] = (code, user_id)

    def unbind_sid(self, sid: str) -> tuple[str, str] | None:
        return self._sid_index.pop(sid, None)

    def lookup_sid(self, sid: str) -> tuple[str, str] | None:
        return self._sid_index.get(sid)

    # ---------- cleanup ----------
    def sweep(self, now: float | None = None) -> dict:
        """One cleanup pass. Removes players past the disconnect grace, reassigns
        hosts whose seat was vacated, and deletes rooms empty past the grace.

        Returns a description of what changed so the caller (the socket layer)
        can broadcast the right updates. This keeps the manager free of any
        Socket.IO dependency.
        """
        now = now if now is not None else time.time()
        roster_changed: set[str] = set()
        host_changed: dict[str, str] = {}
        deleted: list[str] = []

        for code, room in list(self.rooms.items()):
            # 1. Drop players who have been gone longer than the grace period.
            expired = [
                uid for uid, p in room.players.items()
                if not p.connected
                and p.disconnected_at is not None
                and now - p.disconnected_at > Config.DISCONNECT_GRACE
            ]
            for uid in expired:
                room.remove_player(uid)
                roster_changed.add(code)

            # 2. If the host's seat is now empty (host was removed above),
            #    promote someone. A host who is merely disconnected-within-grace
            #    keeps the host seat, so a refresh never loses it.
            if room.get_player(room.host_id) is None:
                new_host = room.reassign_host()
                if new_host:
                    host_changed[code] = new_host
                    roster_changed.add(code)

            # 3. Delete rooms that have had no connected players past the grace.
            if (
                not room.has_connected()
                and room.empty_since is not None
                and now - room.empty_since > Config.ROOM_EMPTY_GRACE
            ):
                self.delete_room(code)
                deleted.append(code)
                roster_changed.discard(code)
                host_changed.pop(code, None)

        return {"roster": roster_changed, "host": host_changed, "deleted": deleted}


# Shared singleton imported across the app.
room_manager = RoomManager()