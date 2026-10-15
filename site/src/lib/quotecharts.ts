// The quote page's charts below the price: the symbol against the S&P 500, its calendar years,
// its falls from the high, a company's income statements and what a fund holds.
import { BaselineSeries, LineStyle, type Time } from "lightweight-charts";
import { add, h, linkTo } from "./dom";
import { pct, shortDate, signedPct, type N } from "./format";
import { baseChart, C, returnsChart } from "./lwc";
import type { History, Weight } from "./market";

const ok = (v: N): v is number => typeof v === "number" && Number.isFinite(v);

// One colour for the symbol, one for the S&P 500, wherever the two are drawn side by side.
export const SELF = "#f2f0ea";
export const BENCH = "#8c8b86";
// The figures of an income statement.
export const REVENUE = "#6f93c4";
export const EARNINGS = "#c9a45a";

function swatch(color: string, cls = "h-[3px] w-4 rounded-full") {
  const s = h("span", `inline-block flex-none align-middle ${cls}`);
  s.style.background = color;
  return s;
}

export function legend(items: { name: string; color: string; value?: string; tone?: string }[]): HTMLElement {
  return add(h("div", "flex flex-wrap gap-x-5 gap-y-1 text-[13px]"),
    ...items.map((i) => add(h("span", "inline-flex items-center gap-1.5"), swatch(i.color), h("span", "text-muted", i.name),
      i.value ? h("span", `num ${i.tone ?? "text-ink-strong"}`, i.value) : null)));
}

// Small buttons that pick one of a few views of the same chart.
export function picker<T extends string>(items: readonly T[], current: T, pick: (v: T) => void, labels: Partial<Record<T, string>> = {}): HTMLElement {
  const box = h("div", "tabs");
  box.setAttribute("role", "tablist");
  const draw = (now: T) => box.replaceChildren(...items.map((v) => {
    const b = h("button", "tab-btn", labels[v] ?? v);
    b.type = "button";
    b.setAttribute("role", "tab");
    b.setAttribute("aria-selected", String(v === now));
    b.addEventListener("click", () => (draw(v), pick(v)));
    return b;
  }));
  draw(current);
  return box;
}

// --- against the S&P 500 -------------------------------------------------------------------------

export const SPANS = { "1Y": 252, "3Y": 756, "5Y": 1260 } as const;
export type Span = keyof typeof SPANS;

// The spans the closes cover: a span is offered when most of it is there.
export const spansOf = (hist: History) => (Object.keys(SPANS) as Span[]).filter((s, i) => !i || hist.dates.length > SPANS[s] * 0.8);

// Both lines from zero at the start of the span; the legend says where each ended and by how much they differ.
export function growth(host: HTMLElement, hist: History, symbol: string, span: Span) {
  const n = Math.min(hist.dates.length, SPANS[span] + 1);
  const dates = hist.dates.slice(-n), mine = hist.closes.slice(-n);
  const bench = hist.benchmark_closes?.slice(-n) ?? null;
  const first = bench?.findIndex(ok) ?? -1;
  const lines = [{ name: symbol, values: mine.map((c) => c / mine[0] - 1), color: SELF }];
  // The benchmark starts where it has a close: a symbol listed before it has none at first.
  const b0 = first >= 0 && bench ? bench[first]! : null;
  if (b0 && bench) lines.push({ name: "S&P 500", values: bench.map((c) => (ok(c) ? c / b0 - 1 : 0)), color: BENCH });
  const top = h("div", "mb-3");
  const box = h("div");
  host.replaceChildren(top, box);
  const ends = lines.map((l) => l.values[l.values.length - 1]);
  top.replaceChildren(legend([
    ...lines.map((l, i) => ({ name: l.name, color: l.color, value: signedPct(ends[i]), tone: ends[i] > 0 ? "up" : ends[i] < 0 ? "down" : "text-ink" })),
  ]), ...(lines.length > 1 ? [h("p", "mt-1 text-[13px] text-muted",
    `${symbol} ${ends[0] >= ends[1] ? "ahead of" : "behind"} the S&P 500 by ${(Math.abs(ends[0] - ends[1]) * 100).toFixed(1)} percentage points since ${shortDate(dates[0])}.`)] : []));
  returnsChart(box, dates, lines, 300);
}

// --- bars ------------------------------------------------------------------------------------------

export type Group = { label: string; values: N[]; note?: string };

// Columns side by side for a few periods: each group one period, each colour one series. Zero is a
// line; a fall goes below it. Every column carries its figure.
export function columns(groups: Group[], series: { name: string; color: string }[], format: (v: number) => string, height = 190): HTMLElement {
  const all = groups.flatMap((g) => g.values).filter(ok);
  const hi = Math.max(0, ...all), lo = Math.min(0, ...all);
  const span = hi - lo || 1;
  const zero = (hi / span) * 100; // from the top, in percent of the plot
  const plot = h("div", "relative flex gap-2 sm:gap-4");
  plot.style.height = `${height}px`;
  plot.style.marginTop = "18px"; // room for the figure over the tallest column
  plot.style.marginBottom = lo < 0 ? "18px" : "0";
  const axis = h("div", "absolute inset-x-0 h-px bg-line-strong");
  axis.style.top = `${zero}%`;
  plot.append(axis);
  for (const g of groups) {
    const col = h("div", "relative flex h-full min-w-0 flex-1 justify-center gap-[3px]");
    g.values.forEach((v, i) => {
      const lane = h("div", "relative h-full min-w-0 flex-1 max-w-[38px]");
      if (ok(v)) {
        const bar = h("div", "absolute inset-x-0 rounded-[2px]");
        bar.style.background = series[i].color;
        const size = (Math.abs(v) / span) * 100;
        bar.style.top = `${v >= 0 ? zero - size : zero}%`;
        bar.style.height = `${Math.max(size, 0.6)}%`;
        const label = h("span", "num pointer-events-none absolute left-1/2 hidden -translate-x-1/2 whitespace-nowrap text-[10.5px] text-ink sm:block", format(v));
        if (v >= 0) label.style.bottom = `${100 - zero + size}%`;
        else label.style.top = `${zero + size}%`;
        if (v >= 0) label.style.marginBottom = "2px";
        lane.title = `${g.label} · ${series[i].name}: ${format(v)}`;
        lane.append(bar, label);
      }
      col.append(lane);
    });
    plot.append(col);
  }
  const labels = add(h("div", "mt-2 flex gap-2 sm:gap-4"),
    ...groups.map((g) => add(h("div", "min-w-0 flex-1 text-center"), h("div", "num truncate text-[12px] text-ink", g.label),
      g.note ? h("div", "truncate text-[11px] text-faint", g.note) : null)));
  return add(h("div"), legend(series), plot, labels);
}

// Rows of shares of a whole, longest first: a name (a link, when it has a page), a bar and a percent.
export function weights(items: (Weight & { href?: string | null; tag?: string })[]): HTMLElement {
  const max = Math.max(...items.map((i) => i.weight), 0.0001);
  return add(h("div", "space-y-2"), ...items.map((i) => {
    const bar = h("div", "h-[6px] rounded-full bg-ink-strong/70");
    bar.style.width = `${(i.weight / max) * 100}%`;
    const name = i.href ? linkTo(i.href, "min-w-0 truncate text-ink-strong hover:underline", i.name) : h("span", "min-w-0 truncate text-ink", i.name);
    return add(h("div", "grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_3.5rem] items-center gap-3 text-sm"),
      add(h("div", "flex min-w-0 items-baseline gap-2"), i.tag ? h("span", "num flex-none text-[12px] text-muted", i.tag) : null, name),
      add(h("div", "h-[6px] rounded-full bg-line"), bar),
      h("span", "num text-right text-[13px] text-ink-strong", pct(i.weight)));
  }));
}

// One bar split into what a fund holds: stocks, bonds, cash.
const MIX = ["#f2f0ea", "#6f93c4", "#c9a45a", "#a388c9", "#35c98f", "#8c8b86"];
export function mix(items: Weight[]): HTMLElement {
  const bar = h("div", "flex h-[10px] overflow-hidden rounded-full bg-line");
  items.forEach((i, k) => {
    const part = h("div", "h-full");
    part.style.width = `${i.weight * 100}%`;
    part.style.background = MIX[k % MIX.length];
    part.title = `${i.name}: ${pct(i.weight)}`;
    bar.append(part);
  });
  return add(h("div"), bar, add(h("div", "mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[13px]"),
    ...items.map((i, k) => add(h("span", "inline-flex items-center gap-1.5"), swatch(MIX[k % MIX.length], "h-2 w-2 rounded-full"),
      h("span", "text-muted", i.name), h("span", "num text-ink-strong", pct(i.weight))))));
}

// --- falls from the high ----------------------------------------------------------------------------

// How far below its highest close so far the price stood each day: zero at a new high.
export function drawdowns(host: HTMLElement, dates: string[], closes: number[], height = 200) {
  const box = h("div");
  box.style.height = `${height}px`;
  host.replaceChildren(box);
  const chart = baseChart(box);
  chart.applyOptions({ localization: { locale: "en-US", priceFormatter: (v: number) => `${v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}%` } });
  let peak = -Infinity;
  // Filled between zero and the line: the deeper the fall, the more red.
  const series = chart.addSeries(BaselineSeries, { baseValue: { type: "price", price: 0 }, topLineColor: C.down, bottomLineColor: C.down,
    topFillColor1: "rgba(0,0,0,0)", topFillColor2: "rgba(0,0,0,0)", bottomFillColor1: C.down2, bottomFillColor2: C.down2,
    lineWidth: 1, priceLineVisible: false, lastValueVisible: true });
  series.setData(dates.map((d, i) => {
    peak = Math.max(peak, closes[i]);
    return { time: d as Time, value: +((closes[i] / peak - 1) * 100).toFixed(2) };
  }));
  series.createPriceLine({ price: 0, color: C.cross, lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: false, title: "" });
  chart.timeScale().fitContent();
}
