/* Canvas engine — the drawing surface, with no networking knowledge.
 *
 * Responsibilities:
 *  - Capture pointer input (mouse + touch via Pointer Events).
 *  - Batch points per animation frame and hand each batch out as a "segment"
 *    (the unit we send over the wire). This is the latency-critical throttle:
 *    ~60 emits/sec max instead of one per raw pointermove.
 *  - Store all coordinates NORMALIZED to 0..1 so every client renders the same
 *    picture regardless of screen size; denormalize only at render time.
 *  - Keep the ordered list of segments so we can replay on resize.
 *
 * Segment shape (also the wire format):
 *   { strokeId, color, size, erase, points: [[nx,ny], ...] }
 * Consecutive segments of one stroke share their boundary point (the client
 * seeds each batch with the last point of the previous batch), so the renderer
 * can draw each segment as an independent polyline and they join seamlessly.
 */
window.Board = (function () {
  "use strict";

  function create(canvas) {
    const ctx = canvas.getContext("2d");
    const ops = [];                 // all segments, in order (for resize replay)
    let enabled = true;
    let tool = { color: "#1f1f1f", size: 6, erase: false };
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

    function onDown(e) {
      if (!enabled) return;
      e.preventDefault();
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

    // ---- public API ----
    return {
      setTool: function (t) { tool = Object.assign({}, tool, t); },
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
      setEnabled: function (v) { enabled = !!v; },
    };
  }

  return { create: create };
})();