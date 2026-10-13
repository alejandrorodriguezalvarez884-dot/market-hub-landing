// The parts of the Today page: the day's figures, the sectors' places today against the year's,
// every instrument on one scale over several spans, and the day's widest moves. Each is built
// still and comes in when the page reaches it (lib/motion.ts).
import { add, h, linkTo, svg } from "./dom";
import { change, compact, level, signedPct, toneClass } from "./format";
import type { Mover, Overview, Sector, Snapshot } from "./market";
import { count, reached, rv, still } from "./motion";
import { quoteHref, rateItem, rulerScale } from "./widgets";

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const fill = (v: number) => (v > 0 ? "bg-up up" : v < 0 ? "bg-down down" : "bg-muted");

// --- A mark that moves ---------------------------------------------------------------------------

// The ruler's mark (a stem from zero and a dot at the move), able to go from one place to
// another. It starts at zero and unseen; set() sends it to its place.
export type Mark = { el: HTMLElement; set(move: number | null | undefined, scale: number): void };
export function mark(): Mark {
  const el = h("div", "track live");
  el.setAttribute("aria-hidden", "true");
  const stem = h("span", "track-stem"), dot = h("span", "track-dot");
  add(el, stem, dot);
  return {
    el,
    set(move, scale) {
      el.classList.toggle("set", isNum(move));
      if (!isNum(move)) return;
      const reach = Math.max(-1, Math.min(1, move / scale));
      stem.className = `track-stem ${fill(move)}`;
      dot.className = `track-dot ${fill(move)} ${Math.abs(move) > scale ? "off" : ""}`;
      stem.style.transform = `scaleX(${reach})`;
      dot.style.left = `${50 + reach * 50}%`;
    },
  };
}

// --- The day's figures ---------------------------------------------------------------------------

// An index's name where there is little room for it.
export const shortName = (s: Snapshot) => s.name.replace(" Industrial Average", "");

// One index at the top of the page: its level, counted from the previous close, its move and its
// mark. Picking it takes the reader to its session.
export function figure(s: Snapshot, scale: number, turn: number, onPick: () => void): HTMLElement {
  const el = rv(h("button", "figure group text-left"), turn);
  el.type = "button";
  el.addEventListener("click", onPick);
  const value = h("span", "num block text-[1.45rem] leading-tight text-ink-strong sm:text-[1.7rem]", level(s.price, s.kind));
  const m = mark();
  m.el.style.setProperty("--track", "100%");
  add(el,
    add(h("span", "flex items-baseline justify-between gap-3 text-[13px] text-muted"), h("span", "truncate group-hover:text-ink-strong", shortName(s)),
      h("span", "flex-none whitespace-nowrap opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100", "Its session ↓")),
    value,
    h("span", `num mt-0.5 block text-[13px] ${toneClass(s.change_pct)}`, `${change(s.change, s.kind)} (${signedPct(s.change_pct, 2)})`),
    add(h("span", "mt-2 block"), m.el));
  reached(el, () => {
    count(value, s.price - s.change, s.price, (v) => level(v, s.kind), 1100);
    setTimeout(() => m.set(s.change_pct, scale), still() ? 0 : 120 * turn);
  }, 0);
  return el;
}

// --- Sectors: today's order against the year's ------------------------------------------------

const ROW = 34; // a sector's row, in pixels

// Two columns of the same sectors, each in its own order: the day's on the left, the year's on
// the right, and a line from each sector's place in one to its place in the other. Pointing at a
// sector, on either side, leaves its line alone on the page.
export function sectorSlope(sectors: Sector[]): HTMLElement {
  const today = [...sectors].sort((a, b) => b.change_pct - a.change_pct);
  const year = [...sectors].sort((a, b) => (b.return_ytd ?? 0) - (a.return_ytd ?? 0));
  const el = h("div", "slope");
  const lines = svg("svg", { class: "slope-lines", height: today.length * ROW, "aria-hidden": "true" });
  const left = h("div", "min-w-0"), right = h("div", "min-w-0");
  const labels = new Map<string, HTMLElement[]>(), strokes = new Map<string, SVGGElement>();
  let held: string | null = null; // the sector a tap has left on

  const light = (name: string | null) => {
    el.classList.toggle("dim", !!name);
    labels.forEach((els, key) => els.forEach((e) => e.classList.toggle("on", key === name)));
    strokes.forEach((g, key) => g.classList.toggle("on", key === name));
  };
  // Pointing at a part of a sector lights it; a tap or a click leaves it lit until the next one.
  const follow = (part: Element, name: string) => {
    part.addEventListener("pointerenter", () => light(name));
    part.addEventListener("pointerleave", () => light(held));
    part.addEventListener("focus", () => light(name));
    part.addEventListener("blur", () => light(held));
    part.addEventListener("click", () => light((held = held === name ? null : name)));
  };
  const label = (s: Sector, side: "l" | "r") => {
    const v = side === "l" ? s.change_pct : s.return_ytd;
    const b = h("button", "slope-row");
    b.type = "button";
    b.style.height = `${ROW}px`;
    const name = h("span", `min-w-0 flex-1 truncate text-ink-strong ${side === "l" ? "text-right" : "hidden text-left sm:block"}`, s.name);
    const fig = h("span", `num w-[4.1rem] flex-none text-[13px] ${side === "l" ? "text-right" : "text-left"} ${toneClass(v)}`, signedPct(v, side === "l" ? 2 : 1));
    add(b, ...(side === "l" ? [name, fig] : [fig, name]));
    follow(b, s.name);
    labels.set(s.name, [...(labels.get(s.name) ?? []), b]);
    return add(h("div"), b);
  };
  today.forEach((s, i) => left.append(rv(label(s, "l"), i)));
  year.forEach((s, i) => right.append(rv(label(s, "r"), i + 5)));

  // The lines are drawn in the pixels the middle column has, and again when it changes.
  const draw = () => {
    const w = lines.clientWidth;
    if (!w) return;
    lines.setAttribute("viewBox", `0 0 ${w} ${today.length * ROW}`);
    lines.replaceChildren(...today.map((s, i) => {
      const [y0, y1] = [(i + 0.5) * ROW, (year.indexOf(s) + 0.5) * ROW];
      const d = `M5 ${y0}C${w / 2} ${y0} ${w / 2} ${y1} ${w - 5} ${y1}`;
      const g = svg("g", { class: `slope-line ${s.change_pct >= 0 ? "text-up" : "text-down"}`, style: `--i:${i}` });
      const hit = svg("path", { d, fill: "none", stroke: "transparent", "stroke-width": 16, "pointer-events": "stroke" });
      follow(hit, s.name);
      g.append(svg("path", { d, pathLength: 1, class: "slope-path", fill: "none", stroke: "currentColor", "stroke-width": 1.5 }),
        svg("circle", { cx: 5, cy: y0, r: 3, fill: "currentColor" }), svg("circle", { cx: w - 5, cy: y1, r: 3, fill: "currentColor", class: "slope-end" }), hit);
      strokes.set(s.name, g);
      return g;
    }));
    light(held);
  };
  add(el,
    h("div", "slope-head pr-[0.1rem] text-right", "Today"), h("div"), h("div", "slope-head", "This year"),
    left, lines, right);
  new ResizeObserver(draw).observe(lines);
  reached(lines, () => lines.classList.add("in"));
  return el;
}

// How many sectors are up and how many are down, as two figures.
export function breadth(sectors: Sector[]): HTMLElement {
  const [up, down] = [sectors.filter((s) => s.change_pct > 0).length, sectors.filter((s) => s.change_pct < 0).length];
  const one = (n: number, word: string, tone: string, turn: number) => {
    const fig = h("span", `num block text-[3.4rem] leading-none ${tone}`, "0");
    const cell = rv(add(h("div"), fig, h("span", "mt-2 block text-[13px] text-muted", word)), turn);
    reached(cell, () => count(fig, 0, n, (v) => String(Math.round(v)), 700));
    return cell;
  };
  return add(h("div", "flex gap-10"), one(up, up === 1 ? "sector up" : "sectors up", "up", 0), one(down, down === 1 ? "sector down" : "sectors down", "down", 1));
}

// --- Everything on one scale ----------------------------------------------------------------------

export const SPANS = [
  { key: "day", label: "Today", of: (s: Snapshot) => s.change_pct },
  { key: "1m", label: "1 month", of: (s: Snapshot) => s.return_1m },
  { key: "ytd", label: "This year", of: (s: Snapshot) => s.return_ytd },
  { key: "1y", label: "1 year", of: (s: Snapshot) => s.return_1y },
] as const;
export type Span = (typeof SPANS)[number];

// The half-width of the ruler over a span longer than the day: a round figure that holds all the
// moves but the two largest, so that an outlier or two do not flatten every other mark.
function spanScale(moves: number[]): number {
  const sizes = moves.map(Math.abs).sort((a, b) => b - a);
  const hold = sizes[Math.min(2, sizes.length - 1)] ?? 0;
  return [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1].find((s) => s >= hold) ?? Math.ceil(hold);
}
const scaleEnd = (scale: number) => `${(scale * 100).toFixed((scale * 100) % 1 ? 1 : 0)}%`;

export type Ends = { top: Snapshot | null; bottom: Snapshot | null; of: Span["of"] };

// Every instrument of the overview on one ruler. show() moves all the marks to a span's figures
// and says which instruments are at its two ends.
export function liveRuler(o: Overview): { el: HTMLElement; show(span: Span): Ends } {
  const el = h("div", "ruler");
  const axis = [h("span"), h("span", "", "0"), h("span")];
  add(el, add(h("div", "ruler-row !py-0"), h("span"), h("span", "hidden sm:block"), add(h("div", "ruler-axis"), ...axis), h("span")));
  const charted = [...o.indices, ...o.commodities, ...o.currencies, ...o.crypto];
  const rows: { s: Snapshot; m: Mark | null; fig: HTMLElement; live: boolean }[] = [];
  let span: Span = SPANS[0], scale = 0.01;

  const set = (r: (typeof rows)[number]) => {
    if (r.s.kind === "rate") {
      // A yield moves in basis points, not in percent of itself: it has its figure for the day and no mark.
      const day = span.key === "day";
      r.fig.textContent = day ? rateItem(r.s).text! : "—";
      r.fig.className = `num text-right text-[13px] ${day ? toneClass(r.s.change) : "text-muted"}`;
      return;
    }
    const v = span.of(r.s);
    r.fig.textContent = signedPct(v, span.key === "day" ? 2 : 1);
    r.fig.className = `num text-right text-[13px] ${toneClass(v)}`;
    if (r.live) r.m!.set(v, scale);
  };

  const group = (title: string, items: Snapshot[]) => {
    if (!items.length) return;
    const head = rv(h("div", "ruler-group", title));
    el.append(head);
    const mine = items.map((s, i) => {
      const rate = s.kind === "rate";
      const row = rv(rate ? h("div", "ruler-row") : linkTo(quoteHref(s.symbol), "ruler-row"), i + 1);
      const r = { s, m: rate ? null : mark(), fig: h("span"), live: false };
      add(row,
        add(h("span", "min-w-0"), h("span", "block truncate text-ink-strong", s.name), h("span", "num block text-[12.5px] text-muted sm:hidden", level(s.price, s.kind))),
        h("span", "num hidden text-right text-[13px] text-ink sm:block", level(s.price, s.kind)),
        r.m?.el ?? h("span", "track"), r.fig);
      el.append(row);
      rows.push(r);
      return r;
    });
    // The marks of a group leave zero one after another, once the group is on screen.
    reached(head, () => mine.forEach((r, i) => setTimeout(() => ((r.live = true), set(r)), still() ? 0 : 150 + i * 55)));
  };
  group("Stock indices", o.indices);
  group("Treasury yields", o.rates);
  group("Commodities", o.commodities);
  group("Currencies", o.currencies);
  group("Crypto", o.crypto);

  function show(next: Span): Ends {
    span = next;
    const moves = charted.map(span.of).filter(isNum);
    scale = span.key === "day" ? rulerScale(moves) : spanScale(moves);
    axis[0].textContent = `−${scaleEnd(scale)}`;
    axis[2].textContent = `+${scaleEnd(scale)}`;
    rows.forEach(set);
    const ranked = charted.filter((s) => isNum(span.of(s))).sort((a, b) => span.of(b)! - span.of(a)!);
    return { top: ranked[0] ?? null, bottom: ranked[ranked.length - 1] ?? null, of: span.of };
  }
  show(span);
  return { el, show };
}

// --- The widest moves ---------------------------------------------------------------------------

// The largest falls and the largest rises of the day, each as a bar from the same line: falls to
// its left, rises to its right, on one scale. On a narrow screen they are two lists, rises first.
export function tug(losers: Mover[], gainers: Mover[]): HTMLElement {
  const most = Math.max(0.0001, ...[...losers, ...gainers].map((m) => Math.abs(m.change_pct)));
  const side = (title: string, items: Mover[], cls: string) =>
    add(h("div", `movers ${cls}`), h("h3", "movers-title", title), ...items.map((m, i) => {
      const row = rv(linkTo(quoteHref(m.symbol), "mover"), i);
      const bar = h("span", "mover-bar");
      bar.style.setProperty("--w", (Math.abs(m.change_pct) / most).toFixed(4));
      const fig = h("span", `num flex-none text-[13px] ${toneClass(m.change_pct)}`, signedPct(0, 2));
      reached(row, () => count(fig, 0, m.change_pct, (v) => signedPct(v, 2), 900 + i * 70));
      return add(row,
        add(h("span", "mover-name"), h("span", "num block text-ink-strong", m.symbol), h("span", "block truncate text-[12.5px] text-muted", m.name)),
        add(h("span", "mover-zone"), bar, fig));
    }));
  return add(h("div", "tug"), side("Largest rises", gainers, "rises"), side("Largest falls", losers, "falls"));
}

// The most traded stocks of the day, each with its volume as a bar on the same scale.
export function traded(items: Mover[]): HTMLElement {
  const most = Math.max(1, ...items.map((m) => m.volume ?? 0));
  return add(h("div", "grid grid-cols-2 gap-x-8 gap-y-6 md:grid-cols-3 xl:grid-cols-6"), ...items.map((m, i) => {
    const bar = h("span", "volume-bar");
    bar.style.setProperty("--w", ((m.volume ?? 0) / most).toFixed(4));
    return add(rv(linkTo(quoteHref(m.symbol), "group block min-w-0"), i),
      add(h("span", "flex items-baseline justify-between gap-2"), h("span", "num text-ink-strong group-hover:underline", m.symbol),
        h("span", `num text-[13px] ${toneClass(m.change_pct)}`, signedPct(m.change_pct, 2))),
      h("span", "block truncate text-[12.5px] text-muted", m.name),
      add(h("span", "mt-2 block h-[3px] bg-line"), bar),
      h("span", "num mt-1.5 block text-[12.5px] text-ink", isNum(m.volume) ? `${compact(m.volume)} shares` : "—"));
  }));
}
