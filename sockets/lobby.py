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

log = logging.getLogger("pictionary.lobby")


def _broadcast_room(socketio, room):
    socketio.emit("room_update", room.public_state(), to=room.code)


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

        if room.state != "LOBBY" and not is_returning:
            return emit("room_error",
                        {"message": "That game has already started.",
                         "code": "STARTED", "fatal": True})

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
        _broadcast_room(socketio, room)

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
        _broadcast_room(socketio, room)

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

        # Phase 1: transition state only. The actual round/draw/guess loop is
        # built in Phase 4 — the client shows a placeholder for STARTING.
        room.state = "STARTING"
        log.info("game starting in room %s", code)
        _broadcast_room(socketio, room)

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
            _broadcast_room(socketio, room)


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