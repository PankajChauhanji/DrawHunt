/* Room page (the waiting lobby for Phase 1).
 *
 * Opens the socket, joins the room with our stable identity, and renders the
 * room snapshot the server broadcasts. Host-only controls are shown/enabled
 * based on whether our user_id matches the room's host_id — but the server is
 * the real gate; the UI just reflects it.
 */
(function () {
  "use strict";

  const cfg = window.INKLING; // { code, minPlayers, maxPlayers }
  const myUid = Identity.getUserId();

  // --- elements ---
  const dot = document.getElementById("conn-dot");
  const codeEl = document.getElementById("room-code");
  const copyBtn = document.getElementById("copy-btn");
  const playersEl = document.getElementById("players");
  const playerCountEl = document.getElementById("player-count");
  const roundsSel = document.getElementById("rounds-select");
  const durationSel = document.getElementById("duration-select");
  const settingsNote = document.getElementById("settings-note");
  const startBtn = document.getElementById("start-btn");
  const waitNote = document.getElementById("wait-note");
  const overlay = document.getElementById("overlay");
  const overlayBody = document.getElementById("overlay-body");

  // views + board elements
  const lobbyView = document.getElementById("lobby-view");
  const boardView = document.getElementById("board-view");
  const backBtn = document.getElementById("back-to-lobby");
  const sidePlayersEl = document.getElementById("side-players");
  const wordBar = document.getElementById("word-bar");
  const hostWordTools = document.getElementById("host-word-tools");
  const wordInput = document.getElementById("word-input");
  const setWordBtn = document.getElementById("set-word-btn");
  let boardCtl = null;          // BoardView instance (lazy-initialised once)
  let chatCtl = null;           // ChatView instance
  let boardReady = false;
  let lastState = null;         // most recent room snapshot
  let amDrawer = false;         // do I hold the word this turn?

  codeEl.textContent = cfg.code;

  // Stable avatar colour per player, derived from their user_id.
  const PALETTE = ["#ff5d5d", "#f5b14c", "#36d399", "#5da9ff", "#c98bff", "#ff8fb1", "#4fd1c5", "#f6c744"];
  function colorFor(id) {
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
    return PALETTE[h % PALETTE.length];
  }
  function initials(name) {
    const parts = name.trim().split(/\s+/);
    return ((parts[0] || "?")[0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
  }

  // Scoreboard shown beside the canvas during play.
  function renderSidePlayers(state) {
    if (!sidePlayersEl) return;
    sidePlayersEl.innerHTML = "";
    state.players
      .slice()
      .sort(function (a, b) { return b.score - a.score; })
      .forEach(function (p) {
        const row = document.createElement("div");
        row.className =
          "sp" + (p.has_guessed ? " guessed" : "") + (p.connected ? "" : " offline");
        const av = document.createElement("span");
        av.className = "sp-av";
        av.style.background = colorFor(p.user_id);
        av.textContent = initials(p.name);
        const nm = document.createElement("span");
        nm.className = "sp-name";
        nm.textContent = p.name + (p.user_id === myUid ? " (you)" : "");
        const badge = document.createElement("span");
        badge.className = "sp-badge";
        badge.textContent = p.is_drawer ? "✏️" : (p.has_guessed ? "✓" : "");
        const sc = document.createElement("span");
        sc.className = "sp-score";
        sc.textContent = p.score;
        row.append(av, nm, badge, sc);
        sidePlayersEl.appendChild(row);
      });
  }

  function setConn(state) {
    document.body.dataset.conn = state;
  }

  // ---- name gate: shared links may open the room with no name stored ----
  function ensureNameThen(callback) {
    if (Identity.getName()) {
      callback();
      return;
    }
    overlayBody.innerHTML =
      '<h2>One thing first</h2>' +
      '<p class="overlay-sub">What should we call you?</p>' +
      '<input id="late-name" class="field" maxlength="20" placeholder="Your name" autofocus />' +
      '<button id="late-go" class="btn btn-primary">Join the room</button>';
    overlay.classList.add("show");
    const input = document.getElementById("late-name");
    const go = document.getElementById("late-go");
    function submit() {
      const v = input.value.trim();
      if (!v) { input.focus(); return; }
      Identity.setName(v);
      overlay.classList.remove("show");
      callback();
    }
    go.addEventListener("click", submit);
    input.addEventListener("keydown", function (e) { if (e.key === "Enter") submit(); });
    input.focus();
  }

  // ---- rendering ----
  function render(state) {
    lastState = state;
    const isHost = state.host_id === myUid;
    const players = state.players;
    const connected = players.filter(function (p) { return p.connected; });

    // roster
    playersEl.innerHTML = "";
    players.forEach(function (p) {
      const row = document.createElement("div");
      row.className = "player" + (p.connected ? "" : " offline");
      const av = document.createElement("span");
      av.className = "avatar";
      av.style.background = colorFor(p.user_id);
      av.textContent = initials(p.name);
      const nm = document.createElement("span");
      nm.className = "pname";
      nm.textContent = p.name;
      const tags = document.createElement("span");
      tags.className = "tags";
      if (p.user_id === state.host_id) tags.innerHTML += '<span class="tag host">host</span>';
      if (p.user_id === myUid) tags.innerHTML += '<span class="tag you">you</span>';
      row.append(av, nm, tags);
      playersEl.appendChild(row);
    });
    playerCountEl.textContent = connected.length + "/" + cfg.maxPlayers;

    // settings
    roundsSel.value = String(state.settings.rounds);
    durationSel.value = String(state.settings.duration);
    roundsSel.disabled = !isHost;
    durationSel.disabled = !isHost;
    settingsNote.textContent = isHost
      ? "You're the host — set the rules."
      : "Only the host can change these.";

    // start control
    if (isHost) {
      startBtn.style.display = "";
      waitNote.style.display = "none";
      const enough = connected.length >= cfg.minPlayers;
      startBtn.disabled = !enough;
      startBtn.textContent = enough
        ? "Start drawing"
        : "Need " + cfg.minPlayers + " players to start";
    } else {
      startBtn.style.display = "none";
      waitNote.style.display = "";
      waitNote.textContent = "Waiting for the host to start…";
    }

    // ---- view switch: lobby vs drawing board ----
    if (state.state === "DRAWING") {
      showBoard(isHost);
      renderSidePlayers(state);
      hostWordTools.style.display = isHost ? "" : "none";
    } else {
      showLobby();
      // back in the lobby: reset per-turn UI
      amDrawer = false;
      if (wordBar) wordBar.textContent = "·····";
    }
  }

  function showBoard(isHost) {
    lobbyView.style.display = "none";
    boardView.style.display = "";
    backBtn.style.display = isHost ? "" : "none";
    if (!boardReady) {
      boardCtl = window.BoardView.init({
        canvas: document.getElementById("board-canvas"),
        socket: socket,
        swatches: document.getElementById("swatches"),
        sizes: document.getElementById("sizes"),
        eraser: document.getElementById("eraser-btn"),
        undo: document.getElementById("undo-btn"),
        clear: document.getElementById("clear-btn"),
      });
      chatCtl = window.ChatView.init({
        socket: socket,
        log: document.getElementById("chat-log"),
        input: document.getElementById("chat-input"),
        send: document.getElementById("chat-send"),
      });
      boardReady = true;
    }
    // size the canvas to its now-visible container, then it's ready to draw.
    boardCtl.resize();
  }

  function showLobby() {
    boardView.style.display = "none";
    lobbyView.style.display = "";
  }

  function fatalError(msg) {
    overlayBody.innerHTML =
      '<h2>Can\'t join</h2><p class="overlay-sub">' + msg + "</p>" +
      '<a class="btn btn-primary" href="/">Back to home</a>';
    overlay.classList.add("show");
  }

  // ---- socket ----
  let socket;
  function connect() {
    socket = io();

    socket.on("connect", function () {
      setConn("connected");
      // (Re)join on every connect — this is also what makes reconnect work.
      socket.emit("join_room", {
        code: cfg.code,
        name: Identity.getName(),
        user_id: myUid,
      });
    });
    socket.on("disconnect", function () { setConn("disconnected"); });
    socket.io.on("reconnect_attempt", function () { setConn("connecting"); });

    socket.on("room_update", render);

    // ---- word state (Phase 3) ----
    socket.on("your_word", function (d) {
      amDrawer = true;
      if (wordBar) {
        wordBar.textContent = "You're drawing: " + d.word;
        wordBar.classList.add("is-drawer");
      }
    });
    socket.on("word_hint", function (d) {
      amDrawer = false;
      if (wordBar) {
        wordBar.textContent = d.mask || "·····";
        wordBar.classList.remove("is-drawer");
      }
    });

    socket.on("room_error", function (e) {
      if (e.code === "NO_NAME") {
        ensureNameThen(function () {
          socket.emit("join_room", { code: cfg.code, name: Identity.getName(), user_id: myUid });
        });
      } else if (e.fatal) {
        fatalError(e.message);
      } else {
        // Non-fatal (e.g. "only the host can…") — brief inline flash.
        settingsNote.textContent = e.message;
        if (chatCtl && boardView.style.display !== "none") chatCtl.note(e.message);
      }
    });

    // host controls
    roundsSel.addEventListener("change", pushSettings);
    durationSel.addEventListener("change", pushSettings);
    startBtn.addEventListener("click", function () {
      socket.emit("start_game", {});
    });
    backBtn.addEventListener("click", function () {
      socket.emit("back_to_lobby", {});
    });
    setWordBtn.addEventListener("click", function () {
      const w = wordInput.value.trim();
      if (!w) { wordInput.focus(); return; }
      socket.emit("set_word", { word: w });
      wordInput.value = "";
    });
    wordInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") setWordBtn.click();
    });
  }

  function pushSettings() {
    socket.emit("update_settings", {
      rounds: parseInt(roundsSel.value, 10),
      duration: parseInt(durationSel.value, 10),
    });
  }

  copyBtn.addEventListener("click", function () {
    navigator.clipboard.writeText(cfg.code).then(function () {
      copyBtn.textContent = "Copied!";
      setTimeout(function () { copyBtn.textContent = "Copy code"; }, 1500);
    });
  });

  setConn("connecting");
  ensureNameThen(connect);
})();