// A session as one line, drawn as far as the page says: from the first trade to the last, over
// the previous close. Above that close the line is the colour of a rise, below it the colour of a
// fall. The page moves it with the scroll; a pointer over it reads any moment already drawn.
import { svg } from "./dom";
import { level } from "./format";
import type { ChartData } from "./market";

// A moment of the line: its time (the exchange's clock, as the API gives it), its value, and
// whether it is the line's end.
export type Reading = { time: number; value: number; last: boolean };
export type Extreme = { time: number; value: number };
export type Day = { open: Extreme; high: Extreme; low: Extreme; last: Extreme; prev: number };
export type DayChart = {
  set(data: ChartData | null): Day | null; // null when there is no session to draw
  draw(f: number): void; // how much of the line is drawn, from 0 to 1
};

const HOUR = 3600;
let made = 0;

// The exchange's clock at a moment: "11:05 AM".
export const clock = (time: number) => new Date(time * 1000).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "UTC" });
const oclock = (time: number) => new Date(time * 1000).toLocaleTimeString("en-US", { hour: "numeric", timeZone: "UTC" });

// Round figures for the scale: a few of them between two values.
function ticks(lo: number, hi: number, about = 4): number[] {
  const raw = (hi - lo) / about;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}

// `host` has a size of its own and is the frame the drawing is placed in (position: relative).
export function dayChart(host: HTMLElement, onRead: (r: Reading) => void): DayChart {
  const id = `day-${++made}`;
  let data: ChartData | null = null;
  let points: { t: number; v: number }[] = [];
  let day: Day | null = null;
  let f = 0;
  // What draw() moves, and the scales of the last drawing.
  let parts: { cut: SVGRectElement; tip: SVGGElement; guide: SVGLineElement; cross: SVGGElement; marks: { el: SVGGElement; time: number }[] } | null = null;
  let x = (_t: number) => 0, y = (_v: number) => 0;

  // The line's value at a moment, between the two points around it.
  function valueAt(time: number): number {
    let lo = 0, hi = points.length - 1;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (points[mid].t <= time) lo = mid;
      else hi = mid;
    }
    const [a, b] = [points[lo], points[hi]];
    return b.t === a.t ? b.v : a.v + ((b.v - a.v) * (time - a.t)) / (b.t - a.t);
  }
  const span = () => [points[0].t, points[points.length - 1].t] as const;
  const timeAt = (part: number) => span()[0] + (span()[1] - span()[0]) * part;
  const tone = (v: number) => (v > day!.prev ? "var(--color-up)" : v < day!.prev ? "var(--color-down)" : "var(--color-muted)");

  function render() {
    const [W, H] = [host.clientWidth, host.clientHeight];
    if (!data || !day || W < 80 || H < 80) return;
    parts = null;
    const narrow = W < 520;
    const m = { top: 30, right: narrow ? 62 : 74, bottom: 26 };
    const [pw, ph] = [W - m.right, H - m.top - m.bottom];
    const [first, last] = span();
    // A day of the stock exchange is drawn on the whole session, so that a day under way stops
    // where it is; anything else, on the hours it has traded.
    const startOfDay = first - (first % 86400);
    const end = first - startOfDay === 9.5 * HOUR ? Math.max(last, startOfDay + 16 * HOUR) : last;
    const lo = Math.min(day.low.value, day.prev), hi = Math.max(day.high.value, day.prev);
    const pad = (hi - lo) * 0.14 || hi * 0.001;
    x = (t) => ((t - first) / (end - first)) * pw;
    y = (v) => m.top + ((hi + pad - v) / (hi - lo + 2 * pad)) * ph;

    const el = svg("svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "absolute inset-0 touch-pan-y select-none", role: "img", "aria-label": `${data.name}, the session as a line` });
    const text = (s: string, at: [number, number], anchor: string, cls: string) => {
      const t = svg("text", { x: at[0], y: at[1], "text-anchor": anchor, class: `num text-[11px] ${cls}`, fill: "currentColor" });
      t.textContent = s;
      return t;
    };
    const rule = (yy: number, cls: string, dash = "") =>
      svg("line", { x1: 0, x2: pw, y1: yy, y2: yy, class: cls, stroke: "currentColor", "stroke-width": 1, "stroke-dasharray": dash, "shape-rendering": "crispEdges" });

    // The scale: a few round levels, the previous close among them, and the hours.
    const base = y(day.prev);
    for (const v of ticks(lo - pad * 0.5, hi + pad * 0.5, narrow ? 3 : 4)) {
      if (Math.abs(y(v) - base) < 16) continue;
      el.append(rule(y(v), "text-line"), text(level(v, data.kind), [pw + 8, y(v) + 4], "start", "text-faint"));
    }
    el.append(rule(base, "text-muted", "2 4"), text(level(day.prev, data.kind), [pw + 8, base + 4], "start", "text-ink"),
      text(narrow ? "prev." : "prev. close", [pw + 8, base + 17], "start", "!text-[10px] text-faint"));
    const every = (end - first) / HOUR > 12 ? 6 : (end - first) / HOUR > 7 ? 4 : 2;
    for (let t = Math.ceil(first / HOUR) * HOUR; t <= end; t += HOUR) {
      if ((t / HOUR) % every || x(t) < 18 || x(t) > pw - 18) continue;
      el.append(svg("line", { x1: x(t), x2: x(t), y1: m.top + ph, y2: m.top + ph + 4, class: "text-line-strong", stroke: "currentColor" }),
        text(oclock(t), [x(t), H - 6], "middle", "text-faint"));
    }
    el.append(rule(m.top + ph, "text-line-strong"));

    // The line and the ground between it and the previous close, each in two halves: what is
    // above that close and what is below it.
    const path = points.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p.v).toFixed(1)}`).join("");
    const defs = svg("defs");
    const cut = svg("rect", { x: 0, y: 0, width: 0, height: H });
    const clip = (name: string, ...shapes: SVGElement[]) => {
      const c = svg("clipPath", { id: `${id}-${name}` });
      c.append(...shapes);
      return c;
    };
    defs.append(clip("drawn", cut), clip("above", svg("rect", { x: 0, y: 0, width: pw, height: base })),
      clip("below", svg("rect", { x: 0, y: base, width: pw, height: H - base })));
    const drawn = svg("g", { "clip-path": `url(#${id}-drawn)` });
    for (const [half, color] of [["above", "var(--color-up)"], ["below", "var(--color-down)"]] as const) {
      const g = svg("g", { "clip-path": `url(#${id}-${half})` });
      g.append(svg("path", { d: `${path}L${x(last).toFixed(1)} ${base}L0 ${base}Z`, style: `fill:${color}`, "fill-opacity": 0.1 }),
        svg("path", { d: path, fill: "none", style: `stroke:${color}`, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
      drawn.append(g);
    }
    el.append(defs, drawn);

    // The day's high and its low, each named once the line has passed it.
    const marks = ([["High", day.high, -1], ["Low", day.low, 1]] as const).map(([name, at, side]) => {
      const [mx, my] = [x(at.time), y(at.value)];
      const g = svg("g", { class: "day-mark" });
      g.append(svg("circle", { cx: mx, cy: my, r: 3.5, class: "text-ink-strong", fill: "var(--color-page)", stroke: "currentColor", "stroke-width": 1.5 }),
        text(`${name} ${level(at.value, data!.kind)}`, [Math.min(pw - 4, Math.max(4, mx)), my + (side < 0 ? -10 : 19)],
          mx < 70 ? "start" : mx > pw - 70 ? "end" : "middle", "text-ink-strong"));
      el.append(g);
      return { el: g, time: at.time };
    });

    // The end of what is drawn, and the moment under the pointer.
    const guide = svg("line", { y1: m.top, y2: m.top + ph, class: "text-line-strong", stroke: "currentColor", "stroke-dasharray": "2 3" });
    const tip = svg("g");
    tip.append(svg("circle", { r: 10, class: "day-halo", "fill-opacity": 0.22 }), svg("circle", { r: 4.5, stroke: "var(--color-page)", "stroke-width": 1.5 }));
    const cross = svg("g", { class: "text-ink-strong", visibility: "hidden" });
    cross.append(svg("line", { y1: m.top, y2: m.top + ph, stroke: "currentColor", "stroke-width": 1 }), svg("circle", { r: 4, fill: "var(--color-page)", stroke: "currentColor", "stroke-width": 1.5 }));
    el.append(guide, tip, cross);

    const read = (e: PointerEvent) => {
      const time = Math.min(timeAt(f), Math.max(first, first + ((e.clientX - el.getBoundingClientRect().left) / pw) * (end - first)));
      const v = valueAt(time);
      cross.setAttribute("visibility", "visible");
      cross.firstElementChild!.setAttribute("transform", `translate(${x(time)} 0)`);
      cross.lastElementChild!.setAttribute("transform", `translate(${x(time)} ${y(v)})`);
      onRead({ time, value: v, last: time >= last });
    };
    el.addEventListener("pointermove", read);
    el.addEventListener("pointerdown", read);
    el.addEventListener("pointerleave", () => {
      cross.setAttribute("visibility", "hidden");
      draw(f);
    });

    host.replaceChildren(el);
    parts = { cut, tip, guide, cross, marks };
    draw(f);
  }

  function draw(part: number) {
    f = Math.min(1, Math.max(0, part));
    if (!parts || !day) return;
    const time = timeAt(f), v = valueAt(time);
    parts.cut.setAttribute("width", String(x(time) + 1));
    parts.tip.setAttribute("transform", `translate(${x(time)} ${y(v)})`);
    parts.tip.style.fill = tone(v);
    parts.tip.classList.toggle("is-last", f >= 1);
    parts.guide.setAttribute("transform", `translate(${x(time)} 0)`);
    for (const mark of parts.marks) mark.el.classList.toggle("in", time >= mark.time);
    if (parts.cross.getAttribute("visibility") === "hidden") onRead({ time, value: v, last: f >= 1 });
  }

  function set(next: ChartData | null): Day | null {
    const bars = (next?.bars ?? []).filter((b) => typeof b.time === "number") as (ChartData["bars"][number] & { time: number })[];
    data = bars.length > 1 ? next : null;
    day = null;
    if (data) {
      const step = bars[1].time - bars[0].time;
      points = [{ t: bars[0].time, v: bars[0].open }, ...bars.map((b) => ({ t: b.time + step, v: b.close }))];
      const top = bars.reduce((a, b) => (b.high > a.high ? b : a)), bottom = bars.reduce((a, b) => (b.low < a.low ? b : a));
      const end = points[points.length - 1];
      day = {
        open: { time: bars[0].time, value: bars[0].open }, last: { time: end.t, value: end.v }, prev: data.prev_close,
        high: { time: top.time + step / 2, value: top.high }, low: { time: bottom.time + step / 2, value: bottom.low },
      };
    }
    render();
    return day;
  }

  new ResizeObserver(() => render()).observe(host);
  return { set, draw };
}
