// My Hub's chart: today's holdings against the indices, over the range the reader picks.
import { add, card, h } from "./dom";
import { signedPct } from "./format";
import { points, tone } from "./hub";
import { compareChart } from "./lwc";
import type { Dashboard } from "./types";

// A colour per index, quiet enough to leave the holdings' line in front.
export const INDEX_COLORS: Record<string, string> = { SPY: "#8c8b86", QQQ: "#6f93c4", DIA: "#c9a45a", IWM: "#a388c9" };
const RANGES = ["1M", "3M", "YTD", "1Y"] as const;
const DAYS: Record<string, number> = { "1M": 30, "3M": 91, "1Y": 365 };

// Where a range starts in the series: the last close on or before its first day.
function start(dates: string[], range: string): number {
  const last = dates[dates.length - 1];
  const cutoff = range === "YTD" ? `${+last.slice(0, 4) - 1}-12-31` : new Date(Date.parse(`${last}T00:00:00Z`) - DAYS[range] * 86400000).toISOString().slice(0, 10);
  let from = 0;
  for (let i = 0; i < dates.length && dates[i] <= cutoff; i++) from = i;
  return from;
}

export function indexChart(d: Dashboard): HTMLElement {
  const c = card("Today's holdings against the indices",
    "The positions you hold now, held through the period, next to the indices, all from 100. Trades are not recorded, so this is not your actual past return.");
  const hst = d.history;
  if (!hst.dates.length) return (c.body.append(h("p", "text-sm text-muted", "No common price history yet.")), c.el);
  let range: string = "1Y";
  const shown = new Set(["SPY"]);
  const host = h("div");
  let chart: { remove(): void } | null = null;

  const draw = () => {
    const from = start(hst.dates, range);
    const rebased = (values: number[]) => values.slice(from).map((v, _, part) => +((v / part[0]) * 100).toFixed(2));
    chart?.remove();
    chart = compareChart(host, hst.dates.slice(from), [
      { name: "Your holdings", values: rebased(hst.portfolio_rebased), color: "#f2f0ea" },
      ...d.performance.indices.filter((i) => shown.has(i.ticker) && hst.indices[i.ticker]).map((i) => ({ name: i.name, values: rebased(hst.indices[i.ticker]), color: INDEX_COLORS[i.ticker] ?? "#8c8b86" })),
    ], 320);
  };

  const ranges = h("div", "tabs");
  ranges.setAttribute("role", "tablist");
  for (const r of RANGES) {
    const b = h("button", "tab-btn", r);
    b.type = "button";
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", String(r === range));
    b.addEventListener("click", () => {
      range = r;
      ranges.querySelectorAll("button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
      draw();
    });
    ranges.append(b);
  }
  const toggles = h("div", "flex flex-wrap gap-1.5");
  for (const i of d.performance.indices) {
    if (!hst.indices[i.ticker]) continue;
    const swatch = h("span", "inline-block h-[3px] w-3 rounded-full");
    swatch.style.background = INDEX_COLORS[i.ticker] ?? "#8c8b86";
    const b = add(h("button", "chip !font-sans !px-2 !py-0.5 aria-[pressed=false]:opacity-50"), swatch, i.name);
    b.type = "button";
    b.setAttribute("aria-pressed", String(shown.has(i.ticker)));
    b.addEventListener("click", () => {
      shown.has(i.ticker) ? shown.delete(i.ticker) : shown.add(i.ticker);
      b.setAttribute("aria-pressed", String(shown.has(i.ticker)));
      draw();
    });
    toggles.append(b);
  }
  add(c.body, add(h("div", "mb-3 flex flex-wrap items-center justify-between gap-3"), ranges, toggles), host, periodStrip(d));
  // Drawn once the panel is in the page, so the chart knows its width.
  requestAnimationFrame(draw);
  return c.el;
}

// Each period in a cell: the holdings' return, the index's, and the gap between them in points.
export function periodStrip(d: Dashboard): HTMLElement {
  const index = d.performance.indices[0];
  return add(h("div", "mt-5 grid grid-cols-2 gap-px overflow-hidden rounded-sm border border-line bg-line sm:grid-cols-5"),
    ...d.performance.periods.map((p) => {
      const theirs = p.indices[index.ticker];
      const gap = p.portfolio != null && theirs != null ? p.portfolio - theirs : null;
      return add(h("div", "bg-page p-3"),
        h("div", "label", p.label),
        h("div", `num mt-1 text-lg font-semibold ${tone(p.portfolio)}`, signedPct(p.portfolio, p.key === "1d" ? 2 : 1)),
        add(h("div", "mt-0.5 text-[12px] text-muted"), `${index.name} `, h("span", "num", signedPct(theirs, p.key === "1d" ? 2 : 1))),
        h("div", `num mt-0.5 text-[12px] ${tone(gap)}`, gap == null ? "—" : `${points(gap, p.key === "1d" ? 2 : 1)} ${gap >= 0 ? "ahead" : "behind"}`));
    }));
}
