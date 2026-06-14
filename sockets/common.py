"""Small helpers shared by the socket modules.

`broadcast_room` sends the full room snapshot to everyone in the room. Note it
calls `public_state()`, which deliberately never includes the secret word —
only `has_guessed` flags and the rest of the roster — so broadcasting it after
a correct guess flips players green without leaking the answer.
"""


def broadcast_room(socketio, room):
    socketio.emit("room_update", room.public_state(), to=room.code)