// Tiny deterministic animation engine: renderFrame(t) puts the whole page in
// the state it has at time t (seconds), so the renderer can capture any frame.
//
// Times are written relative to the enclosing scene:
//   s+0.5     scene start + 0.5s        e-1     scene end - 1s
//   c2        start of cue 2            c2e     end of cue 2
//   c2@0.4    40% of the way through cue 2 (follow a word in a sentence)
//   any of the above can take a +/- offset, e.g. c1@0.5+0.2
//
// Attributes (elements animated with data-in/out/tap must not use their own
// CSS transform; wrap them instead):
//   data-in="t"  data-fx="up|down|left|right|fade|pop|zoom|screen|phone|none"  data-dur
//   data-out="t" data-fx-out="fade|screen|up|down"  data-dur-out
//   data-type="t" data-text="..." [data-cps] [data-mask="•"] [data-ph="placeholder"]
//   data-count="t" data-from data-to [data-dec] [data-pre] [data-suf] [data-cdur]
//   data-on="t" [data-off="t"] [data-on-cls="name"]   toggles class "on" (or name)
//   data-cls="name@t, other@t"      adds classes from a time on
//   data-progress="t" [data-pdur] [data-ease]   sets CSS var --p from 0 to 1
//   data-draw="t" [data-ddur]       draws an SVG path
//   data-tap="t"                    tap ripple + press (also emits a click sound)
//   data-sfx="name"                 sound effect at the data-in (or data-on) time
//   data-float="amp,period"  data-spin="deg per second"
(function () {
  const TL = window.__TIMELINE__;
  const byId = {};
  TL.scenes.forEach((s) => (byId[s.id] = s));

  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const ease = {
    linear: (p) => p,
    out: (p) => 1 - Math.pow(1 - p, 3),
    in: (p) => p * p * p,
    inOut: (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2),
    back: (p) => 1 + 2.4 * Math.pow(p - 1, 3) + 1.4 * Math.pow(p - 1, 2),
  };

  function time(expr, sc) {
    expr = String(expr).replace(/\s+/g, "");
    if (/^[\d.]+$/.test(expr)) return sc.start + parseFloat(expr);
    const m = expr.match(/^(?:c(\d+)(e|@([\d.]+))?|(s)|(e))([+-][\d.]+)?$/);
    if (!m) throw new Error(`bad time "${expr}" in scene ${sc.id}`);
    let base;
    if (m[1] !== undefined) {
      const cue = sc.cues[+m[1]];
      if (!cue) throw new Error(`no cue ${m[1]} in scene ${sc.id}`);
      if (m[2] === "e") base = cue.end;
      else if (m[3] !== undefined) base = cue.start + parseFloat(m[3]) * (cue.end - cue.start);
      else base = cue.start;
    } else if (m[4]) base = sc.start;
    else base = sc.end;
    return base + (m[6] ? parseFloat(m[6]) : 0);
  }

  const scenes = [];
  const items = [];
  const events = { taps: [], sfx: [], scenes: TL.scenes.map(({ id, start, end }) => ({ id, start, end })) };

  for (const sec of document.querySelectorAll(".scene")) {
    const sc = byId[sec.id];
    if (!sc) throw new Error(`scene ${sec.id} is not in the timeline`);
    const scene = { sec, sc, visible: false };
    scenes.push(scene);
    for (const el of sec.querySelectorAll("*")) {
      const d = el.dataset;
      if (!Object.keys(d).length) continue;
      const it = { el, scene };
      if (d.in) it.in = { t: time(d.in, sc), fx: d.fx || "up", dur: +(d.dur || (d.fx === "phone" ? 0.9 : 0.6)) };
      if (d.out) it.out = { t: time(d.out, sc), fx: d.fxOut || "fade", dur: +(d.durOut || 0.35) };
      if (d.type) it.type = { t: time(d.type, sc), text: d.text || "", cps: +(d.cps || 14), mask: d.mask, ph: d.ph };
      if (d.count) it.count = { t: time(d.count, sc), from: +(d.from || 0), to: +d.to, dec: +(d.dec || 0), pre: d.pre || "", suf: d.suf || "", dur: +(d.cdur || 1) };
      if (d.on) it.on = { t: time(d.on, sc), off: d.off ? time(d.off, sc) : Infinity, cls: d.onCls || "on" };
      if (d.cls) it.cls = d.cls.split(",").map((s) => { const i = s.indexOf("@"); return { n: s.slice(0, i).trim(), t: time(s.slice(i + 1), sc) }; });
      if (d.progress) it.progress = { t: time(d.progress, sc), dur: +(d.pdur || 1), ease: ease[d.ease || "inOut"] };
      if (d.draw) { const len = el.getTotalLength(); it.draw = { t: time(d.draw, sc), dur: +(d.ddur || 1.5), len }; el.style.strokeDasharray = len; }
      if (d.tap) {
        const ring = document.createElement("span");
        ring.className = "tapring";
        el.appendChild(ring);
        it.tap = { t: time(d.tap, sc), ring };
        events.taps.push(it.tap.t);
      }
      if (d.sfx) events.sfx.push({ name: d.sfx, t: it.in ? it.in.t : it.on ? it.on.t : sc.start });
      if (d.float) it.float = d.float.split(",").map(Number);
      if (d.spin) it.spin = +d.spin;
      items.push(it);
    }
  }

  const FADE_OUT = 0.35;
  const FADE_IN = 0.3;
  const last = TL.scenes[TL.scenes.length - 1];

  function sceneOpacity(sc, t) {
    const fin = sc.start === 0 ? clamp(t / 0.6) : clamp((t - sc.start) / FADE_IN);
    const fout = sc === last ? clamp((sc.end - t) / 0.9) : clamp((sc.end - t) / FADE_OUT);
    return Math.min(fin, fout);
  }

  function applyIn(st, a, t) {
    const p = clamp((t - a.t) / a.dur);
    if (a.fx === "none") { st.op *= p > 0 ? 1 : 0; return; }
    const e = a.fx === "pop" ? ease.back(p) : ease.out(p);
    st.op *= clamp(p * 1.6);
    const k = 1 - e;
    switch (a.fx) {
      case "up": st.y += 34 * k; break;
      case "down": st.y -= 34 * k; break;
      case "left": st.x -= 44 * k; break;
      case "right": st.x += 44 * k; break;
      case "pop": st.s *= 0.5 + 0.5 * e; break;
      case "zoom": st.s *= 0.92 + 0.08 * e; break;
      case "screen": st.x += 60 * k; break;
      case "phone": st.y += 90 * k; break;
    }
  }

  function applyOut(st, a, t) {
    const p = clamp((t - a.t) / a.dur);
    const e = ease.in(p);
    st.op *= 1 - p;
    switch (a.fx) {
      case "screen": st.x -= 60 * e; break;
      case "up": st.y -= 30 * e; break;
      case "down": st.y += 60 * e; break;
    }
  }

  const fmt = (v, dec) => v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });

  function renderItem(it, t) {
    const el = it.el;
    if (it.in || it.out || it.tap || it.float || it.spin) {
      const st = { op: 1, x: 0, y: 0, s: 1, r: 0 };
      if (it.in) applyIn(st, it.in, t);
      if (it.out) applyOut(st, it.out, t);
      if (it.tap) {
        const dt = t - it.tap.t;
        if (dt > -0.1 && dt < 0.3) st.s *= 1 - 0.05 * Math.sin(Math.PI * clamp((dt + 0.1) / 0.4));
        const p = clamp(dt / 0.6);
        it.tap.ring.style.opacity = dt < 0 || dt > 0.6 ? 0 : 1 - ease.in(p);
        it.tap.ring.style.transform = `translate(-50%, -50%) scale(${0.35 + 1.1 * ease.out(p)})`;
      }
      if (it.float) st.y += it.float[0] * Math.sin((2 * Math.PI * t) / it.float[1]);
      if (it.spin) st.r = (t * it.spin) % 360;
      el.style.opacity = st.op;
      el.style.visibility = st.op <= 0.001 ? "hidden" : "";
      el.style.transform = `translate(${st.x}px, ${st.y}px) scale(${st.s}) rotate(${st.r}deg)`;
    }
    if (it.type) {
      const a = it.type;
      const len = a.text.length;
      const n = clamp(Math.floor((t - a.t) * a.cps), 0, len);
      const done = a.t + len / a.cps;
      if (n === 0 && a.ph && t < a.t) { el.textContent = a.ph; el.classList.add("ph"); }
      else { el.textContent = a.mask ? a.mask.repeat(n) : a.text.slice(0, n); el.classList.remove("ph"); }
      const active = t >= a.t - 0.4 && t < done + 0.7;
      el.classList.toggle("caret", active);
      el.classList.toggle("blink", active && (t < a.t || t > done) && Math.floor(t * 2.4) % 2 === 1);
    }
    if (it.count) {
      const a = it.count;
      const v = a.from + (a.to - a.from) * ease.out(clamp((t - a.t) / a.dur));
      el.textContent = a.pre + fmt(v, a.dec) + a.suf;
    }
    if (it.on) el.classList.toggle(it.on.cls, t >= it.on.t && t < it.on.off);
    if (it.cls) for (const c of it.cls) el.classList.toggle(c.n, t >= c.t);
    if (it.progress) el.style.setProperty("--p", it.progress.ease(clamp((t - it.progress.t) / it.progress.dur)));
    if (it.draw) el.style.strokeDashoffset = it.draw.len * (1 - ease.inOut(clamp((t - it.draw.t) / it.draw.dur)));
  }

  // ---- global layers ----
  const capBox = document.querySelector("#captions .box");
  const caps = TL.captions.map((c, i, all) => ({
    ...c,
    fadeIn: i === 0 || c.start - all[i - 1].end > 0.1,
    fadeOut: i === all.length - 1 || all[i + 1].start - c.end > 0.1,
  }));
  const progressEl = document.getElementById("progress");
  const segs = [...progressEl.querySelectorAll(".seg")];
  const stepScenes = TL.scenes.filter((s) => /^step\d$/.test(s.id));
  const blobs = [...document.querySelectorAll("#bg .blob")];

  function renderGlobal(t) {
    const cap = caps.find((c) => t >= c.start && t < c.end);
    if (cap) {
      if (capBox.textContent !== cap.text) capBox.textContent = cap.text;
      const fi = cap.fadeIn ? clamp((t - cap.start) / 0.15) : 1;
      const fo = cap.fadeOut ? clamp((cap.end - t) / 0.15) : 1;
      capBox.style.opacity = Math.min(fi, fo);
    } else capBox.style.opacity = 0;

    const first = stepScenes[0], lastStep = stepScenes[stepScenes.length - 1];
    progressEl.style.opacity = Math.min(clamp((t - first.start) / 0.5), clamp((lastStep.end - t) / 0.5));
    const current = stepScenes.findIndex((s) => t >= s.start && t < s.end);
    segs.forEach((seg, i) => {
      seg.classList.toggle("active", i === current);
      seg.classList.toggle("done", current >= 0 && i < current);
    });

    blobs[0].style.transform = `translate(${120 * Math.sin(t / 9)}px, ${60 * Math.cos(t / 7)}px)`;
    blobs[1].style.transform = `translate(${-90 * Math.cos(t / 11)}px, ${80 * Math.sin(t / 8)}px)`;
  }

  window.renderFrame = function (t) {
    for (const s of scenes) {
      const op = sceneOpacity(s.sc, t);
      s.visible = op > 0.001;
      s.sec.style.opacity = op;
      s.sec.style.visibility = s.visible ? "visible" : "hidden";
    }
    for (const it of items) if (it.scene.visible) renderItem(it, t);
    renderGlobal(t);
  };
  window.__EVENTS__ = events;
  window.__DURATION__ = TL.duration;
})();
