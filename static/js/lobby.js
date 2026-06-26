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
  const wordModeSel = document.getElementById("wordmode-select");
  const showThemeToggle = document.getElementById("show-theme-toggle");
  const showLangToggle = document.getElementById("show-language-toggle");
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
  const wordContext = document.getElementById("word-context");
  const roundBadge = document.getElementById("round-badge");
  const timerEl = document.getElementById("timer");
  const toolbarEl = document.querySelector(".toolbar");
  let boardCtl = null;          // BoardView instance (lazy-initialised once)
  let chatCtl = null;           // ChatView instance
  let boardReady = false;
  let lastState = null;         // most recent room snapshot
  let amDrawer = false;         // do I hold the word this turn?
  let timerHandle = null;       // countdown interval
  let chooseTimerHandle = null; // word-choice countdown interval

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
    const isHost = state.host_id === myUid;
    const sorted = state.players.slice().sort(function (a, b) { return b.score - a.score; });
    sorted.forEach(function (p, i) {
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
      // lead over the next-ranked player
      const lead = document.createElement("span");
      lead.className = "sp-lead";
      const next = sorted[i + 1];
      if (next) {
        const diff = p.score - next.score;
        lead.textContent = diff > 0 ? "+" + diff : "";
      }
      row.append(av, nm, badge, sc, lead);
      // host kick control (not on self)
      if (isHost && p.user_id !== myUid) {
        const kick = document.createElement("button");
        kick.className = "kick-btn";
        kick.title = "Remove " + p.name;
        kick.setAttribute("aria-label", "Remove " + p.name);
        kick.textContent = "✕";
        kick.addEventListener("click", function () {
          if (confirm("Remove " + p.name + " from the game?")) {
            socket.emit("remove_player", { user_id: p.user_id });
          }
        });
        row.append(kick);
      }
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
      if (isHost && p.user_id !== myUid) {
        const kick = document.createElement("button");
        kick.className = "kick-btn";
        kick.title = "Remove " + p.name;
        kick.setAttribute("aria-label", "Remove " + p.name);
        kick.textContent = "✕";
        kick.addEventListener("click", function () {
          if (confirm("Remove " + p.name + " from the room?")) {
            socket.emit("remove_player", { user_id: p.user_id });
          }
        });
        row.append(kick);
      }
      playersEl.appendChild(row);
    });
    playerCountEl.textContent = connected.length + "/" + cfg.maxPlayers;

    // settings
    roundsSel.value = String(state.settings.rounds);
    durationSel.value = String(state.settings.duration);
    if (wordModeSel) wordModeSel.value = state.settings.word_mode || "auto";
    if (showThemeToggle) showThemeToggle.checked = !!state.settings.show_theme;
    if (showLangToggle) showLangToggle.checked = !!state.settings.show_language;
    roundsSel.disabled = !isHost;
    durationSel.disabled = !isHost;
    if (wordModeSel) wordModeSel.disabled = !isHost;
    if (showThemeToggle) showThemeToggle.disabled = !isHost;
    if (showLangToggle) showLangToggle.disabled = !isHost;
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

    // ---- view switch: lobby vs in-game board ----
    const inGame = (state.state === "CHOOSING" || state.state === "DRAWING" ||
                    state.state === "ROUND_END" || state.state === "GAME_END");
    if (inGame) {
      showBoard(isHost);
      renderSidePlayers(state);
      if (roundBadge) {
        roundBadge.textContent = state.total_rounds
          ? "Round " + state.round + "/" + state.total_rounds : "";
      }
      // If we arrive in CHOOSING (e.g. as a late joiner) and we're not the
      // drawer, reflect that someone is choosing.
      if (state.state === "CHOOSING" && state.drawer_id !== myUid) {
        const d = state.players.find(function (p) { return p.user_id === state.drawer_id; });
        if (wordBar) wordBar.textContent = (d ? d.name : "Someone") + " is choosing a word…";
      }
    } else {
      showLobby();
      amDrawer = false;
      stopTimer();
      if (wordBar) wordBar.textContent = "·····";
      if (roundBadge) roundBadge.textContent = "";
      setWordContext(null);
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

  // ---- per-turn timer (visual only; the server is authoritative) ----
  function startTimer(seconds) {
    stopTimer();
    let left = Math.max(0, Math.round(seconds));
    function tick() {
      if (timerEl) {
        timerEl.textContent = "⏱ " + left + "s";
        timerEl.classList.toggle("low", left <= 10);
      }
      if (left <= 0) { stopTimer(); return; }
      left -= 1;
    }
    tick();
    timerHandle = setInterval(tick, 1000);
  }
  function stopTimer() {
    if (timerHandle) { clearInterval(timerHandle); timerHandle = null; }
    if (timerEl) { timerEl.textContent = ""; timerEl.classList.remove("low"); }
  }

  function hideOverlay() {
    overlay.classList.remove("show");
    if (chooseTimerHandle) { clearInterval(chooseTimerHandle); chooseTimerHandle = null; }
  }

  // Enable/disable drawing for this client and show the toolbar only to the drawer.
  function setDrawer(isDrawer) {
    amDrawer = isDrawer;
    if (boardCtl) boardCtl.setEnabled(isDrawer);
    if (toolbarEl) toolbarEl.style.visibility = isDrawer ? "visible" : "hidden";
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
    // ---- word state ----
    socket.on("your_word", function (d) {
      setDrawer(true);
      setWordContext(null);   // the drawer sees the real word; no hint needed
      if (wordBar) {
        wordBar.textContent = "You're drawing: " + d.word;
        wordBar.classList.add("is-drawer");
      }
    });
    socket.on("word_hint", function (d) {
      setDrawer(false);
      setWordContext(d.context);
      if (wordBar) {
        wordBar.textContent = d.mask || "·····";
        wordBar.classList.remove("is-drawer");
      }
    });

    // ---- game loop (Phase 4) ----
    socket.on("your_turn", function (d) {
      // I'm the drawer — pick (auto) or type (own) a word before the timer ends.
      stopTimer();
      if (chooseTimerHandle) { clearInterval(chooseTimerHandle); chooseTimerHandle = null; }
      if (wordBar) { wordBar.textContent = "Your turn — pick a word!"; wordBar.classList.remove("is-drawer"); }
      const secs = d.duration || 10;

      let body;
      if (d.mode === "own") {
        body =
          '<h2>Type a word to draw</h2>' +
          '<p class="overlay-sub">Round ' + d.round + " of " + d.total_rounds +
          " — others will guess this</p>" +
          '<input id="own-word" class="field" maxlength="40" placeholder="your secret word" autocomplete="off" autofocus />' +
          '<button id="own-go" class="btn btn-primary">Start drawing</button>' +
          '<p class="choose-timer" id="choose-timer">Auto-picks in ' + secs + "s</p>";
      } else {
        const btns = d.choices.map(function (w) {
          return '<button class="btn btn-primary choice" data-word="' +
            w.replace(/"/g, "&quot;") + '">' + escapeHtml(w) + "</button>";
        }).join("");
        body =
          '<h2>Choose a word to draw</h2>' +
          '<p class="overlay-sub">Round ' + d.round + " of " + d.total_rounds + "</p>" +
          '<div class="choice-row">' + btns + "</div>" +
          '<p class="choose-timer" id="choose-timer">Auto-picks in ' + secs + "s</p>";
      }
      overlayBody.innerHTML = body;
      overlay.classList.add("show");

      if (d.mode === "own") {
        const input = document.getElementById("own-word");
        const go = document.getElementById("own-go");
        function submitOwn() {
          const w = input.value.trim();
          if (!w) { input.focus(); return; }
          if (chooseTimerHandle) { clearInterval(chooseTimerHandle); chooseTimerHandle = null; }
          socket.emit("choose_word", { word: w });
          hideOverlay();
        }
        go.addEventListener("click", submitOwn);
        input.addEventListener("keydown", function (e) { if (e.key === "Enter") submitOwn(); });
        if (input.focus) input.focus();
      } else {
        overlayBody.querySelectorAll(".choice").forEach(function (b) {
          b.addEventListener("click", function () {
            if (chooseTimerHandle) { clearInterval(chooseTimerHandle); chooseTimerHandle = null; }
            socket.emit("choose_word", { word: b.dataset.word });
            hideOverlay();
          });
        });
      }

      // local countdown (the server is what actually auto-picks at 0)
      let left = secs;
      const ct = document.getElementById("choose-timer");
      chooseTimerHandle = setInterval(function () {
        left -= 1;
        if (left <= 0) {
          clearInterval(chooseTimerHandle); chooseTimerHandle = null;
          if (ct) ct.textContent = "Picking one for you…";
          overlayBody.querySelectorAll(".choice, #own-go, #own-word").forEach(function (b) { b.disabled = true; });
          return;
        }
        if (ct) ct.textContent = "Auto-picks in " + left + "s";
      }, 1000);
    });

    socket.on("choosing", function (d) {
      // The drawer keeps their word-choice popup (driven by your_turn); this
      // event is only to tell the OTHER players who is choosing.
      if (d.drawer_id === myUid) return;
      hideOverlay();
      stopTimer();
      setWordContext(null);
      if (wordBar) {
        wordBar.classList.remove("is-drawer");
        wordBar.textContent = d.drawer_name + " is choosing a word…";
      }
    });

    socket.on("turn_start", function (d) {
      hideOverlay();
      setDrawer(d.drawer_id === myUid);
      if (d.drawer_id === myUid) setWordContext(null);
      else if (d.context) setWordContext(d.context);
      startTimer(d.duration);
    });

    socket.on("turn_end", function (d) {
      stopTimer();
      setDrawer(false);
      setWordContext(null);
      const rows = (function () {
        if (!d.awards || !Object.keys(d.awards).length) return "<p class='overlay-sub'>Nobody guessed it.</p>";
        const names = {};
        (lastState ? lastState.players : []).forEach(function (p) { names[p.user_id] = p.name; });
        return "<div class='award-row'>" + Object.keys(d.awards).map(function (uid) {
          return "<div class='award'><span>" + escapeHtml(names[uid] || "?") +
            "</span><span class='pts'>+" + d.awards[uid] + "</span></div>";
        }).join("") + "</div>";
      })();
      overlayBody.innerHTML =
        "<h2>The word was</h2><p class='reveal-word'>" + escapeHtml(d.word || "") + "</p>" + rows;
      overlay.classList.add("show");
    });

    socket.on("game_end", function (d) {
      stopTimer();
      setDrawer(false);
      const isHost = lastState && lastState.host_id === myUid;
      const scores = d.scores || [];
      const top = scores.slice(0, 3);
      const rest = scores.slice(3);

      // podium: 2nd | 1st | 3rd, ordered so the winner is centre + tallest
      const podiumOrder = [top[1], top[0], top[2]];
      const heights = ["mid", "high", "low"];
      const medals = ["🥈", "🥇", "🥉"];
      const podium = '<div class="podium">' + podiumOrder.map(function (p, i) {
        if (!p) return "";
        return '<div class="pod ' + heights[i] + (p.user_id === myUid ? " me" : "") + '">' +
          '<span class="pod-medal">' + medals[i] + "</span>" +
          '<span class="pod-name">' + escapeHtml(p.name) + "</span>" +
          '<span class="pod-score">' + p.score + "</span>" +
          '<span class="pod-base"></span></div>';
      }).join("") + "</div>";

      const list = rest.length
        ? '<div class="final-list">' + rest.map(function (p, i) {
            var isLast = (i === rest.length - 1);
            var emoji = isLast ? "😭" : "😔";
            return '<div class="final-row' + (p.user_id === myUid ? " me" : "") + '">' +
              '<span class="rank">' + (i + 4) + ".</span>" +
              '<span class="final-emoji">' + emoji + "</span>" +
              '<span class="final-name">' + escapeHtml(p.name) + "</span>" +
              '<span class="final-score">' + p.score + "</span></div>";
          }).join("") + "</div>"
        : "";

      overlayBody.innerHTML =
        '<h2>Game over!</h2>' + podium + list +
        (isHost
          ? "<button id='play-again' class='btn btn-primary'>Play again</button>" +
            "<button id='to-lobby' class='btn btn-ghost'>Back to lobby</button>"
          : "<p class='overlay-sub'>Waiting for the host…</p>");
      overlay.classList.add("show");
      const pa = document.getElementById("play-again");
      const tl = document.getElementById("to-lobby");
      if (pa) pa.addEventListener("click", function () { hideOverlay(); socket.emit("start_game", {}); });
      if (tl) tl.addEventListener("click", function () { hideOverlay(); socket.emit("back_to_lobby", {}); });
    });

    socket.on("room_error", function (e) {
      if (e.code === "NO_NAME") {
        ensureNameThen(function () {
          socket.emit("join_room", { code: cfg.code, name: Identity.getName(), user_id: myUid });
        });
      } else if (e.fatal) {
        fatalError(e.message);
      } else {
        settingsNote.textContent = e.message;
        if (chatCtl && boardView.style.display !== "none") chatCtl.note(e.message);
      }
    });

    socket.on("kicked", function () {
      stopTimer();
      overlayBody.innerHTML =
        '<h2>Removed from the room</h2>' +
        '<p class="overlay-sub">The host removed you from this game.</p>' +
        '<a class="btn btn-primary" href="/">Back to home</a>';
      overlay.classList.add("show");
      try { socket.disconnect(); } catch (_) {}
    });

    socket.on("reaction", function (d) {
      if (d && d.emoji) spawnReaction(d.emoji);
    });

    // host controls
    roundsSel.addEventListener("change", pushSettings);
    durationSel.addEventListener("change", pushSettings);
    if (wordModeSel) wordModeSel.addEventListener("change", pushSettings);
    if (showThemeToggle) showThemeToggle.addEventListener("change", pushSettings);
    if (showLangToggle) showLangToggle.addEventListener("change", pushSettings);
    startBtn.addEventListener("click", function () { socket.emit("start_game", {}); });
    backBtn.addEventListener("click", function () { socket.emit("back_to_lobby", {}); });

    setupReactions();
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function pushSettings() {
    socket.emit("update_settings", {
      rounds: parseInt(roundsSel.value, 10),
      duration: parseInt(durationSel.value, 10),
      word_mode: wordModeSel ? wordModeSel.value : "auto",
      show_theme: showThemeToggle ? showThemeToggle.checked : false,
      show_language: showLangToggle ? showLangToggle.checked : false,
    });
  }

  // Theme/Language hint shown above the word for guessers (host-toggleable).
  function setWordContext(ctx) {
    if (!wordContext) return;
    if (!ctx || (!ctx.language && !ctx.theme)) {
      wordContext.textContent = "";
      wordContext.style.display = "none";
      return;
    }
    const parts = [];
    if (ctx.language) parts.push("Language: " + ctx.language);
    if (ctx.theme) parts.push("Theme: " + ctx.theme);
    wordContext.textContent = parts.join("   ·   ");
    wordContext.style.display = "";
  }

  // Reactions: Praise, Dislike, Rage, and Chaos
  const REACTIONS = [
    "👍", "❤️", "🔥", "😂", "🎨", "🧠", "🎯",
    "👎", "🤮", "🍅", "🗑️", "😡", "😤", "🤦",
    "❓", "🤷", "🥱", "🤡", "💩", "👀"
  ];

  function setupReactions() {
    const btn = document.getElementById("reaction-btn");
    const picker = document.getElementById("reaction-picker");
    if (!btn || !picker || btn._wired) return;
    btn._wired = true;

    picker.innerHTML = "";
    REACTIONS.forEach(function (em) {
      const b = document.createElement("button");
      b.className = "reaction-option";
      b.type = "button";
      b.textContent = em;
      b.addEventListener("click", function (e) {
        e.stopPropagation();
        socket.emit("react", { emoji: em });
        closePicker();
      });
      picker.appendChild(b);
    });

    function openPicker() { picker.classList.add("show"); picker.setAttribute("aria-hidden", "false"); }
    function closePicker() { picker.classList.remove("show"); picker.setAttribute("aria-hidden", "true"); }

    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (picker.classList.contains("show")) closePicker(); else openPicker();
    });
    document.addEventListener("click", function (e) {
      if (!picker.contains(e.target) && e.target !== btn) closePicker();
    });
  }

  function spawnReaction(emoji) {
    const layer = document.getElementById("reactions-layer");
    if (!layer) return;
    const el = document.createElement("span");
    el.className = "reaction-float";
    el.textContent = emoji;
    const left = 28 + Math.random() * 44;          // 28%..72% across the screen
    const drift = (Math.random() * 2 - 1) * 70;    // sideways wander
    const dur = 2600 + Math.random() * 900;
    el.style.left = left + "%";
    el.style.setProperty("--drift", drift + "px");
    el.style.setProperty("--dur", dur + "ms");
    layer.appendChild(el);
    setTimeout(function () { el.remove(); }, dur + 120);
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