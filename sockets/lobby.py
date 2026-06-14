"""
Lobby socket handlers.

Events in (client -> server):
    join_room        {code, name, user_id}     join or re-attach to a room
    update_settings  {rounds, duration}         host-only; change room settings
    start_game       {}                          host-only; begin the game
    leave_room       {}                          graceful exit

Events out (server -> client):
    room_update      full room snapshot, broadcast to everyone in the room
    room_error       {message, code?, fatal?}    sent only to the acting client

Design choice: a single broadcast event (`room_update`) carries the entire
room state. The client re-renders from it wholesale, so there is no incremental
client state to drift out of sync. At <=10 players these payloads are tiny.

Authority: settings and start are HOST-ONLY and enforced HERE on the server,
keyed off the sid index (not a user_id in the payload, which a client could
spoof). Hiding buttons on the client is only UX; this is the real gate.
"""
import logging

from flask import request
from flask_socketio import emit, join_room as sio_join, leave_room as sio_leave

from config import Config
from game.manager import room_manager
from sockets.common import broadcast_room

log = logging.getLogger("pictionary.lobby")


def register(socketio):
    @socketio.on("join_room")
    def on_join(data):
        code = (data.get("code") or "").strip().upper()
        name = (data.get("name") or "").strip()[: Config.NAME_MAX_LEN]
        user_id = (data.get("user_id") or "").strip()

        if not code or not user_id:
            return emit("room_error", {"message": "Missing room code or identity.", "fatal": True})

        room = room_manager.get_room(code)
        if room is None:
            return emit("room_error",
                        {"message": "We couldn't find that room. Check the code.",
                         "code": "NOT_FOUND", "fatal": True})

        is_returning = user_id in room.players

        # Joining a game already in progress is allowed: the player picks up the
        # live canvas (replayed below) and, once the round loop exists, will
        # spectate until the next turn. (Earlier this was rejected; Phase 2's
        # late-joiner replay and the planned mid-game spectator flow need it.)

        if not is_returning and room.is_full():
            return emit("room_error",
                        {"message": f"That room is full ({Config.MAX_PLAYERS} players).",
                         "code": "FULL", "fatal": True})

        if not name and not is_returning:
            return emit("room_error",
                        {"message": "Please enter a name to join.",
                         "code": "NO_NAME", "fatal": False})

        room.add_player(user_id, name, request.sid)
        sio_join(code)
        room_manager.bind_sid(request.sid, code, user_id)
        log.info("join: %s (%s) -> room %s [%d players]",
                 name, user_id, code, room.player_count())
        broadcast_room(socketio, room)

        # If they joined mid-draw, replay the current canvas to them alone so
        # their board matches everyone else's.
        if room.state == "DRAWING" and room.stroke_ops:
            emit("canvas_state", {"ops": room.stroke_ops})

        # Replay word state too, so a reconnecting drawer recovers their word
        # and guessers get the masked pattern. The real word goes ONLY to the drawer.
        if room.state == "DRAWING" and room.current_word:
            if room.drawer_id == user_id:
                emit("your_word", {"word": room.current_word})
            else:
                emit("word_hint", {"mask": room.masked_word(),
                                   "length": len(room.current_word),
                                   "drawer_id": room.drawer_id})

    @socketio.on("update_settings")
    def on_update_settings(data):
        lookup = room_manager.lookup_sid(request.sid)
        if not lookup:
            return emit("room_error", {"message": "You are not in a room."})
        code, user_id = lookup
        room = room_manager.get_room(code)
        if room is None:
            return emit("room_error", {"message": "Room no longer exists.", "fatal": True})
        if not room.is_host(user_id):
            return emit("room_error", {"message": "Only the host can change settings."})
        if room.state != "LOBBY":
            return emit("room_error", {"message": "Settings are locked once the game starts."})

        # Validate against allowed values; ignore anything out of range.
        rounds = data.get("rounds")
        duration = data.get("duration")
        if rounds in Config.ALLOWED_ROUNDS:
            room.settings["rounds"] = rounds
        if duration in Config.ALLOWED_DURATIONS:
            room.settings["duration"] = duration

        log.info("settings updated in %s by host: %s", code, room.settings)
        broadcast_room(socketio, room)

    @socketio.on("start_game")
    def on_start_game(data):
        lookup = room_manager.lookup_sid(request.sid)
        if not lookup:
            return emit("room_error", {"message": "You are not in a room."})
        code, user_id = lookup
        room = room_manager.get_room(code)
        if room is None:
            return emit("room_error", {"message": "Room no longer exists.", "fatal": True})
        if not room.is_host(user_id):
            return emit("room_error", {"message": "Only the host can start the game."})
        if room.connected_count() < Config.MIN_PLAYERS:
            return emit("room_error",
                        {"message": f"Need at least {Config.MIN_PLAYERS} players to start."})

        # Phase 2: go straight to the shared drawing board with a clean canvas.
        # Phase 4 will insert a CHOOSING state (drawer picks a word) before this.
        room.clear_strokes()
        room.clear_word()
        room.state = "DRAWING"
        log.info("game starting (DRAWING) in room %s", code)
        broadcast_room(socketio, room)

    @socketio.on("back_to_lobby")
    def on_back_to_lobby(data):
        lookup = room_manager.lookup_sid(request.sid)
        if not lookup:
            return emit("room_error", {"message": "You are not in a room."})
        code, user_id = lookup
        room = room_manager.get_room(code)
        if room is None:
            return emit("room_error", {"message": "Room no longer exists.", "fatal": True})
        if not room.is_host(user_id):
            return emit("room_error", {"message": "Only the host can do that."})
        room.clear_strokes()
        room.clear_word()
        room.state = "LOBBY"
        log.info("room %s returned to lobby by host", code)
        broadcast_room(socketio, room)

    @socketio.on("leave_room")
    def on_leave_room(data):
        lookup = room_manager.unbind_sid(request.sid)
        if not lookup:
            return
        code, user_id = lookup
        room = room_manager.get_room(code)
        if room is None:
            return
        was_host = room.is_host(user_id)
        room.remove_player(user_id)
        sio_leave(code)
        if was_host:
            room.reassign_host()
        log.info("leave: %s left room %s", user_id, code)
        if room.has_connected():
            broadcast_room(socketio, room)


def start_sweeper(socketio):
    """Launch the periodic cleanup loop as an eventlet background task."""
    def loop():
        while True:
            socketio.sleep(Config.SWEEP_INTERVAL)
            changes = room_manager.sweep()
            for code in changes["roster"]:
                room = room_manager.get_room(code)
                if room is not None:
                    socketio.emit("room_update", room.public_state(), to=code)
    socketio.start_background_task(loop)