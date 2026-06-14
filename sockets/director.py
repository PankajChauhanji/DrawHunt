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

log = logging.getLogger("draw_hunt.director")

TICK = 0.25


def _build_hint_schedule(word, duration):
    """Decide which letters to reveal and when. Returns [(reveal_time, index)]
    sorted by time. Max revealed ~= HINT_FRACTION of the letters (capped), and
    at least one letter always stays hidden. Reveals are spread evenly across
    the turn: duration/(hints+1), so they trickle out rather than dump at once."""
    positions = [i for i, ch in enumerate(word) if ch != " "]
    n = len(positions)
    if n <= 1 or duration <= 0:
        return []
    max_hints = round(Config.HINT_FRACTION * n)
    max_hints = min(max_hints, Config.HINT_MAX, n - 1)   # never reveal the whole word
    if max_hints <= 0:
        return []
    import random as _r
    chosen = _r.sample(positions, max_hints)
    interval = duration / (max_hints + 1)
    return sorted((interval * (k + 1), chosen[k]) for k in range(max_hints))


def _emit_hint(socketio, room, drawer_id):
    """Push the updated mask to guessers only (the drawer already knows it)."""
    mask = room.masked_word()
    for p in room.players.values():
        if p.connected and p.user_id != drawer_id:
            socketio.emit("word_hint",
                          {"mask": mask, "length": len(room.current_word),
                           "drawer_id": drawer_id},
                          to=p.sid)
    socketio.emit("chat",
                  {"system": True, "kind": "hint", "message": "💡 A letter was revealed"},
                  to=room.code)


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
    (chosen, typed, or auto-picked), False if the drawer left before choosing."""
    room = room_manager.get_room(code)
    room.state = "CHOOSING"
    room.current_word = None
    room.drawer_id = drawer_id
    mode = room.settings.get("word_mode", Config.DEFAULT_WORD_MODE)
    # In "own" mode the drawer types a word, so there are no preset choices.
    room.word_choices = [] if mode == "own" else words.pick_choices(Config.WORD_CHOICES, room.used_words)
    drawer = room.players[drawer_id]
    for p in room.players.values():
        p.is_drawer = (p.user_id == drawer_id)

    socketio.emit("your_turn",
                  {"choices": room.word_choices, "mode": mode,
                   "round": room.current_round, "total_rounds": room.total_rounds,
                   "duration": Config.CHOOSE_DURATION},
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
        if room.current_word is not None:        # drawer chose / typed (set by handler)
            return True
        d = room.players.get(drawer_id)
        if d is None or not d.connected:         # drawer left while choosing
            return False
        if waited >= Config.CHOOSE_DURATION:     # auto-pick on timeout
            # In "own" mode there's no list, so fall back to a random bank word.
            fallback = (room.word_choices or words.pick_choices(1, room.used_words))
            room.set_word(random.choice(fallback) if fallback else words.pick_choices(1)[0], drawer_id)
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

    hint_schedule = _build_hint_schedule(room.current_word, duration)
    elapsed = 0.0
    drawer_gone_for = 0.0
    while True:
        socketio.sleep(TICK)
        elapsed += TICK
        room = room_manager.get_room(code)
        if not _alive(room):
            return
        # reveal any hints whose time has come
        while hint_schedule and elapsed >= hint_schedule[0][0]:
            _t, idx = hint_schedule.pop(0)
            room.revealed_indices.add(idx)
            _emit_hint(socketio, room, drawer_id)
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