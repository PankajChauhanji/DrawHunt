# Pictionary Game — Complete Build Roadmap

A real-time, multiplayer draw-and-guess game (skribbl.io style) built with **Flask-SocketIO**.
One player draws a chosen word; others guess via chat; scores are awarded by guess order. Rooms hold up to 10 players and run for an admin-selected number of rounds.

---

## 1. Tech Stack (locked)

| Layer | Choice | Why |
|---|---|---|
| Web framework | Flask | Familiar, minimal |
| Real-time | Flask-SocketIO | WebSockets + rooms + broadcast |
| Async worker | eventlet (or gevent) | Non-blocking concurrent sockets — **required**, not optional |
| Frontend | HTML5 Canvas + vanilla JS | Drawing surface; Socket.IO JS client |
| State | In-memory Python dict | Sufficient at 10 users / single instance |
| Server | gunicorn + eventlet worker | Production run command |
| Host | Render / Fly.io / Railway | Free or near-free, WebSocket-capable |

**Hard rule:** run a single server process. In-memory state means horizontal scaling would split rooms across processes. If you ever scale out, you add a Redis adapter — but not now.

---

## 2. Architecture & Data Flow

```
Browser (Canvas + JS)  <-- WebSocket -->  Flask-SocketIO server
        |                                          |
   draws strokes  --emit('draw')-->  relay to room (no processing)
   types guess    --emit('guess')--> server checks word -> award/score
                                      <-- broadcast events back
```

Three event categories, by cost:
- **Hot path (relay only):** drawing strokes. Server does zero logic, just rebroadcasts to the room. Keep this dumb and fast.
- **Logic path:** join, guess, round transitions, scoring. All authority lives server-side.
- **Lifecycle:** connect, disconnect, reconnect.

**Server is the single source of truth.** Clients never decide the word, the scores, or who guessed. They render what the server tells them. This prevents cheating (e.g., reading the word out of client memory) and keeps state consistent.

---

## 3. Project Structure

```
pictionary/
├── app.py                  # Flask app + SocketIO init + entrypoint
├── config.py               # constants: rounds, timers, points, max players
├── requirements.txt
├── game/
│   ├── __init__.py
│   ├── room.py             # Room class: players, state, scoring
│   ├── player.py           # Player dataclass
│   ├── manager.py          # RoomManager: create/find/cleanup rooms
│   └── words.py            # word bank + random word selection
├── sockets/
│   ├── __init__.py
│   ├── connection.py       # connect / disconnect / reconnect handlers
│   ├── lobby.py            # create room, join room, start game
│   ├── drawing.py          # draw / clear / undo relay
│   └── gameplay.py         # guess, round flow, scoring, chat
├── static/
│   ├── css/style.css
│   └── js/
│       ├── socket.js       # connection + event wiring
│       ├── canvas.js       # drawing logic, stroke batching
│       ├── chat.js         # guess/chat input + render
│       └── game.js         # UI state: scoreboard, timer, word choice
└── templates/
    ├── index.html          # landing: create / join
    └── game.html           # the game room
```

Keep socket handlers split by concern (connection / lobby / drawing / gameplay) so files stay small and the event contract is easy to audit.

---

## 4. Core Data Model (server state)

```python
# Player
{
  sid: str,              # Socket.IO session id (changes on reconnect)
  user_id: str,         # stable id stored client-side, survives reconnect
  name: str,
  score: int,
  has_guessed: bool,    # this round — drives the "green profile"
  is_drawer: bool,
  connected: bool,
}

# Room (keyed by group code)
{
  code: str,
  host_id: str,             # admin who set rounds/started
  players: dict[user_id -> Player],
  state: str,               # LOBBY | CHOOSING | DRAWING | ROUND_END | GAME_END
  total_rounds: int,
  current_round: int,
  drawer_order: list[user_id],
  drawer_index: int,
  current_word: str | None,
  word_choices: list[str],
  round_start_ts: float,
  round_duration: int,      # seconds
  stroke_history: list,     # for mid-round joiners to catch up
  guessed_order: list[user_id],  # who guessed, in order, for scoring
}
```

`stroke_history` is the key to a clean experience: when someone joins or reconnects mid-round, you replay it so their canvas matches everyone else's.

---

## 5. Socket Event Contract

This is the API between client and server. Lock it down early — most bugs come from a drifting contract.

### Client → Server
| Event | Payload | Action |
|---|---|---|
| `create_room` | `{name, rounds, duration}` | Create room, return code, make sender host |
| `join_room` | `{code, name, user_id?}` | Add/reattach player, send current state |
| `start_game` | `{code}` | Host only; build drawer order, begin round 1 |
| `choose_word` | `{code, word}` | Drawer picks from the 3 options |
| `draw` | `{code, stroke}` | Relay stroke to room (no logic) |
| `clear_canvas` | `{code}` | Drawer clears; relay + reset stroke_history |
| `chat` | `{code, message}` | Guess attempt OR normal chat |
| `leave_room` | `{code}` | Graceful exit |

### Server → Client
| Event | Payload | Meaning |
|---|---|---|
| `room_joined` | `{code, players, state, you}` | Confirmation + snapshot |
| `player_list` | `{players}` | Roster changed (join/leave/score) |
| `your_turn` | `{word_choices}` | You are the drawer; pick a word |
| `round_start` | `{drawer_id, round, duration, word_length}` | Others see masked word `_ _ _` |
| `draw` | `{stroke}` | Render this stroke |
| `clear_canvas` | `{}` | Wipe canvas |
| `chat` | `{name, message}` | Normal chat line (non-guess) |
| `player_guessed` | `{user_id, name}` | Flip profile green; **word never sent** |
| `round_end` | `{word, scores}` | Reveal word, show round scores |
| `game_end` | `{final_scores}` | Final leaderboard |
| `error` | `{message}` | Bad action / room full / not host |

**Critical privacy rule:** when a player guesses correctly, broadcast only "X guessed it" — never echo their message text to the room, or you leak the answer. The guesser's own client may show a confirmation, but other clients receive only the green-flip event.

---

## 6. Game State Machine

```
LOBBY ──start_game──► CHOOSING ──choose_word/timeout──► DRAWING
                          ▲                                  │
                          │                          (all guessed OR timer ends)
                          │                                  ▼
                       ROUND_END ◄───────────────────────────┘
                          │
              more drawers/rounds left? ──yes──► next drawer (CHOOSING)
                          │ no
                          ▼
                       GAME_END
```

- A **round** = every player has taken one turn as drawer (or your chosen definition — decide this and be consistent).
- After each drawer's turn: reset `has_guessed`, `guessed_order`, `stroke_history`, `current_word`; rotate to next drawer.
- After the last drawer of the last round: `GAME_END`.

Decide early: does "rounds = N" mean N full cycles through all players, or N total turns? This single definition affects the whole flow — write it down in `config.py` as a comment.

---

## 7. Scoring Logic

A simple, fair, well-tested scheme:

**Guessers** — points scale by how early they guess:
```
points = base_points * (time_remaining / round_duration)
# or rank-based: 1st = 100, 2nd = 80, 3rd = 60 ... floor at e.g. 30
```
Rank-based is simpler and feels fair; time-based rewards speed more sharply. Pick one.

**Drawer** — rewarded only if at least one person guesses:
```
if guessed_order:  drawer_points = round(avg_or_fixed_bonus)
else:              drawer_points = 0
```
This matches your spec: if nobody guesses, the drawer also gets 0.

**Edge cases to handle in scoring:**
- Round ends with **nobody** guessing → everyone (incl. drawer) gets 0 that round.
- Round ends early when **everyone** has guessed → end immediately, don't wait for timer.
- A correct guess must be ignored if it arrives after the player already guessed (no double-scoring).
- The drawer's own chat messages are never treated as guesses.

---

## 8. Guess Detection

```python
def is_correct_guess(message, word):
    return message.strip().lower() == word.strip().lower()
```
Keep it strict at first (exact match, case-insensitive, trimmed). Later you can add:
- Optional "close guess" feedback (Levenshtein distance 1 → "you're close!") shown **only** to that guesser.
- Stripping extra internal whitespace.
Avoid fuzzy auto-accept — it causes disputes.

---

## 9. Edge Cases (the part that makes it robust)

This is where clones break. Handle each explicitly.

| Scenario | Handling |
|---|---|
| **Drawer disconnects mid-round** | End round immediately, reveal word, award nobody drawer points, rotate to next drawer. |
| **Guesser disconnects** | Mark `connected=False`; keep their score; remove from active roster display. |
| **Reconnect mid-round** | Match by `user_id` (stored client-side), re-bind new `sid`, replay `stroke_history`, send masked word + remaining time. |
| **Host disconnects** | Promote next player to host (or pause/auto-end if lobby). |
| **Room empties** | RoomManager cleans up the room (timer or zero-connected check) to free memory. |
| **Room full (10)** | Reject join with `error`. |
| **Duplicate names** | Allow but disambiguate, or append a number. |
| **Player joins mid-game** | Add as spectator until next round; insert into drawer order for following rounds. |
| **Drawer never picks a word** | Auto-pick after a short choose-timer, or skip turn. |
| **Empty room code / typo** | Validate, return clear `error`. |

A stable `user_id` (generated client-side, kept in a JS variable for the session) is what makes reconnection work — `sid` changes on every reconnect, so never key players by `sid`.

---

## 10. Drawing Performance (latency targets)

The whole point of the project. Rules:
- **Send vectors, not images.** A stroke is `{x, y, prevX, prevY, color, size}` or a batched array of points.
- **Batch + throttle.** Collect points and emit every ~30–50ms or once per `requestAnimationFrame`, not on every `mousemove`.
- **Normalize coordinates** to 0–1 (fraction of canvas) so different screen sizes render identically. Multiply by local canvas size on receipt.
- **Server relays blindly** — `emit('draw', data, room=code, include_self=False)`. No parsing.
- **Append to `stroke_history`** on the server for replay; cap or clear it on `clear_canvas`.

At 10 users this keeps perceived drawing lag at network-round-trip level (the unavoidable floor), which is your stated goal.

---

## 11. Build Phases (milestone order)

Build in this order — each phase is independently testable.

**Phase 0 — Skeleton**
- Flask app, SocketIO init with eventlet, serve `index.html`.
- Confirm a client connects and `connect`/`disconnect` fire.
- ✅ Done when: server logs a connection from the browser.

**Phase 1 — Rooms & Lobby**
- `create_room` / `join_room`, RoomManager, player roster.
- Landing page → game page with live player list.
- ✅ Done when: two browsers see each other in one room.

**Phase 2 — Drawing relay (the core)**
- Canvas drawing locally → emit strokes → render on other clients.
- Stroke batching + normalized coords + `stroke_history` replay.
- ✅ Done when: drawing on screen A appears smoothly on screen B, and a 3rd joiner sees existing strokes.

**Phase 3 — Chat & guessing**
- `chat` event, guess detection, green-flip, message suppression.
- ✅ Done when: correct guess flips profile green without leaking the word.

**Phase 4 — Game loop**
- State machine, word choice, drawer rotation, round/turn counting, timer.
- ✅ Done when: a full game runs start → finish with turns rotating.

**Phase 5 — Scoring & end screen**
- Per-round scoring, drawer bonus, leaderboard, `game_end`.
- ✅ Done when: scores are correct across a full game.

**Phase 6 — Robustness**
- All Section 9 edge cases. Reconnection. Room cleanup.
- ✅ Done when: you can disconnect/refresh anyone mid-round without corrupting state.

**Phase 7 — Polish & deploy**
- UI styling, sounds/animations, deploy to host, test over real network.
- ✅ Done when: friends on different networks play a clean game.

---

## 12. Testing Strategy

- **Manual multi-client:** open several browser tabs / incognito windows as different players — fastest way to test real-time behavior.
- **Unit tests** for pure logic: scoring, guess detection, drawer rotation, round counting. These don't need sockets and catch most logic bugs.
- **Disconnection drills:** kill tabs at each game phase (choosing, drawing, round-end) and verify recovery.
- **Latency check:** test across networks, not just localhost — localhost hides all real lag.
- **Load sanity:** fill a room to 10 and confirm drawing stays smooth.

---

## 13. Deployment Notes

- Run with: `gunicorn --worker-class eventlet -w 1 app:app`
  **`-w 1` is mandatory** — multiple workers would split your in-memory rooms.
- Free tiers sleep on idle → first joiner eats a cold start. Acceptable for session play.
- Enable WebSocket transport on the host (Render/Fly support it; confirm in their docs).
- Set `cors_allowed_origins` appropriately in SocketIO init.
- Use environment variables for secret key and config, not hardcoded values.

---

## 14. Stretch Goals (after it works)

- Word difficulty tiers / custom word lists per room.
- Hint reveal (uncover letters as time runs down).
- "Close guess" nudges to the guesser only.
- Persistent leaderboard (then you'd introduce a DB).
- Mobile/touch drawing support.
- Round replay / drawing playback.

---

## 15. Sequencing Summary

> Skeleton → Lobby → **Drawing relay** → Chat/guess → Game loop → Scoring → Robustness → Deploy.

Get Phase 2 (drawing relay) feeling good before anything else — it's the heart of the game and the thing your latency goal lives or dies on. Everything after it is comparatively straightforward logic.
