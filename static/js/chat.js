/* Chat UI for the board. Renders the message log and wires the input.
 * Security note: message text is set via textContent, never innerHTML, so a
 * message like "<img onerror=...>" is shown as literal text, not executed.
 */
window.ChatView = (function () {
  "use strict";

  function init(opts) {
    const socket = opts.socket;
    const log = opts.log;
    const input = opts.input;
    const sendBtn = opts.send;

    function atBottom() {
      return log.scrollHeight - log.scrollTop - log.clientHeight < 40;
    }
    function scroll() { log.scrollTop = log.scrollHeight; }

    function addLine(payload) {
      const stick = atBottom();
      const el = document.createElement("div");

      if (payload.system) {
        el.className = "chat-line system" + (payload.kind ? " " + payload.kind : "");
        el.textContent = payload.message;
      } else {
        el.className = "chat-line" + (payload.team ? " team" : "");
        const who = document.createElement("span");
        who.className = "chat-name";
        who.textContent = payload.name + ": ";
        const msg = document.createElement("span");
        msg.className = "chat-msg";
        msg.textContent = payload.message; // safe: literal text
        el.append(who, msg);
      }
      log.appendChild(el);
      if (stick) scroll();
    }

    function addLocal(text, cls) {
      const el = document.createElement("div");
      el.className = "chat-line " + (cls || "system");
      el.textContent = text;
      log.appendChild(el);
      scroll();
    }

    function send() {
      const v = input.value.trim();
      if (!v) return;
      socket.emit("chat", { message: v });
      input.value = "";
    }

    sendBtn.addEventListener("click", send);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); send(); }
    });

    socket.on("chat", addLine);
    socket.on("guess_feedback", function (d) {
      if (d && d.correct) addLocal("You guessed it! 🎉", "system guess");
    });

    return {
      clear: function () { log.innerHTML = ""; },
      note: addLocal,
    };
  }

  return { init: init };
})();