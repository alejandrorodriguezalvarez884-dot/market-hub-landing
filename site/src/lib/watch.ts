// The watchlist page: what /api/watchlist returns (see src/markethub/watch.py) and the pieces that
// draw it. A stock's reading is a set of gauges, one per aspect (how far the price is from its
// average, its trend, its strength against the index...), each with a sentence under it; the
// whole list is a map with a dot per stock.
import { api } from "./api";
import { add, h, linkTo, svg } from "./dom";
import { pct, price, shortDate, signedPct } from "./format";
import { cell, moveCell, points, tone } from "./hub";
import { link, tidyName } from "./site";
import { sparkline } from "./spark";
import { AVERAGES } from "./watchcharts";
import { track } from "./widgets";

type N = number | null;
export type Span = "1m" | "3m" | "6m" | "12m";
export type Against = { gaps: Record<Span, N>; returns: Record<Span, N>; state: "ahead" | "fading" | "gaining" | "behind"; line: number[];
  high_sessions: N; low_sessions: N };
export type Reading = {
  as_of: string; price: number; day_change_pct: N; daily_range_pct: N;
  extension: { pct: number; ranges: N; state: "extended_above" | "above" | "at" | "below" | "extended_below"; percentile: N; sessions: N;
    band: [number, number] | null; low: number; high: number; pct_200: N } | null;
  trend: { sma20: N; sma50: number; sma200: N; slope_50: N; slope_200: N; state: "up" | "pullback" | "down" | "rebound" | "mixed" } | null;
  momentum: { rsi: N; returns: Record<"1w" | Span, N> };
  range: { low: number; high: number; position: N; from_high: number; from_low: N; sessions_since_high: number };
  volume: { average: number; week_ratio: number; up_down: N } | null;
  volatility: N; strength: Against | null; spark: number[];
};
export type Aspect = "extension" | "trend" | "strength" | "sector" | "momentum" | "range" | "volume" | "growth" | "valuation";
// A stock in sentences: by the code at once, by the model when it answers.
export type Analysis = { headline: string; points: { aspect: Aspect; text: string }[]; contrast: string; written: boolean };
export type Item = {
  ticker: string; name: string; kind: "stock" | "fund"; sector: string | null; industry: string | null; reading: Reading | null;
  sector_strength: { name: string; fund: string; against_market: Against | null; stock: Against | null } | null;
  valuation: { pe: N; forward_pe: N; market_cap: N; days_to_results: N } | null;
  analysis: Analysis;
};
export type Board = { sample: boolean; as_of: string; benchmark: { ticker: string; name: string }; watchlist: string[]; positions: string[]; items: Item[] };
type Growing = { quarter?: number; year?: number; next_year?: number };
export type Growth = { eps?: Growing; revenue?: Growing; analysts: N };
export type Read = { sample: boolean; ticker: string; growth: Growth | null; captions: Analysis; analysis: Analysis | null };
export type Bars = { sample: boolean; ticker: string; time: string[]; open: number[]; high: number[]; low: number[]; close: number[]; volume: number[] };

export const getBoard = () => api<Board>("/api/watchlist");
export const getStock = (t: string) => api<{ sample: boolean; item: Item }>(`/api/watchlist/stock?t=${encodeURIComponent(t)}`);
// A stock's bars and its reading are asked for once a visit, however many times they are drawn.
function once<T>(path: string): (t: string) => Promise<T> {
  const asked = new Map<string, Promise<T>>();
  return (t) => {
    if (!asked.has(t)) asked.set(t, api<T>(`${path}?t=${encodeURIComponent(t)}`).catch((e) => (asked.delete(t), Promise.reject(e))));
    return asked.get(t)!;
  };
}
export const getBars = once<Bars>("/api/watchlist/bars");
export const getRead = once<Read>("/api/watchlist/read");

export const EXTENSION = { extended_above: "Extended above", above: "Above its average", at: "At its average", below: "Below its average", extended_below: "Extended below" };
export const TREND = { up: "Uptrend", pullback: "Pullback in an uptrend", down: "Downtrend", rebound: "Rebound in a downtrend", mixed: "No clear trend" };
export const STRENGTH = { ahead: "Ahead", fading: "Ahead, losing ground", gaining: "Behind, gaining ground", behind: "Behind" };
const SPANS: [Span, string][] = [["1m", "1 month"], ["3m", "3 months"], ["6m", "6 months"], ["12m", "12 months"]];
export const quoteHref = (t: string) => link(`/quote/?t=${encodeURIComponent(t)}`);

// --- Marks -------------------------------------------------------------------------------------

// A horizontal scale: marks placed at fractions of its width.
function scale(marks: (HTMLElement | null)[], cls = ""): HTMLElement {
  const el = h("div", `wl-scale ${cls}`);
  el.setAttribute("aria-hidden", "true");
  return add(el, ...marks);
}
const place = <T extends HTMLElement>(el: T, x: number) => ((el.style.left = `${Math.max(0, Math.min(1, x)) * 100}%`), el);
const dot = (x: number, cls = "", hollow = false) => place(h("span", `wl-dot ${cls} ${hollow ? "wl-hollow" : ""}`), x);
const tick = (x: number, color?: string) => {
  const el = place(h("span", "wl-tick"), x);
  if (color) el.style.background = color;
  return el;
};
function band(from: number, to: number): HTMLElement {
  const el = place(h("span", "wl-band"), from);
  el.style.width = `${Math.max(0, Math.min(1, to) - Math.max(0, from)) * 100}%`;
  return el;
}
// Labels along a scale. Two that would sit on each other are moved apart.
function labels(items: { x: number; text: string; color?: string }[], cls = ""): HTMLElement {
  let last = -1;
  return add(h("div", `relative h-4 ${cls}`), ...[...items].sort((a, b) => a.x - b.x).map((item) => {
    const x = (last = Math.min(0.97, Math.max(item.x, last + 0.1, 0.03)));
    const el = place(h("span", "num absolute -translate-x-1/2 whitespace-nowrap text-[11px] text-muted", item.text), x);
    if (item.color) el.style.color = item.color;
    return el;
  }));
}
// A figure with what it is under it.
const fig = (value: string, label: string, cls = "text-ink-strong") => add(h("div", "min-w-0"),
  h("div", `num text-[15px] leading-tight ${cls}`, value), h("div", "mt-0.5 text-[11.5px] leading-snug text-muted", label));
const figs = (...items: (HTMLElement | null)[]) => add(h("div", "flex flex-wrap gap-x-6 gap-y-2"), ...items);
const ends = (left: string, right: string, middle?: HTMLElement | null) => add(h("div", "mt-1 flex items-center justify-between gap-2 text-[11px] text-faint"),
  h("span", "num", left), middle ?? null, h("span", "num", right));
const key = (mark: string, text: string) => add(h("span", "inline-flex items-center gap-1"), h("span", mark), text);

// Rows of moves on one ruler: zero in the middle, the same scale for every cell.
function ruler(rows: { label: string; cells: (number | null | undefined)[] }[], heads: string[] | null, say: (v: N | undefined) => string): HTMLElement | null {
  rows = rows.filter((r) => r.cells.some((c) => c != null));
  if (!rows.length) return null;
  const width = Math.max(0.05, ...rows.flatMap((r) => r.cells.map((c) => Math.abs(c ?? 0))));
  const el = h("div", "grid items-center gap-x-3 gap-y-0.5 text-[12.5px]");
  el.style.gridTemplateColumns = `4.4rem repeat(${rows[0].cells.length}, minmax(0, 1fr))`;
  if (heads) add(el, h("span"), ...heads.map((t) => h("span", "pb-1 text-[11.5px] text-muted", t)));
  for (const r of rows) {
    add(el, h("span", "text-muted", r.label), ...r.cells.map((c) => {
      const slot = add(h("span", "min-w-0 flex-1"), track(c, width));
      slot.style.setProperty("--track", "100%");
      return add(h("span", "flex min-w-0 items-center gap-2"), slot, h("span", `num w-[4.6rem] flex-none text-right ${tone(c)}`, say(c)));
    }));
  }
  return el;
}
const inPoints = (v: N | undefined) => points(v).replace(" pts", "");

// --- The gauges, one per aspect ----------------------------------------------------------------

// The gap to the 50-day average, on the scale of this stock's own gaps: the band is where it
// usually stands, so a dot outside it is a price that is extended.
function extensionGauge(r: Reading): HTMLElement | null {
  const e = r.extension;
  if (!e) return null;
  const lo = Math.min(e.low, 0), hi = Math.max(e.high, 0), pad = (hi - lo) * 0.04 || 0.01;
  const x = (v: number) => (v - lo + pad) / (hi - lo + 2 * pad);
  return add(h("div"),
    figs(fig(signedPct(e.pct), "from its 50-day average", tone(e.pct)),
      e.ranges != null ? fig(`${Math.abs(e.ranges).toFixed(1)}×`, "its daily range") : null,
      e.percentile != null ? fig(pct(e.percentile, 0), `of ${e.sessions} sessions stood lower against it`) : null),
    scale([e.band ? band(x(e.band[0]), x(e.band[1])) : null, tick(x(0), AVERAGES[1].color), dot(x(e.pct), tone(e.pct), e.state.startsWith("extended"))], "mt-3"),
    ends(signedPct(e.low, 0), signedPct(e.high, 0), add(h("span", "flex flex-wrap justify-center gap-x-3"),
      e.band ? key("wl-key-band", "usual range") : null, key("wl-key-tick", "50-day average"))));
}

// The price and its three averages on one line of prices: their order is the trend.
function trendLadder(r: Reading): HTMLElement | null {
  const t = r.trend;
  if (!t) return null;
  type Mark = { v: number; a: (typeof AVERAGES)[number] };
  const marks = [{ v: t.sma200, a: AVERAGES[2] }, { v: t.sma50, a: AVERAGES[1] }, { v: t.sma20, a: AVERAGES[0] }].filter((m) => m.v != null) as Mark[];
  const all = [...marks.map((m) => m.v), r.price];
  const lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo) * 0.14 || hi * 0.01;
  const x = (v: number) => (v - lo + pad) / (hi - lo + 2 * pad);
  const slope = (name: string, v: N) => (v == null ? null : add(h("span", "whitespace-nowrap"), `${name} `, h("span", `num ${tone(v)}`, `${v > 0.001 ? "↗" : v < -0.001 ? "↘" : "→"} ${signedPct(v)}`)));
  return add(h("div"),
    labels(marks.map((m) => ({ x: x(m.v), text: String(m.a.sessions), color: m.a.color }))),
    scale([...marks.map((m) => tick(x(m.v), m.a.color)), dot(x(r.price))]),
    labels([{ x: x(r.price), text: price(r.price) }], "mt-0.5 [&>span]:text-ink-strong"),
    add(h("div", "mt-2 flex flex-wrap gap-x-4 gap-y-0.5 text-[12px] text-muted"), slope("50-day, in a month", t.slope_50), slope("200-day", t.slope_200)));
}

function strengthGauge(r: Reading, index: string): HTMLElement | null {
  const s = r.strength;
  if (!s) return null;
  const extreme = s.high_sessions ? `highest in ${s.high_sessions} sessions` : s.low_sessions ? `lowest in ${s.low_sessions} sessions` : null;
  return add(h("div"),
    ruler(SPANS.map(([k, label]) => ({ label, cells: [s.gaps[k]] })), null, inPoints),
    add(h("div", "mt-2.5 flex items-center gap-3 text-[12px] text-muted"), sparkline(s.line, 112, 26),
      add(h("span", "min-w-0"), `Its price over the ${index}'s, six months`, extreme ? h("span", "block text-ink", `At its ${extreme}`) : null)));
}

function sectorGauge(item: Item): HTMLElement | null {
  const s = item.sector_strength;
  if (!s?.against_market) return null;
  return ruler(SPANS.map(([k, label]) => ({ label, cells: [s.against_market!.gaps[k], s.stock?.gaps[k]] })), ["Sector vs index", `${item.ticker} vs sector`], inPoints);
}

function momentumGauge(r: Reading): HTMLElement | null {
  const m = r.momentum;
  if (m.rsi == null) return null;
  const back: [keyof typeof m.returns, string][] = [["1w", "1W"], ["1m", "1M"], ["3m", "3M"], ["6m", "6M"], ["12m", "12M"]];
  return add(h("div"),
    add(h("div", "flex items-baseline gap-2"), h("span", "num text-[15px] text-ink-strong", m.rsi.toFixed(0)), h("span", "text-[11.5px] text-muted", "RSI, 14 sessions")),
    scale([band(0.3, 0.7), dot(m.rsi / 100)], "mt-2"),
    labels([{ x: 0, text: "0" }, { x: 0.3, text: "30" }, { x: 0.7, text: "70" }, { x: 1, text: "100" }], "mt-0.5 [&>span]:text-faint"),
    add(h("div", "mt-2.5 grid grid-cols-5 gap-px overflow-hidden rounded-sm bg-line"), ...back.map(([k, label]) =>
      add(h("div", "bg-page px-1 py-1 text-center"), h("div", "text-[11px] text-muted", label), h("div", `num text-[12px] ${tone(m.returns[k])}`, signedPct(m.returns[k], 0))))));
}

function rangeGauge(r: Reading): HTMLElement | null {
  const g = r.range;
  if (g.position == null) return null;
  return add(h("div"),
    figs(fig(signedPct(g.from_high), "from its 52-week high"), fig(String(g.sessions_since_high), "sessions since that high"), fig(signedPct(g.from_low, 0), "from its low")),
    scale([dot(g.position)], "mt-3"), ends(price(g.low), price(g.high)));
}

function volumeGauge(r: Reading): HTMLElement | null {
  const v = r.volume;
  if (!v) return null;
  const share = v.up_down == null ? null : v.up_down / (1 + v.up_down);
  const split = h("div", "mt-3 flex h-[5px] gap-px overflow-hidden rounded-full");
  if (share != null) {
    const up = h("span", "block bg-up"), down = h("span", "block flex-1 bg-down");
    up.style.width = `${share * 100}%`;
    add(split, up, down);
  }
  return add(h("div"),
    figs(fig(`${v.week_ratio.toFixed(2)}×`, "last 5 sessions, against the 50-day average"),
      v.up_down != null ? fig(`${v.up_down.toFixed(2)}×`, "traded on up days per share on down days") : null),
    scale([tick(0.5), dot(Math.min(v.week_ratio, 2) / 2)], "mt-3"), ends("0", "2×", h("span", "", "average")),
    share != null ? split : null);
}

function growthGauge(g: Growth): HTMLElement | null {
  return ruler([{ label: "Earnings", cells: [g.eps?.year, g.eps?.next_year] }, { label: "Revenue", cells: [g.revenue?.year, g.revenue?.next_year] }],
    ["This fiscal year", "Next fiscal year"], (v) => signedPct(v));
}

function valuationGauge(item: Item): HTMLElement | null {
  const v = item.valuation;
  if (!v || (v.pe == null && v.forward_pe == null && v.days_to_results == null)) return null;
  return figs(v.pe != null ? fig(`${v.pe.toFixed(1)}×`, "its earnings of the last 12 months") : null,
    v.forward_pe != null ? fig(`${v.forward_pe.toFixed(1)}×`, "the estimate for next year") : null,
    v.days_to_results != null ? fig(v.days_to_results ? `${v.days_to_results} days` : "Today", "to its next results") : null);
}

// --- A stock's reading -------------------------------------------------------------------------

function block(aspect: Aspect, title: string, state: string | null | undefined, gauge: HTMLElement | null): HTMLElement | null {
  if (!gauge) return null;
  const say = h("p", "wl-say");
  say.dataset.say = aspect;
  const el = add(h("section", "wl-aspect"),
    add(h("header", "mb-3 flex items-baseline justify-between gap-3"), h("h4", "label", title), state ? h("span", "wl-state", state) : null), gauge, say);
  el.dataset.aspect = aspect;
  return el;
}

// What a stock is doing at a glance: a few words per aspect, for the head of its chart.
export function stateMarks(item: Item): HTMLElement[] {
  const r = item.reading;
  if (!r) return [];
  const mark = (text: string, figure?: string, cls = "") => add(h("span", "wl-state"), text, figure ? h("span", `num ml-1 ${cls}`, figure) : null);
  return [
    r.extension ? mark(EXTENSION[r.extension.state].replace(" its average", " 50-day"), signedPct(r.extension.pct, 0), tone(r.extension.pct)) : null,
    r.trend ? mark(TREND[r.trend.state]) : null,
    r.strength?.gaps["3m"] != null ? mark("vs S&P 500, 3M", inPoints(r.strength.gaps["3m"]), tone(r.strength.gaps["3m"])) : null,
  ].filter((x): x is HTMLElement => !!x);
}

export function stockHead(item: Item, cls = ""): HTMLElement {
  const r = item.reading;
  return add(h("div", `flex min-w-0 items-baseline gap-2 ${cls}`),
    linkTo(quoteHref(item.ticker), "flex-none font-semibold text-ink-strong hover:underline", item.ticker),
    h("span", "min-w-0 flex-1 truncate text-[12.5px] text-muted", tidyName(item.name)),
    r ? h("span", "num flex-none text-[13px] text-ink-strong", price(r.price)) : null,
    r ? h("span", `num flex-none text-[13px] ${tone(r.day_change_pct)}`, signedPct(r.day_change_pct, 2)) : null);
}

export type Card = { el: HTMLElement; load(): void };

// The reading of one stock: its sentence, and a gauge per aspect with what it shows under it.
// Drawn at once from the figures; `load` then asks for what analysts estimate and for the fuller
// reading, and puts them in.
export function readingCard(item: Item, index: string): Card {
  const r = item.reading;
  if (!r) return { el: add(h("div", "wl-card"), h("p", "text-[13px] text-muted", `No prices for ${item.ticker} right now.`)), load() {} };
  const headline = h("p", "wl-headline");
  const contrast = add(h("p", "wl-contrast"), add(svg("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": 1.6, "stroke-linecap": "round",
    "stroke-linejoin": "round", "aria-hidden": "true", class: "mt-0.5 h-4 w-4 flex-none text-muted" }), svg("path", { d: "M7 7h13m0 0-3-3m3 3-3 3M17 17H4m0 0 3-3m-3 3 3 3" })), h("span"));
  contrast.hidden = true;
  const growth = h("div", "contents");
  const grid = add(h("div", "wl-aspects"),
    block("extension", "Price and its 50-day average", r.extension && EXTENSION[r.extension.state], extensionGauge(r)),
    block("trend", "Trend", r.trend && TREND[r.trend.state], trendLadder(r)),
    block("strength", `Against the ${index}, in points`, r.strength && STRENGTH[r.strength.state], strengthGauge(r, index)),
    block("sector", item.sector_strength ? `Sector: ${item.sector_strength.name}` : "Sector", item.sector_strength?.against_market && STRENGTH[item.sector_strength.against_market.state], sectorGauge(item)),
    block("momentum", "Momentum", null, momentumGauge(r)),
    block("range", "52-week range", null, rangeGauge(r)),
    block("volume", "Volume", null, volumeGauge(r)),
    growth,
    block("valuation", "Price to earnings", null, valuationGauge(item)));
  const el = add(h("div", "wl-card"), headline, contrast, grid);

  // The model's sentence for an aspect where it wrote one; the code's otherwise.
  function say(first: Analysis | null, second: Analysis) {
    headline.textContent = first?.headline || second.headline;
    for (const p of el.querySelectorAll<HTMLElement>("[data-say]")) {
      const of = (a: Analysis | null) => a?.points.find((x) => x.aspect === p.dataset.say)?.text;
      p.textContent = of(first) ?? of(second) ?? "";
      p.hidden = !p.textContent;
    }
    (contrast.lastChild as HTMLElement).textContent = first?.contrast ?? "";
    contrast.hidden = !first?.contrast;
  }
  say(null, item.analysis);

  let asked = false;
  return {
    el,
    load() {
      if (asked) return;
      asked = true;
      getRead(item.ticker)
        .then((read) => {
          const g = read.growth && block("growth", "Growth, by analysts' consensus", read.growth.analysts ? `${read.growth.analysts} analysts` : null, growthGauge(read.growth));
          if (g) growth.replaceChildren(g);
          if (!read.analysis) return say(null, read.captions);
          el.style.opacity = "0";
          setTimeout(() => (say(read.analysis, read.captions), (el.style.opacity = "1")), 260);
        })
        .catch(() => {});
    },
  };
}

// --- The whole list at once --------------------------------------------------------------------

type Placed = { item: Item; x: number; y: number };

// Every stock as a dot: across, how far its price is from its 50-day average, in daily ranges;
// up, how many points it is ahead of the index over three months. A ring marks a price that is
// extended by the stock's own standard.
export function listMap(items: Item[], index: string, onPick: (item: Item) => void): HTMLElement {
  const placed: Placed[] = [], off: string[] = [];
  for (const item of items) {
    const x = item.reading?.extension?.ranges, y = item.reading?.strength?.gaps["3m"];
    if (x == null || y == null) off.push(item.ticker);
    else placed.push({ item, x, y });
  }
  const host = h("div", "wl-map");
  const ringed = placed.some((p) => p.item.reading!.extension!.state.startsWith("extended"));
  const note = add(h("p", "mt-1 flex flex-wrap items-center gap-x-5 gap-y-1 text-[12px] text-muted"),
    ringed ? add(h("span", "inline-flex items-center gap-1.5"), h("span", "inline-block h-3 w-3 rounded-full border border-ink-strong"), "Extended from its 50-day average") : null,
    off.length ? h("span", "", `Not on the map: ${off.join(", ")}.`) : null);
  const el = add(h("div"), host, note);
  if (!placed.length) return (host.append(h("p", "py-10 text-center text-[13px] text-muted", "Nothing to place on the map yet.")), el);
  const across = Math.min(8, Math.max(3, Math.ceil(Math.max(...placed.map((p) => Math.abs(p.x))))));
  const up = Math.min(0.6, Math.max(0.1, Math.ceil(Math.max(...placed.map((p) => Math.abs(p.y))) / 0.05) * 0.05));

  function draw(width: number) {
    const W = Math.max(300, Math.round(width)), H = Math.round(Math.min(560, Math.max(320, W * 0.5)));
    const m = { l: 44, r: 16, t: 28, b: 46 };
    const px = (v: number) => m.l + ((Math.max(-across, Math.min(across, v)) + across) / (2 * across)) * (W - m.l - m.r);
    const py = (v: number) => m.t + (1 - (Math.max(-up, Math.min(up, v)) + up) / (2 * up)) * (H - m.t - m.b);
    const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "group", "aria-label": "The stocks by their gap to the 50-day average and their gap to the index" });
    const text = (x: number, y: number, t: string, cls: string, anchor = "start") => {
      const e = svg("text", { x, y, "text-anchor": anchor, class: cls });
      e.textContent = t;
      return e;
    };
    for (let i = -across; i <= across; i++) {
      if (i) s.append(svg("line", { x1: px(i), x2: px(i), y1: m.t, y2: H - m.b, class: "stroke-line", "stroke-dasharray": "2 4" }));
      if (!(i % (across > 5 ? 2 : 1))) s.append(text(px(i), H - m.b + 14, i > 0 ? `+${i}` : String(i).replace("-", "−"), "num fill-faint text-[11px]", "middle"));
    }
    for (const v of [-up, -up / 2, up / 2, up]) {
      s.append(svg("line", { x1: m.l, x2: W - m.r, y1: py(v), y2: py(v), class: "stroke-line", "stroke-dasharray": "2 4" }));
      s.append(text(m.l - 6, py(v) + 4, `${v > 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(0)}`, "num fill-faint text-[11px]", "end"));
    }
    s.append(svg("line", { x1: px(0), x2: px(0), y1: m.t, y2: H - m.b, class: "stroke-line-strong" }), svg("line", { x1: m.l, x2: W - m.r, y1: py(0), y2: py(0), class: "stroke-line-strong" }));
    s.append(text(m.l, m.t - 12, `Points against the ${index}, 3 months`, "fill-muted text-[11.5px]"),
      text((m.l + W - m.r) / 2, H - 8, "Daily ranges from the 50-day average", "fill-muted text-[11.5px]", "middle"));
    // Those nearest the middle are drawn last, so their names are not covered.
    for (const p of [...placed].sort((a, b) => Math.hypot(b.x / across, b.y / up) - Math.hypot(a.x / across, a.y / up))) {
      const cx = px(p.x), cy = py(p.y), left = cx > W - 70;
      const e = p.item.reading!.extension!;
      const g = svg("g", { class: "wl-map-dot", tabindex: 0, role: "button", "aria-label": `${p.item.ticker}: ${EXTENSION[e.state]}, ${points(p.y)} against the index` });
      const tip = svg("title");
      tip.textContent = `${tidyName(p.item.name)} · ${signedPct(e.pct)} from its 50-day average (${p.x.toFixed(1)} daily ranges) · ${points(p.y)} against the ${index} over 3 months`;
      g.append(tip);
      if (e.state.startsWith("extended")) g.append(svg("circle", { cx, cy, r: 10, class: "fill-none stroke-ink-strong", "stroke-width": 1 }));
      g.append(svg("circle", { cx, cy, r: 5, class: "fill-ink-strong" }), text(cx + (left ? -13 : 13), cy + 4, p.item.ticker, "num fill-ink text-[12px]", left ? "end" : "start"));
      g.addEventListener("click", () => onPick(p.item));
      g.addEventListener("keydown", (ev) => (ev.key === "Enter" || ev.key === " ") && (ev.preventDefault(), onPick(p.item)));
      s.append(g);
    }
    host.replaceChildren(s);
  }
  // Drawn to the width it is given, once it is in the page, and again whenever that width changes.
  let drawn = 0;
  const fit = () => {
    const width = Math.round(host.clientWidth);
    if (width && width !== drawn) draw((drawn = width));
  };
  queueMicrotask(fit);
  new ResizeObserver(fit).observe(host);
  return el;
}

type Column = { head: string; value: (i: Item) => number | string | null | undefined; draw: (i: Item) => HTMLElement };

// The same stocks as a table: press a column's name to order by it, a row to open its reading.
export function listTable(items: Item[], onPick: (item: Item) => void): HTMLElement {
  const read = items.filter((i) => i.reading);
  const ranges = Math.max(2, ...read.map((i) => Math.abs(i.reading!.extension?.ranges ?? 0)));
  const gaps = Math.max(0.05, ...read.map((i) => Math.abs(i.reading!.strength?.gaps["3m"] ?? 0)));
  const tracked = (v: N | undefined, width: number, text: string) => add(h("td", "whitespace-nowrap"),
    add(h("span", "mr-2 inline-block w-[84px] align-middle [--track:84px]"), track(v == null ? null : v / width, 1)), h("span", `num ${tone(v)}`, text));
  const columns: Column[] = [
    { head: "Stock", value: (i) => i.ticker, draw: (i) => add(h("td"), h("span", "font-semibold text-ink-strong", i.ticker), h("div", "max-w-[11rem] truncate text-[11px] text-muted", tidyName(i.name))) },
    { head: "Price", value: (i) => i.reading!.price, draw: (i) => cell(price(i.reading!.price), "num text-ink-strong") },
    { head: "Today", value: (i) => i.reading!.day_change_pct, draw: (i) => moveCell(i.reading!.day_change_pct, 2) },
    { head: "From its 50-day average", value: (i) => i.reading!.extension?.ranges, draw: (i) => tracked(i.reading!.extension?.ranges, ranges, signedPct(i.reading!.extension?.pct)) },
    { head: "", value: (i) => i.reading!.extension?.state, draw: (i) => cell(i.reading!.extension ? EXTENSION[i.reading!.extension.state] : "—", "!text-left !font-sans text-muted") },
    { head: "Trend", value: (i) => i.reading!.trend?.state, draw: (i) => cell(i.reading!.trend ? TREND[i.reading!.trend.state] : "—", "!font-sans text-muted") },
    { head: "vs S&P 500, 3 months", value: (i) => i.reading!.strength?.gaps["3m"], draw: (i) => tracked(i.reading!.strength?.gaps["3m"], gaps, points(i.reading!.strength?.gaps["3m"])) },
    { head: "Sector vs S&P 500", value: (i) => i.sector_strength?.against_market?.gaps["3m"], draw: (i) => cell(points(i.sector_strength?.against_market?.gaps["3m"]), `num ${tone(i.sector_strength?.against_market?.gaps["3m"])}`) },
    { head: "RSI", value: (i) => i.reading!.momentum.rsi, draw: (i) => cell(i.reading!.momentum.rsi?.toFixed(0) ?? "—", "num") },
    { head: "From 52-week high", value: (i) => i.reading!.range.from_high, draw: (i) => cell(signedPct(i.reading!.range.from_high), "num text-muted") },
  ];
  const table = h("table", "data-table"), body = h("tbody");
  let by = 6, down = true;
  const heads = columns.map((col, n) => {
    const b = h("button", "hover:text-ink-strong", col.head);
    b.type = "button";
    b.addEventListener("click", () => {
      down = by === n ? !down : n !== 0 && n !== 4 && n !== 5;
      by = n;
      fill();
    });
    return add(h("th", n === 4 ? "!text-left" : ""), col.head ? b : null);
  });
  const fill = () => {
    heads.forEach((x, n) => x.setAttribute("aria-sort", n === by ? (down ? "descending" : "ascending") : "none"));
    heads.forEach((x, n) => x.firstChild && ((x.firstChild as HTMLElement).className = n === by ? "text-ink-strong underline decoration-line-strong underline-offset-4" : "hover:text-ink-strong"));
    const value = columns[by].value;
    const sorted = [...read].sort((a, b) => {
      const [x, y] = [value(a), value(b)];
      if (x == null || y == null) return x == null ? (y == null ? 0 : 1) : -1; // what is not known goes last
      const order = typeof x === "string" ? x.localeCompare(String(y)) : x - (y as number);
      return down ? -order : order;
    });
    body.replaceChildren(...sorted.map((item) => {
      const tr = add(h("tr", "row-link"), ...columns.map((col) => col.draw(item)));
      tr.addEventListener("click", () => onPick(item));
      return tr;
    }));
  };
  add(table, add(h("thead"), add(h("tr"), ...heads)), body);
  fill();
  return add(h("div", "overflow-x-auto"), table);
}

export const asOf = (b: Board) => `Prices of ${shortDate(b.as_of)}`;
