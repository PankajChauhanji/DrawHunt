/* Canvas engine — the drawing surface, with no networking knowledge.
 *
 * Responsibilities:
 *  - Capture pointer input (mouse + touch via Pointer Events).
 *  - Batch points per animation frame and hand each batch out as a "segment"
 *    (the unit we send over the wire). This is the latency-critical throttle:
 *    ~60 emits/sec max instead of one per raw pointermove.
 *  - Store all coordinates NORMALIZED to 0..1 so every client renders the same
 *    picture regardless of screen size; denormalize only at render time.
 *  - Keep the ordered list of ops so we can replay on resize / late join.
 *  - Flood fill ("bucket") as a raster op recorded by seed point + colour, so
 *    it replays correctly against whatever was on the canvas at that moment.
 *
 * Op shapes (also the wire format):
 *   stroke: { strokeId, color, size, erase, points: [[nx,ny], ...] }
 *   fill:   { strokeId, type:"fill", color, x, y }
 * Consecutive segments of one stroke share their boundary point (the client
 * seeds each batch with the last point of the previous batch), so the renderer
 * can draw each segment as an independent polyline and they join seamlessly.
 */
window.Board = (function () {
  "use strict";

  function hexToRgb(hex) {
    const m = /^#([0-9a-fA-F]{6})$/.exec(hex || "");
    if (!m) return null;
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function create(canvas) {
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const ops = [];                 // all ops, in order (for resize replay)
    let enabled = true;
    // mode: "brush" | "bucket". erase only applies to brush.
    let tool = { color: "#1f1f1f", size: 6, erase: false, mode: "brush" };
    let onSegment = function () {};

    // logical (CSS px) size of the canvas
    let W = 1, H = 1;

    function fit() {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      W = Math.max(1, rect.width);
      H = Math.max(1, rect.height);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); // draw in CSS px
      ctx.lineCap = "round";
      ctx.lineJoin = "round";
    }

    function redrawAll() {
      ctx.clearRect(0, 0, W, H);
      for (let i = 0; i < ops.length; i++) renderSegment(ops[i]);
    }

    function renderSegment(seg) {
      if (seg && seg.type === "fill") { fillAt(seg); return; }
      const pts = seg.points;
      if (!pts || !pts.length) return;
      ctx.globalCompositeOperation = seg.erase ? "destination-out" : "source-over";
      ctx.strokeStyle = seg.color;
      ctx.fillStyle = seg.color;
      ctx.lineWidth = seg.size * W; // size is normalized by width
      if (pts.length === 1) {
        // a tap / single point -> dot
        ctx.beginPath();
        ctx.arc(pts[0][0] * W, pts[0][1] * H, (seg.size * W) / 2, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.beginPath();
        ctx.moveTo(pts[0][0] * W, pts[0][1] * H);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0] * W, pts[i][1] * H);
        ctx.stroke();
      }
      ctx.globalCompositeOperation = "source-over";
    }

    // ---- flood fill (raster, operates on device pixels) ----
    function fillAt(seg) {
      const cw = canvas.width, ch = canvas.height;
      if (cw < 1 || ch < 1) return;
      const rgb = hexToRgb(seg.color);
      if (!rgb) return;
      let px = Math.round(seg.x * cw);
      let py = Math.round(seg.y * ch);
      px = Math.min(cw - 1, Math.max(0, px));
      py = Math.min(ch - 1, Math.max(0, py));
      floodFill(cw, ch, px, py, rgb);
    }

    function floodFill(cw, ch, sx, sy, rgb) {
      const TOL = 40; // tolerance soaks up anti-aliased edges
      const img = ctx.getImageData(0, 0, cw, ch);
      const data = img.data;
      const start = (sy * cw + sx) * 4;
      const tr = data[start], tg = data[start + 1], tb = data[start + 2], ta = data[start + 3];
      const [fr, fg, fb] = rgb;

      // No-op if the seed already matches the fill colour (prevents pointless work).
      if (Math.abs(tr - fr) <= TOL && Math.abs(tg - fg) <= TOL &&
          Math.abs(tb - fb) <= TOL && Math.abs(ta - 255) <= TOL) {
        return;
      }

      function match(idx) {
        return Math.abs(data[idx] - tr) <= TOL &&
               Math.abs(data[idx + 1] - tg) <= TOL &&
               Math.abs(data[idx + 2] - tb) <= TOL &&
               Math.abs(data[idx + 3] - ta) <= TOL;
      }
      function paint(idx) {
        data[idx] = fr; data[idx + 1] = fg; data[idx + 2] = fb; data[idx + 3] = 255;
      }

      // Scanline flood fill: push spans, walk left/right, seed rows above/below.
      const stack = [[sx, sy]];
      while (stack.length) {
        const [x, y0] = stack.pop();
        let y = y0;
        // walk up to the top of this column span
        let idx = (y * cw + x) * 4;
        while (y >= 0 && match(idx)) { y--; idx -= cw * 4; }
        y++; idx += cw * 4;
        let reachLeft = false, reachRight = false;
        while (y < ch && match(idx)) {
          paint(idx);
          // left neighbour
          if (x > 0) {
            if (match(idx - 4)) {
              if (!reachLeft) { stack.push([x - 1, y]); reachLeft = true; }
            } else { reachLeft = false; }
          }
          // right neighbour
          if (x < cw - 1) {
            if (match(idx + 4)) {
              if (!reachRight) { stack.push([x + 1, y]); reachRight = true; }
            } else { reachRight = false; }
          }
          y++; idx += cw * 4;
        }
      }
      ctx.putImageData(img, 0, 0);
    }

    // ---- local input ----
    let drawing = false;
    let strokeId = null;
    let pending = [];          // points buffered this frame (normalized)
    let lastSeam = null;       // last point already emitted, to seam segments
    let rafId = null;

    function normPoint(e) {
      const rect = canvas.getBoundingClientRect();
      let x = (e.clientX - rect.left) / rect.width;
      let y = (e.clientY - rect.top) / rect.height;
      x = Math.min(1, Math.max(0, x));
      y = Math.min(1, Math.max(0, y));
      return [Math.round(x * 1e4) / 1e4, Math.round(y * 1e4) / 1e4];
    }

    function newStrokeId() {
      return (
        (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2)) +
        "." + Date.now().toString(36)
      ).slice(0, 60);
    }

    function flush() {
      rafId = null;
      if (!pending.length) return;
      const points = lastSeam ? [lastSeam].concat(pending) : pending.slice();
      const seg = {
        strokeId: strokeId,
        color: tool.color,
        size: sizeNorm(),
        erase: tool.erase,
        points: points,
      };
      lastSeam = pending[pending.length - 1];
      pending = [];
      ops.push(seg);
      renderSegment(seg);
      onSegment(seg);
    }

    function scheduleFlush() {
      if (rafId == null) rafId = requestAnimationFrame(flush);
    }

    function sizeNorm() {
      return tool.size / W; // normalize brush size by width
    }

    function doFill(e) {
      const [nx, ny] = normPoint(e);
      const op = { strokeId: newStrokeId(), type: "fill", color: tool.color, x: nx, y: ny };
      ops.push(op);
      renderSegment(op);
      onSegment(op);
    }

    function onDown(e) {
      if (!enabled) return;
      e.preventDefault();
      if (tool.mode === "bucket") { doFill(e); return; }
      drawing = true;
      strokeId = newStrokeId();
      lastSeam = null;
      pending = [normPoint(e)];
      try { canvas.setPointerCapture(e.pointerId); } catch (_) {}
      scheduleFlush();
    }
    function onMove(e) {
      if (!drawing) return;
      pending.push(normPoint(e));
      scheduleFlush();
    }
    function onUp(e) {
      if (!drawing) return;
      drawing = false;
      scheduleFlush(); // emit any remaining buffered points
      strokeId = null;
      lastSeam = null;
      try { canvas.releasePointerCapture(e.pointerId); } catch (_) {}
    }

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointercancel", onUp);
    canvas.addEventListener("pointerleave", function (e) { if (drawing) onUp(e); });

    fit();

    function applyCursor() {
      canvas.style.cursor = !enabled ? "default"
        : (tool.mode === "bucket" ? "cell" : "crosshair");
    }

    // ---- public API ----
    return {
      setTool: function (t) { tool = Object.assign({}, tool, t); applyCursor(); },
      onLocalSegment: function (cb) { onSegment = cb || function () {}; },
      // render a segment that came from the network or a replay
      drawSegment: function (seg) { ops.push(seg); renderSegment(seg); },
      // authoritative replace (undo / late join)
      setOps: function (newOps) {
        ops.length = 0;
        if (Array.isArray(newOps)) for (let i = 0; i < newOps.length; i++) ops.push(newOps[i]);
        redrawAll();
      },
      clear: function () { ops.length = 0; ctx.clearRect(0, 0, W, H); },
      resize: function () { fit(); redrawAll(); },
      setEnabled: function (v) { enabled = !!v; applyCursor(); },
    };
  }

  return { create: create };
})();
