// The chart of one stock on the watchlist's wall: its daily bars with their 20, 50 and 200-day
// averages, small enough to sit next to several others and to take whatever size its tile has.
import { AreaSeries, CandlestickSeries, HistogramSeries, LineSeries, type ISeriesApi, type SeriesType, type Time } from "lightweight-charts";
import { add, h, linkTo } from "./dom";
import { baseChart, C } from "./lwc";
import type { Bars } from "./watch";

export const RANGES = { "3M": 63, "6M": 126, "1Y": 252, "2Y": 504 } as const;
export type Range = keyof typeof RANGES;
export type ChartLook = { range: Range; style: "candles" | "area"; averages: boolean };

// The averages keep one colour each wherever they are drawn: on the chart and on the gauges.
export const AVERAGES = [
  { sessions: 20, name: "20-day", color: "#c9c7c1" },
  { sessions: 50, name: "50-day", color: "#6f93c4" },
  { sessions: 200, name: "200-day", color: "#c9a45a" },
] as const;

// The mean of the last `n` values at each point; null until there are `n`.
export function average(values: number[], n: number): (number | null)[] {
  let sum = 0;
  return values.map((v, i) => {
    sum += v - (i >= n ? values[i - n] : 0);
    return i >= n - 1 ? sum / n : null;
  });
}

export type TileChart = { look(next: ChartLook): void; remove(): void };

export function tileChart(host: HTMLElement, bars: Bars, first: ChartLook): TileChart {
  const box = h("div", "absolute inset-0");
  const legend = h("div", "pointer-events-none absolute left-1 top-1 z-10 flex gap-2 text-[11px]");
  host.replaceChildren(box, legend);
  const chart = baseChart(box);
  // A logo on every tile of a wall would be most of what is seen: the page credits the library once instead (chartCredit).
  chart.applyOptions({ layout: { fontSize: 10, attributionLogo: false }, rightPriceScale: { borderVisible: false }, timeScale: { borderVisible: false } });
  // A provider that only has closes gives bars with no range: they are drawn as a line.
  const flat = bars.open.every((o, i) => o === bars.close[i] && bars.high[i] === bars.low[i]);
  const lines = AVERAGES.map((a) => ({ ...a, values: average(bars.close, a.sessions) }));
  let series: { remove(): void }[] = [];

  function look(next: ChartLook) {
    for (const s of series) s.remove();
    const from = Math.max(0, bars.time.length - RANGES[next.range]);
    const at = (i: number) => bars.time[i] as Time;
    const index = bars.time.map((_, i) => i).slice(from);
    const rising = bars.close[bars.close.length - 1] >= bars.close[from];
    const drawn: ISeriesApi<SeriesType>[] = [];
    if (next.style === "candles" && !flat) {
      const s = chart.addSeries(CandlestickSeries, { upColor: C.up, downColor: C.down, borderVisible: false, wickUpColor: C.up, wickDownColor: C.down, priceLineVisible: false });
      s.setData(index.map((i) => ({ time: at(i), open: bars.open[i], high: bars.high[i], low: bars.low[i], close: bars.close[i] })));
      drawn.push(s);
    } else {
      const s = chart.addSeries(AreaSeries, { lineColor: rising ? C.up : C.down, topColor: rising ? C.up2 : C.down2, bottomColor: "rgba(0,0,0,0)", lineWidth: 2,
        priceLineVisible: false, crosshairMarkerRadius: 3, crosshairMarkerBorderColor: C.bg });
      s.setData(index.map((i) => ({ time: at(i), value: bars.close[i] })));
      drawn.push(s);
    }
    drawn[0].priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.2 } });
    const shown = next.averages ? lines.filter((l) => l.values[bars.close.length - 1] != null) : [];
    for (const l of shown) {
      const s = chart.addSeries(LineSeries, { color: l.color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      s.setData(index.filter((i) => l.values[i] != null).map((i) => ({ time: at(i), value: l.values[i]! })));
      drawn.push(s);
    }
    if (bars.volume.some((v) => v > 0)) {
      const s = chart.addSeries(HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      s.priceScale().applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });
      s.setData(index.map((i) => ({ time: at(i), value: bars.volume[i], color: C.volume })));
      drawn.push(s);
    }
    series = drawn.map((s) => ({ remove: () => chart.removeSeries(s) }));
    legend.replaceChildren(...shown.map((l) => {
      const name = h("span", "num", String(l.sessions));
      name.style.color = l.color;
      return name;
    }));
    chart.timeScale().fitContent();
  }

  look(first);
  return { look, remove: () => chart.remove() };
}

// The library's credit, where its logo is not drawn.
export function chartCredit(cls = ""): HTMLElement {
  const by = linkTo("https://www.tradingview.com/", "hover:text-ink-strong", "TradingView");
  by.target = "_blank";
  by.rel = "noopener nofollow";
  return add(h("p", `text-[12px] text-faint ${cls}`), "Charts by ", by, " Lightweight Charts™.");
}

// The legend of the averages' colours, for the bar above the wall.
export function averagesKey(): HTMLElement {
  return add(h("span", "inline-flex items-center gap-2.5 text-[12px] text-muted"), ...AVERAGES.map((a) => {
    const swatch = h("span", "inline-block h-[2px] w-3.5 align-middle");
    swatch.style.background = a.color;
    return add(h("span", "inline-flex items-center gap-1"), swatch, a.name);
  }));
}
