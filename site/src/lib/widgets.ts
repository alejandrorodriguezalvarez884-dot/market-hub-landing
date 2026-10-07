// Pieces shared by the public pages: the ruler (every move on one scale) and the tables.
import { add, h, linkTo } from "./dom";
import { change, level, signedPct, toneClass } from "./format";
import type { Mover, Overview, Sector, Snapshot } from "./market";
import { link } from "./site";
import { sparkline } from "./spark";

export const quoteHref = (symbol: string) => link(`/quote/?t=${encodeURIComponent(symbol)}`);

export function pill(v: number | null | undefined, digits = 2): HTMLElement {
  return h("span", typeof v === "number" && v < 0 ? "pill-down" : "pill-up", signedPct(v, digits));
}

// --- The ruler ---------------------------------------------------------------------------------

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

// The half-width of a ruler, as a fraction: the largest move, rounded up to half a percent,
// between ±1% and ±4%. A move beyond it is drawn at the edge, so one outlier does not flatten
// every other mark.
export function rulerScale(moves: (number | null | undefined)[]): number {
  const max = Math.max(0, ...moves.filter(isNum).map(Math.abs));
  return Math.min(0.04, Math.max(0.01, Math.ceil(max / 0.005 - 1e-9) * 0.005));
}

// One mark on the ruler: a stem from zero and a dot at the move.
export function track(move: number | null | undefined, scale: number): HTMLElement {
  const el = h("div", "track");
  el.setAttribute("aria-hidden", "true");
  if (!isNum(move)) return el;
  const off = Math.abs(move) > scale;
  const reach = Math.min(1, Math.abs(move) / scale) * 50; // % of the track, from the middle
  const tone = move > 0 ? "up" : move < 0 ? "down" : "";
  const fill = tone === "up" ? "bg-up" : tone === "down" ? "bg-down" : "bg-muted";
  const stem = h("span", `track-stem ${fill}`);
  stem.style.width = `${reach}%`;
  stem.style[move < 0 ? "right" : "left"] = "50%";
  const dot = h("span", `track-dot ${fill} ${tone} ${off ? "off" : ""}`);
  dot.style.left = `${50 + (move < 0 ? -reach : reach)}%`;
  return add(el, stem, dot);
}

// The scale's ends and its zero, to sit above a column of tracks.
export function rulerAxis(scale: number): HTMLElement {
  const end = `${(scale * 100).toFixed(scale * 100 % 1 ? 1 : 0)}%`;
  return add(h("div", "ruler-axis"), h("span", "", `−${end}`), h("span", "", "0"), h("span", "", `+${end}`));
}

export type RulerItem = {
  name: string;
  value?: string; // the level, in its own unit
  move: number | null | undefined; // the day's move as a fraction: its place on the ruler
  text?: string; // what to print instead of the percentage (basis points for a yield)
  onPick?: () => void;
  href?: string;
  key?: string;
};

export function rulerRow(item: RulerItem, scale: number): HTMLElement {
  const el = item.onPick ? h("button", "ruler-row") : item.href ? linkTo(item.href, "ruler-row") : h("div", "ruler-row");
  if (item.onPick) {
    (el as HTMLButtonElement).type = "button";
    el.setAttribute("aria-pressed", "false");
    el.addEventListener("click", item.onPick);
  }
  if (item.key) el.dataset.key = item.key;
  return add(el,
    add(h("span", "min-w-0"),
      h("span", "block truncate text-ink-strong", item.name),
      item.value ? h("span", "num block text-[12.5px] text-muted sm:hidden", item.value) : null),
    h("span", "num hidden text-right text-[13px] text-ink sm:block", item.value ?? ""),
    item.text ? h("span", "track") : track(item.move, scale),
    h("span", `num text-right text-[13px] ${toneClass(item.move)}`, item.text ?? signedPct(item.move, 2)));
}

// A titled group of rows inside a ruler.
export const rulerGroup = (title: string, rows: HTMLElement[]) => (rows.length ? [h("div", "ruler-group", title), ...rows] : []);

export const snapshotItem = (s: Snapshot, onPick?: (s: Snapshot) => void): RulerItem =>
  ({ key: s.symbol, name: s.name, value: level(s.price, s.kind), move: s.change_pct, onPick: onPick ? () => onPick(s) : undefined, href: onPick ? undefined : quoteHref(s.symbol) });

// A yield moves in basis points, not in percent of itself: it gets its figure and no mark.
export function rateItem(s: Snapshot): RulerItem {
  const bp = Math.round(s.change * 100);
  return { key: s.symbol, name: s.name, value: level(s.price, s.kind), move: s.change, text: `${bp > 0 ? "+" : bp < 0 ? "−" : ""}${Math.abs(bp)} bp` };
}

// Sectors on the ruler, from the strongest to the weakest.
export function sectorRuler(sectors: Sector[]): HTMLElement {
  const sorted = [...sectors].sort((a, b) => b.change_pct - a.change_pct);
  const scale = rulerScale(sorted.map((s) => s.change_pct));
  return add(h("div", "ruler"),
    add(h("div", "ruler-row !py-0 pb-1"), h("span"), h("span", "hidden sm:block"), rulerAxis(scale), h("span")),
    ...sorted.map((s) => rulerRow({ name: s.name, move: s.change_pct }, scale)));
}

// What a sector's move is the move of: the provider says how it measures it.
export const sectorsNote = (o: Overview) => (o.sectors_by === "funds" ? "Each sector by the move of its SPDR fund" : "Average move of each sector's stocks");

// --- Tables ------------------------------------------------------------------------------------

// A table of instruments: level, the day's move on the ruler, and returns over several periods.
export function quoteTable(items: Snapshot[]): HTMLElement {
  const t = h("table", "data-table");
  const rates = items.every((s) => s.kind === "rate");
  const scale = rulerScale(items.map((s) => s.change_pct));
  const head = ["Name", "Last", "Change", rates ? "" : "Today", "", "1 month", "YTD", "1 year", "30 days"];
  add(t, add(h("thead"), add(h("tr"), ...head.map((x) => h("th", "", x)))),
    add(h("tbody"), ...items.map((s) => {
      const linked = s.kind !== "rate";
      const name = linked ? linkTo(quoteHref(s.symbol), "text-ink-strong hover:underline", s.name) : h("span", "text-ink-strong", s.name);
      const tr = add(h("tr", linked ? "row-link" : ""),
        add(h("td"), name),
        h("td", "text-ink-strong", level(s.price, s.kind)),
        h("td", toneClass(s.change), rates ? rateItem(s).text : change(s.change, s.kind)),
        rates ? h("td") : add(h("td"), add(h("div", "ml-auto"), track(s.change_pct, scale))),
        rates ? h("td") : h("td", toneClass(s.change_pct), signedPct(s.change_pct, 2)),
        h("td", toneClass(s.return_1m), signedPct(s.return_1m)),
        h("td", toneClass(s.return_ytd), signedPct(s.return_ytd)),
        h("td", toneClass(s.return_1y), signedPct(s.return_1y)),
        add(h("td"), sparkline(s.spark, 88, 24)));
      if (linked) tr.addEventListener("click", (e) => !(e.target as Element).closest("a") && (location.href = quoteHref(s.symbol)));
      return tr;
    })));
  return add(h("div", "overflow-x-auto"), t);
}

export function moversTable(items: Mover[]): HTMLElement {
  const t = h("table", "data-table");
  add(t, add(h("thead"), add(h("tr"), ...["Stock", "Price", "Today"].map((x) => h("th", "", x)))),
    add(h("tbody"), ...items.map((m) => {
      const tr = add(h("tr", "row-link"),
        add(h("td"), linkTo(quoteHref(m.symbol), "num text-ink-strong hover:underline", m.symbol),
          h("div", "max-w-[11rem] truncate text-[12.5px] text-muted", m.name)),
        h("td", "text-ink", level(m.price, m.kind)),
        add(h("td"), pill(m.change_pct)));
      tr.addEventListener("click", (e) => !(e.target as Element).closest("a") && (location.href = quoteHref(m.symbol)));
      return tr;
    })));
  return add(h("div", "overflow-x-auto"), t);
}

// Tabs over a few views of the same block.
export function tabbed(views: { label: string; render: () => HTMLElement }[], initial = 0): { tabs: HTMLElement; body: HTMLElement } {
  const tabs = h("div", "tabs");
  tabs.setAttribute("role", "tablist");
  const body = h("div");
  const show = (i: number) => {
    tabs.querySelectorAll("button").forEach((b, j) => b.setAttribute("aria-selected", String(i === j)));
    body.replaceChildren(views[i].render());
  };
  views.forEach((v, i) => {
    const b = h("button", "tab-btn", v.label);
    b.type = "button";
    b.setAttribute("role", "tab");
    b.addEventListener("click", () => show(i));
    tabs.append(b);
  });
  show(initial);
  return { tabs, body };
}

// --- States ------------------------------------------------------------------------------------

// A part of the overview the provider did not answer is sample data: say so next to its title.
export function flagSample(o: Overview, sections: string[], title: Element | null) {
  if (!title || !sections.some((s) => o.sample_sections?.includes(s))) return;
  const badge = h("span", "ml-2 align-middle text-[12.5px] font-normal text-warn", "sample figures");
  badge.title = "The data provider did not answer this part: these figures are placeholders, not the market.";
  title.append(badge);
}

export function failed(el: HTMLElement, text = "Not available right now.") {
  el.replaceChildren(h("p", "py-4 text-sm text-muted", text));
}
