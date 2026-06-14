/* BoardView — connects the canvas engine to the socket and the toolbar.
 * Owns no game state; it relays local segments out and applies remote ones.
 */
window.BoardView = (function () {
  "use strict";

  const COLORS = [
    "#1f1f1f", "#e23b3b", "#f59e0b", "#f5d90a",
    "#2bb24c", "#2b7fff", "#7c3aed", "#d94fa0",
  ];
  const SIZES = [3, 6, 12, 24];

  function init(opts) {
    const canvas = opts.canvas;
    const socket = opts.socket;
    const swatchWrap = opts.swatches;
    const sizeWrap = opts.sizes;
    const eraserBtn = opts.eraser;
    const undoBtn = opts.undo;
    const clearBtn = opts.clear;

    const board = window.Board.create(canvas);
    let current = { color: COLORS[0], size: SIZES[1], erase: false };
    board.setTool(current);

    // build colour swatches
    swatchWrap.innerHTML = "";
    COLORS.forEach(function (c) {
      const b = document.createElement("button");
      b.className = "swatch";
      b.style.background = c;
      b.setAttribute("aria-label", "colour " + c);
      b.addEventListener("click", function () {
        current.color = c;
        current.erase = false;
        board.setTool(current);
        syncToolbar();
      });
      b.dataset.color = c;
      swatchWrap.appendChild(b);
    });

    // build size buttons
    sizeWrap.innerHTML = "";
    SIZES.forEach(function (s) {
      const b = document.createElement("button");
      b.className = "size-btn";
      b.dataset.size = String(s);
      const dot = document.createElement("span");
      dot.className = "size-dot";
      dot.style.width = dot.style.height = Math.min(s, 20) + "px";
      b.appendChild(dot);
      b.addEventListener("click", function () {
        current.size = s;
        board.setTool(current);
        syncToolbar();
      });
      sizeWrap.appendChild(b);
    });

    eraserBtn.addEventListener("click", function () {
      current.erase = !current.erase;
      board.setTool(current);
      syncToolbar();
    });
    undoBtn.addEventListener("click", function () { socket.emit("undo", {}); });
    clearBtn.addEventListener("click", function () {
      if (confirm("Clear the whole canvas?")) socket.emit("clear_canvas", {});
    });

    function syncToolbar() {
      swatchWrap.querySelectorAll(".swatch").forEach(function (el) {
        el.classList.toggle("active", !current.erase && el.dataset.color === current.color);
      });
      sizeWrap.querySelectorAll(".size-btn").forEach(function (el) {
        el.classList.toggle("active", Number(el.dataset.size) === current.size);
      });
      eraserBtn.classList.toggle("active", current.erase);
    }
    syncToolbar();

    // local -> network
    board.onLocalSegment(function (seg) { socket.emit("draw", seg); });

    // network -> canvas
    socket.on("draw", function (seg) { board.drawSegment(seg); });
    socket.on("canvas_clear", function () { board.clear(); });
    socket.on("canvas_state", function (d) { board.setOps((d && d.ops) || []); });

    window.addEventListener("resize", function () { board.resize(); });

    return {
      resize: function () { board.resize(); },
      setEnabled: function (v) { board.setEnabled(v); },
    };
  }

  return { init: init };
})();