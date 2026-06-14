"""
Connection lifecycle handlers.

connect:    log the new socket.
disconnect: map the dropping sid back to a player (via the manager's sid
            index) and mark that player disconnected. We do NOT remove them or
            reassign the host immediately — that would make a simple page
            refresh look like the player (or host) left. The background sweeper
            removes them only after the disconnect grace period, so a refresh
            (reconnect within seconds) is seamless.
"""
import logging

from flask import request

from game.manager import room_manager

log = logging.getLogger("pictionary.connection")


def register(socketio):
    @socketio.on("connect")
    def handle_connect():
        log.info("socket connected: sid=%s", request.sid)

    @socketio.on("disconnect")
    def handle_disconnect():
        log.info("socket disconnected: sid=%s", request.sid)
        lookup = room_manager.unbind_sid(request.sid)
        if not lookup:
            return
        code, user_id = lookup
        room = room_manager.get_room(code)
        if room is None:
            return
        room.mark_disconnected(user_id)
        # Reflect the greyed-out player to everyone still in the room.
        if room.has_connected():
            socketio.emit("room_update", room.public_state(), to=code)