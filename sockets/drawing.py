"""
Drawing socket handlers — the hot path of the whole game.

Events in (client -> server):
    draw          one stroke segment: {strokeId, color, size, erase, points:[[x,y],...]}
                  coords are normalized 0..1; size is normalized by canvas width
    clear_canvas  wipe the board
    undo          remove the most recent stroke

Events out (server -> client):
    draw          a segment, relayed to everyone EXCEPT the sender
    canvas_clear  wipe
    canvas_state  {ops:[...]} authoritative full canvas (used for undo + late join)

Performance contract: the `draw` handler does the minimum — validate, relay,
record. It never transforms geometry. Relay happens before recording so the
network hop isn't delayed by bookkeeping.

Authority (Phase 2): drawing is allowed for anyone in the room while the room
is in the DRAWING state (a shared whiteboard, for exercising the relay). Phase 4
adds the single gate that matters for gameplay: only the current drawer may draw.
"""
import logging
import re

from flask import request
from flask_socketio import emit

from config import Config
from game.manager import room_manager

log = logging.getLogger("draw_hunt.drawing")

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _num01(v) -> bool:
    return isinstance(v, (int, float)) and 0.0 <= v <= 1.0


def _sanitize_segment(data) -> dict | None:
    """Validate and normalize an incoming draw op. Returns a clean dict or
    None if anything is off — malformed input is dropped, never trusted.

    Two op shapes are accepted:
      stroke: {strokeId, color, size, erase, points:[[x,y],...]}
      fill:   {strokeId, type:"fill", color, x, y}   (flood-fill seed point)
    """
    if not isinstance(data, dict):
        return None
    stroke_id = data.get("strokeId")
    color = data.get("color")
    if not isinstance(stroke_id, str) or not (1 <= len(stroke_id) <= 64):
        return None
    if not isinstance(color, str) or not _HEX.match(color):
        return None

    # ---- fill op (bucket tool) ----
    if data.get("type") == "fill":
        x = data.get("x")
        y = data.get("y")
        if not _num01(x) or not _num01(y):
            return None
        return {
            "strokeId": stroke_id,
            "type": "fill",
            "color": color,
            "x": round(float(x), 4),
            "y": round(float(y), 4),
        }

    # ---- stroke op (brush / eraser) ----
    size = data.get("size")
    erase = bool(data.get("erase", False))
    points = data.get("points")

    if not isinstance(size, (int, float)) or not (0.0 < size <= 0.5):
        return None
    if not isinstance(points, list) or not (1 <= len(points) <= Config.MAX_POINTS_PER_SEGMENT):
        return None

    clean_points = []
    for p in points:
        if (isinstance(p, (list, tuple)) and len(p) == 2
                and _num01(p[0]) and _num01(p[1])):
            clean_points.append([round(float(p[0]), 4), round(float(p[1]), 4)])
        else:
            return None

    return {
        "strokeId": stroke_id,
        "color": color,
        "size": round(float(size), 4),
        "erase": erase,
        "points": clean_points,
    }


def _active_room(sid):
    """Resolve sid -> (room, user_id) only if the sender is the current drawer
    in a room that is drawing. This is the gate that makes drawing turn-based:
    a non-drawer's draw/clear/undo events are simply dropped."""
    lookup = room_manager.lookup_sid(sid)
    if not lookup:
        return None, None
    code, user_id = lookup
    room = room_manager.get_room(code)
    if room is None or room.state != "DRAWING":
        return None, None
    if room.drawer_id != user_id:
        return None, None
    return room, user_id


def register(socketio):
    @socketio.on("draw")
    def on_draw(data):
        room, user_id = _active_room(request.sid)
        if room is None:
            return
        seg = _sanitize_segment(data)
        if seg is None:
            return
        # Relay first (lowest latency), then record for replay.
        emit("draw", seg, to=room.code, include_self=False)
        room.add_stroke_segment(seg)

    @socketio.on("clear_canvas")
    def on_clear(data):
        room, user_id = _active_room(request.sid)
        if room is None:
            return
        room.clear_strokes()
        socketio.emit("canvas_clear", {}, to=room.code)

    @socketio.on("undo")
    def on_undo(data):
        room, user_id = _active_room(request.sid)
        if room is None:
            return
        removed = room.undo_last_stroke()
        if removed is not None:
            # Authoritative resync is simplest and correct for an infrequent op.
            socketio.emit("canvas_state", {"ops": room.stroke_ops}, to=room.code)