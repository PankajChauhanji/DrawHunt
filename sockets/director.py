"""
The game director.

One background task per active game drives the whole loop by polling room state
on a short tick. This avoids fiddly timer-cancellation: early turn end (everyone
guessed) and forced abort (host returns to lobby) are just conditions the loop
checks each tick, not signals that have to interrupt a sleeping timer.

Flow per turn:  CHOOSING -> DRAWING -> ROUND_END  then advance.
The director owns all game-flow emits so the ordering lives in one place; the
socket handlers only validate and mutate small bits of state that the director
observes (e.g. choose_word sets the word; the director sees it and proceeds).
"""
import logging
import random
import time

from config import Config
from game import scoring, words
from game.manager import room_manager
from sockets.common import broadcast_room

log = logging.getLogger("pictionary.director")

TICK = 0.25


def _alive(room):
    """The game should keep running only while the room exists, has someone
    connected, and hasn't been aborted (host returned to lobby clears the flag)."""
    return room is not None and room.has_connected() and room.game_running


def run_game(socketio, code):
    room = room_manager.get_room(code)
    if room is None:
        return
    try:
        room.setup_game()
        broadcast_room(socketio, room)

        while True:
            room = room_manager.get_room(code)
            if not _alive(room):
                return

            drawer_id = room.current_drawer_id()
            if drawer_id is None:
                break  # nobody left to draw -> end game

            if not _run_choosing(socketio, code, drawer_id):
                room = room_manager.get_room(code)
                if not _alive(room):
                    return
                # drawer never picked (left) -> skip their turn
                if room.advance() == "game_over":
                    break
                continue

            _run_drawing(socketio, code, drawer_id)

            room = room_manager.get_room(code)
            if not _alive(room):
                return

            _run_turn_end(socketio, code)
            socketio.sleep(Config.ROUND_END_PAUSE)

            room = room_manager.get_room(code)
            if not _alive(room):
                return
            room.clear_word()
            if room.advance() == "game_over":
                break

        _run_game_end(socketio, code)
    finally:
        room = room_manager.get_room(code)
        if room is not None:
            room.game_running = False


def _run_choosing(socketio, code, drawer_id) -> bool:
    """Offer word choices to the drawer. Returns True once a word is set
    (chosen or auto-picked), False if the drawer left before choosing."""
    room = room_manager.get_room(code)
    room.state = "CHOOSING"
    room.current_word = None
    room.drawer_id = drawer_id
    room.word_choices = words.pick_choices(Config.WORD_CHOICES, room.used_words)
    drawer = room.players[drawer_id]
    for p in room.players.values():
        p.is_drawer = (p.user_id == drawer_id)

    socketio.emit("your_turn",
                  {"choices": room.word_choices,
                   "round": room.current_round, "total_rounds": room.total_rounds},
                  to=drawer.sid)
    socketio.emit("choosing",
                  {"drawer_id": drawer_id, "drawer_name": drawer.name,
                   "round": room.current_round, "total_rounds": room.total_rounds},
                  to=code)
    broadcast_room(socketio, room)

    waited = 0.0
    while True:
        socketio.sleep(TICK)
        waited += TICK
        room = room_manager.get_room(code)
        if not _alive(room):
            return False
        if room.current_word is not None:        # drawer chose (set by handler)
            return True
        d = room.players.get(drawer_id)
        if d is None or not d.connected:         # drawer left while choosing
            return False
        if waited >= Config.CHOOSE_DURATION:     # auto-pick on timeout
            room.set_word(random.choice(room.word_choices), drawer_id)
            return True


def _run_drawing(socketio, code, drawer_id):
    room = room_manager.get_room(code)
    room.used_words.add(room.current_word)
    room.clear_strokes()
    room.state = "DRAWING"
    room.turn_started_at = time.time()
    duration = int(room.settings.get("duration", Config.ROUND_DURATION))
    drawer = room.players[drawer_id]

    socketio.emit("canvas_clear", {}, to=code)
    socketio.emit("your_word", {"word": room.current_word}, to=drawer.sid)
    for p in room.players.values():
        if p.connected and p.user_id != drawer_id:
            socketio.emit("word_hint",
                          {"mask": room.masked_word(), "length": len(room.current_word),
                           "drawer_id": drawer_id},
                          to=p.sid)
    socketio.emit("turn_start",
                  {"round": room.current_round, "total_rounds": room.total_rounds,
                   "drawer_id": drawer_id, "drawer_name": drawer.name, "duration": duration},
                  to=code)
    socketio.emit("chat",
                  {"system": True, "kind": "info", "message": f"{drawer.name} is drawing!"},
                  to=code)
    broadcast_room(socketio, room)

    elapsed = 0.0
    drawer_gone_for = 0.0
    while True:
        socketio.sleep(TICK)
        elapsed += TICK
        room = room_manager.get_room(code)
        if not _alive(room):
            return
        if room.all_guessed():
            return
        if elapsed >= duration:
            return
        d = room.players.get(drawer_id)
        if d is None or not d.connected:
            # small grace so a drawer's refresh doesn't instantly kill the turn
            drawer_gone_for += TICK
            if drawer_gone_for >= Config.DRAWER_DISCONNECT_GRACE:
                return
        else:
            drawer_gone_for = 0.0


def _run_turn_end(socketio, code):
    room = room_manager.get_room(code)
    word = room.current_word
    awards = scoring.score_turn(room)
    room.state = "ROUND_END"
    socketio.emit("turn_end",
                  {"word": word, "awards": awards,
                   "round": room.current_round, "total_rounds": room.total_rounds},
                  to=code)
    if word:
        socketio.emit("chat",
                      {"system": True, "kind": "info", "message": f"The word was: {word}"},
                      to=code)
    broadcast_room(socketio, room)


def _run_game_end(socketio, code):
    room = room_manager.get_room(code)
    if room is None:
        return
    room.state = "GAME_END"
    room.clear_word()
    standings = sorted((p.public() for p in room.players.values()),
                       key=lambda x: -x["score"])
    socketio.emit("game_end", {"scores": standings}, to=code)
    broadcast_room(socketio, room)
    log.info("game ended in room %s", code)