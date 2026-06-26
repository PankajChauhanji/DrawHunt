/* BoardView — connects the canvas engine to the socket and the toolbar.
 * Owns no game state; it relays local ops out and applies remote ones.
 */
window.BoardView = (function () {
  "use strict";

  const COLORS = [
    "#1f1f1f", "#7a7a7a", "#ffffff", "#e23b3b",
    "#f59e0b", "#f5d90a", "#2bb24c", "#1f8f4d",
    "#2b7fff", "#1d4ed8", "#7c3aed", "#d94fa0",
    "#a0522d", "#f7b8c4",
  ];

  function init(opts) {
    const canvas = opts.canvas;
    const socket = opts.socket;

    // Toolbar elements (static in game.html).
    const swatchWrap = document.getElementById("swatches");
    const sizeSlider = document.getElementById("size-slider");
    const previewDot = document.getElementById("brush-preview-dot");
    const brushBtn = document.getElementById("brush-btn");
    const bucketBtn = document.getElementById("bucket-btn");
    const eraserBtn = document.getElementById("eraser-btn");
    const undoBtn = document.getElementById("undo-btn");
    const clearBtn = document.getElementById("clear-btn");

    const board = window.Board.create(canvas);
    let current = { color: COLORS[0], size: 6, erase: false, mode: "brush" };
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
        current.erase = false;        // picking a colour leaves the eraser
        if (current.mode !== "bucket") current.mode = "brush";
        board.setTool(current);
        syncToolbar();
      });
      b.dataset.color = c;
      swatchWrap.appendChild(b);
    });

    // brush size slider
    if (sizeSlider) {
      sizeSlider.value = String(current.size);
      sizeSlider.addEventListener("input", function () {
        current.size = parseInt(sizeSlider.value, 10) || 1;
        board.setTool(current);
        syncToolbar();
      });
    }

    // tool buttons
    brushBtn.addEventListener("click", function () {
      current.mode = "brush"; current.erase = false;
      board.setTool(current); syncToolbar();
    });
    bucketBtn.addEventListener("click", function () {
      current.mode = "bucket"; current.erase = false;
      board.setTool(current); syncToolbar();
    });
    eraserBtn.addEventListener("click", function () {
      current.mode = "brush"; current.erase = true;
      board.setTool(current); syncToolbar();
    });

    undoBtn.addEventListener("click", function () { socket.emit("undo", {}); });
    clearBtn.addEventListener("click", function () {
      if (confirm("Clear the whole canvas?")) socket.emit("clear_canvas", {});
    });

    function syncToolbar() {
      swatchWrap.querySelectorAll(".swatch").forEach(function (el) {
        el.classList.toggle("active", !current.erase && el.dataset.color === current.color);
      });
      brushBtn.classList.toggle("active", current.mode === "brush" && !current.erase);
      bucketBtn.classList.toggle("active", current.mode === "bucket");
      eraserBtn.classList.toggle("active", current.erase);
      // brush preview: size scaled for display, colour reflects current tool
      if (previewDot) {
        const d = Math.max(4, Math.min(28, current.size));
        previewDot.style.width = d + "px";
        previewDot.style.height = d + "px";
        if (current.erase) {
          previewDot.style.background = "transparent";
          previewDot.style.border = "2px dashed var(--muted)";
        } else {
          previewDot.style.background = current.color;
          previewDot.style.border = "1px solid rgba(0,0,0,0.15)";
        }
      }
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
