/* ============================================================
   Inkling — Phase 0 client
   Opens the Socket.IO connection and reflects its state in the UI.
   This is the browser half of the "connect / disconnect fire" check.
   ============================================================ */

(function () {
  "use strict";

  const body = document.body;
  const statusText = document.getElementById("status-text");
  const sidText = document.getElementById("sid-text");
  const probeBtn = document.getElementById("probe-btn");
  const probeResult = document.getElementById("probe-result");

  // Connect to the same origin that served the page.
  // reconnection defaults are on, which is exactly what we want to observe.
  const socket = io();

  function setState(state, message) {
    body.dataset.state = state;
    statusText.textContent = message;
  }

  // ---- core lifecycle ----
  socket.on("connect", function () {
    setState("connected", "Connected");
    sidText.textContent = "socket id: " + socket.id;
    probeBtn.disabled = false;
  });

  socket.on("disconnect", function (reason) {
    setState("disconnected", "Disconnected");
    sidText.textContent = "reason: " + reason;
    probeBtn.disabled = true;
    probeResult.textContent = "";
  });

  socket.io.on("reconnect_attempt", function () {
    setState("connecting", "Reconnecting…");
  });

  socket.on("connect_error", function (err) {
    setState("disconnected", "Connection error");
    sidText.textContent = err && err.message ? err.message : "unknown error";
  });

  // ---- server acknowledgements (defined in sockets/connection.py) ----
  socket.on("server_hello", function (data) {
    // The server confirms it saw us. The "connect" handler already flipped
    // the dot green; this just proves the server->client channel too.
    console.log("server_hello", data);
  });

  socket.on("pong_check", function (data) {
    const rtt = Math.round(performance.now() - (probeBtn._sentAt || 0));
    probeResult.textContent = "round-trip ok · ~" + rtt + " ms";
    console.log("pong_check", data);
  });

  // ---- manual two-way test ----
  probeBtn.addEventListener("click", function () {
    probeResult.textContent = "pinging…";
    probeBtn._sentAt = performance.now();
    socket.emit("ping_check", { t: Date.now() });
  });
})();