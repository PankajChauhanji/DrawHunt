"""
Chat & guessing handlers (Phase 3).

The core rule: a correct guess, and any message that would reveal the word,
must never reach a player who is still guessing.

Players fall into two groups:
  - "in the know": the drawer and anyone who has already guessed correctly.
    They have all seen the word.
  - "guessers": everyone else.

Message routing:
  - A guesser typing the EXACT word  -> a correct guess. We mark them, flip
    them green (via room broadcast, which carries has_guessed but never the
    word), post a system line, and DROP the message text entirely.
  - A guesser typing a message that CONTAINS the word -> a leak attempt. It is
    shown only to the in-the-know group (plus the sender), never to guessers.
  - An in-the-know player's chat -> shown only to the in-the-know group, so a
    player who already guessed can't drop hints to those still guessing.
  - Any other message -> normal chat, visible to everyone.

set_word here is TEMPORARY Phase 3 scaffolding so guessing can be tested on the
shared board. Phase 4 replaces it with the proper word-choice + drawer rotation.
"""
import logging
import re

from flask import request
from flask_socketio import emit

from config import Config
from game.manager import room_manager
from sockets.common import broadcast_room

log = logging.getLogger("pictionary.gameplay")

CHAT_MAX_LEN = 200
WORD_MAX_LEN = 40


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _levenshtein(a: str, b: str) -> int:
    """Edit distance between two strings (pure Python, no dependency)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def _is_close(guess: str, target: str) -> bool:
    """A near-miss: close enough to nudge, but not exact (exact is handled
    separately as a correct guess)."""
    threshold = (Config.CLOSE_DISTANCE_SHORT if len(target) <= 4
                 else Config.CLOSE_DISTANCE_LONG)
    dist = _levenshtein(guess, target)
    return 0 < dist <= threshold


def _contains_word(normalized_msg: str, normalized_word: str) -> bool:
    # whole-word containment, so "cat" doesn't trip on "category"
    return re.search(r"\b" + re.escape(normalized_word) + r"\b", normalized_msg) is not None


def _emit_chat_to(socketio, room, payload, recipient_sids):
    for sid in recipient_sids:
        socketio.emit("chat", payload, to=sid)


def _in_know_sids(room):
    return {p.sid for p in room.players.values()
            if p.connected and (p.is_drawer or p.has_guessed)}


def register(socketio):
    @socketio.on("chat")
    def on_chat(data):
        lookup = room_manager.lookup_sid(request.sid)
        if not lookup:
            return
        code, user_id = lookup
        room = room_manager.get_room(code)
        if room is None:
            return
        player = room.get_player(user_id)
        if player is None:
            return

        message = (data.get("message") or "").strip()[:CHAT_MAX_LEN]
        if not message:
            return

        word = room.current_word
        if room.state == "DRAWING" and word:
            normalized = _normalize(message)
            target = _normalize(word)
            in_know = player.is_drawer or player.has_guessed

            # 1. correct guess by someone still guessing
            if not in_know and normalized == target:
                import time as _t
                elapsed = max(0.0, _t.time() - room.turn_started_at) if room.turn_started_at else 0.0
                if room.register_correct_guess(user_id, elapsed):
                    log.info("%s guessed the word in room %s", player.name, code)
                    # flip green for everyone (room_update carries has_guessed, NOT the word)
                    broadcast_room(socketio, room)
                    socketio.emit("chat",
                                  {"system": True, "kind": "guess",
                                   "message": f"{player.name} guessed the word!"},
                                  to=code)
                    emit("guess_feedback", {"correct": True})  # private "you got it"
                    if room.all_guessed():
                        socketio.emit("chat",
                                      {"system": True, "kind": "info",
                                       "message": "Everyone guessed it!"},
                                      to=code)
                        # Phase 4 will end the turn here.
                return

            # 2. a guesser's message that contains the word -> keep it from guessers
            if not in_know and _contains_word(normalized, target):
                recipients = _in_know_sids(room)
                recipients.add(request.sid)  # the sender sees their own message
                _emit_chat_to(socketio, room,
                              {"user_id": user_id, "name": player.name,
                               "message": message, "team": True},
                              recipients)
                return

            # 3. in-the-know chat stays within the in-the-know group
            if in_know:
                _emit_chat_to(socketio, room,
                              {"user_id": user_id, "name": player.name,
                               "message": message, "team": True},
                              _in_know_sids(room))
                return

            # 4. near-miss: nudge ONLY this guesser, privately (no word leak).
            #    The message itself still posts publicly as a normal guess below.
            if _is_close(normalized, target):
                emit("chat", {"system": True, "kind": "close",
                              "message": "😯 So close!"})

        # 5. normal chat to the whole room
        socketio.emit("chat",
                      {"user_id": user_id, "name": player.name, "message": message},
                      to=code)

    @socketio.on("choose_word")
    def on_choose_word(data):
        """The drawer commits a word. In "auto" mode it must be one of the three
        offered; in "own" mode it's whatever the drawer typed. The director is
        waiting in CHOOSING and proceeds once the word is set."""
        lookup = room_manager.lookup_sid(request.sid)
        if not lookup:
            return
        code, user_id = lookup
        room = room_manager.get_room(code)
        if room is None or room.state != "CHOOSING":
            return
        if user_id != room.current_drawer_id():
            return  # only the current drawer may choose
        word = (data.get("word") or "").strip()
        if not word:
            return
        mode = room.settings.get("word_mode", Config.DEFAULT_WORD_MODE)
        if mode == "own":
            word = word[:WORD_MAX_LEN]          # drawer's own word, any value
        elif word not in room.word_choices:
            return                               # auto mode: must be one offered
        room.set_word(word, user_id)
        log.info("drawer set a word in room %s (mode=%s)", code, mode)