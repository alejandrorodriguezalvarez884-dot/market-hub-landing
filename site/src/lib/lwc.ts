// Charts on TradingView's Lightweight Charts (Apache-2.0). The library keeps its attribution
// logo on, as its licence asks.
import {
  AreaSeries, CandlestickSeries, ColorType, CrosshairMode, HistogramSeries, LineSeries, LineStyle, createChart,
  type IChartApi, type ISeriesApi, type MouseEventParams, type SeriesType, type Time, type UTCTimestamp,
} from "lightweight-charts";
import { add, h } from "./dom";
import { change, level, signedPct } from "./format";
import { chartData, RANGES, type Bar, type ChartData } from "./market";

// The site's tokens (styles/global.css), as the chart library wants them.
export const C = {
  bg: "#0b0c0d", grid: "#17191b", text: "#8c8b86", line: "#222528", cross: "#5f5f5b", label: "#3a3e42",
  ink: "#f2f0ea", up: "#35c98f", down: "#ff6b57", up2: "rgba(53,201,143,0.16)", down2: "rgba(255,107,87,0.16)",
  volume: "rgba(242,240,234,0.13)",
};

export function baseChart(el: HTMLElement): IChartApi {
  return createChart(el, {
    autoSize: true,
    // Fixed, so numbers and dates read the same as the rest of the site whatever the browser's locale.
    localization: { locale: "en-US" },
    layout: { background: { type: ColorType.Solid, color: C.bg }, textColor: C.text, fontSize: 11,
              fontFamily: "'IBM Plex Mono', ui-monospace, monospace", attributionLogo: true },
    grid: { vertLines: { visible: false }, horzLines: { color: C.grid } },
    rightPriceScale: { borderColor: C.line },
    timeScale: { borderColor: C.line, rightOffset: 2, fixLeftEdge: true, fixRightEdge: true },
    crosshair: { mode: CrosshairMode.Magnet, vertLine: { color: C.cross, labelBackgroundColor: C.label },
                 horzLine: { color: C.cross, labelBackgroundColor: C.label } },
    handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true },
    handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
  });
}

const t = (time: Bar["time"]) => time as Time;

const SPAN: Record<string, string> = { "1D": "Today", "5D": "Five days", "1M": "One month", "6M": "Six months", YTD: "This year", "1Y": "One year", "5Y": "Five years" };

// A bar's moment, as the axis shows it: a date, or a date and the exchange's time.
function when(time: Bar["time"]): string {
  if (typeof time === "string") return new Date(`${time}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  return new Date(time * 1000).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "UTC" });
}

export type PriceChart = { setSymbol(symbol: string): void };

// The main price chart: range tabs, line or candles, volume, and a legend that follows the
// crosshair. `height` in pixels. `intraday: false` when the data plan is known not to have
// intraday bars: the 1D and 5D ranges are not offered and the chart opens on a month.
export function priceChart(host: HTMLElement, opts: { symbol: string; range?: string; style?: "area" | "candles";
                           height?: number; intraday?: boolean; onData?: (d: ChartData) => void }): PriceChart {
  let symbol = opts.symbol;
  // Intraday bars are not in every data plan: without them, the 1D and 5D ranges go away.
  let intraday = opts.intraday ?? true;
  let range = opts.range ?? "1Y";
  if (!intraday && (range === "1D" || range === "5D")) range = "1M";
  let style = opts.style ?? "area";
  let data: ChartData | null = null;
  let seq = 0;

  const rangeTabs = h("div", "tabs");
  rangeTabs.setAttribute("role", "tablist");
  const styleTabs = h("div", "tabs");
  const bar = add(h("div", "flex flex-wrap items-center justify-between gap-x-6 gap-y-1 pb-2"), rangeTabs, styleTabs);
  const box = h("div", "relative");
  box.style.height = `${opts.height ?? 380}px`;
  const legend = h("div", "pointer-events-none absolute left-0 top-1 z-10 text-[12.5px]");
  const status = h("div", "absolute inset-0 z-10 flex items-center justify-center text-sm text-muted");
  add(box, legend, status);
  host.replaceChildren(bar, box);

  const chart = baseChart(box);
  let main: ISeriesApi<SeriesType> | null = null;
  let volume: ISeriesApi<"Histogram"> | null = null;

  function tabs(el: HTMLElement, items: readonly string[], current: () => string, pick: (v: string) => void, labels?: Record<string, string>) {
    el.replaceChildren(...items.map((v) => {
      const b = h("button", "tab-btn", labels?.[v] ?? v);
      b.type = "button";
      b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", String(v === current()));
      b.addEventListener("click", () => pick(v));
      return b;
    }));
  }
  const drawTabs = () => {
    tabs(rangeTabs, RANGES.filter((r) => intraday || (r !== "1D" && r !== "5D")), () => range, (v) => ((range = v), load()));
    tabs(styleTabs, ["area", "candles"], () => style, (v) => ((style = v as typeof style), draw()), { area: "Line", candles: "Candles" });
  };

  function legendFor(b: Bar | null) {
    if (!data) return;
    const bars = data.bars;
    const last = b ?? bars[bars.length - 1];
    const first = data.range === "1D" ? data.prev_close : bars[0].open;
    const diff = last.close - first;
    const pct = first ? diff / first : null;
    const tone = diff > 0 ? "up" : diff < 0 ? "down" : "text-muted";
    // What the figures are: the bar under the crosshair, or the whole range; the change is
    // always counted from the start of the range, and says so.
    const parts: (HTMLElement | string)[] = [h("span", "text-muted", b ? when(b.time) : SPAN[data.range] ?? data.range)];
    if (style === "candles" && b) {
      for (const [k, v] of [["O", last.open], ["H", last.high], ["L", last.low], ["C", last.close]] as const)
        parts.push(h("span", "ml-2 text-muted", k), h("span", "ml-1 num text-ink-strong", level(v, data.kind)));
    } else if (b) parts.push(h("span", "ml-2 num text-ink-strong", level(last.close, data.kind)));
    parts.push(h("span", `ml-2 num ${tone}`, `${change(diff, data.kind)} (${signedPct(pct, 2)})`));
    if (b) parts.push(h("span", "ml-1 text-muted", data.range === "1D" ? "vs. previous close" : "vs. start"));
    legend.replaceChildren(add(h("div", "bg-page/85 pr-2"), ...parts));
  }

  function draw() {
    drawTabs();
    if (main) chart.removeSeries(main);
    if (volume) chart.removeSeries(volume);
    main = volume = null;
    if (!data || !data.bars.length) return;
    const bars = data.bars;
    const first = data.range === "1D" ? data.prev_close : bars[0].open;
    const rising = bars[bars.length - 1].close >= first;
    const digits = data.kind === "fx" ? 4 : data.kind === "rate" ? 3 : 2;
    const priceFormat = { type: "price" as const, precision: digits, minMove: 1 / 10 ** digits };
    if (style === "candles") {
      const s = chart.addSeries(CandlestickSeries, { upColor: C.up, downColor: C.down, borderVisible: false,
        wickUpColor: C.up, wickDownColor: C.down, priceFormat });
      s.setData(bars.map((b) => ({ time: t(b.time), open: b.open, high: b.high, low: b.low, close: b.close })));
      main = s;
    } else {
      const color = rising ? C.up : C.down;
      const s = chart.addSeries(AreaSeries, { lineColor: color, topColor: rising ? C.up2 : C.down2, bottomColor: "rgba(0,0,0,0)",
        lineWidth: 2, priceFormat, priceLineVisible: false, crosshairMarkerRadius: 4, crosshairMarkerBorderColor: C.bg });
      s.setData(bars.map((b) => ({ time: t(b.time), value: b.close })));
      main = s;
    }
    if (data.range === "1D")
      main.createPriceLine({ price: data.prev_close, color: C.cross, lineStyle: LineStyle.Dashed, lineWidth: 1,
                             axisLabelVisible: true, title: "Prev close" });
    if (bars.some((b) => b.volume > 0)) {
      volume = chart.addSeries(HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      volume.setData(bars.map((b) => ({ time: t(b.time), value: b.volume, color: C.volume })));
    }
    main.priceScale().applyOptions({ scaleMargins: { top: 0.12, bottom: volume ? 0.22 : 0.08 } });
    chart.applyOptions({ timeScale: { timeVisible: data.interval.endsWith("m"), secondsVisible: false } });
    chart.timeScale().fitContent();
    legendFor(null);
  }

  const byTime = () => new Map(data?.bars.map((b) => [String(b.time), b]));
  let index = byTime();
  chart.subscribeCrosshairMove((p: MouseEventParams) => {
    if (!data) return;
    if (!p.time) return legendFor(null);
    const key = typeof p.time === "object" ? `${p.time.year}-${String(p.time.month).padStart(2, "0")}-${String(p.time.day).padStart(2, "0")}` : String(p.time);
    legendFor(index.get(key) ?? null);
  });

  async function load() {
    const mine = ++seq;
    drawTabs();
    status.textContent = "Loading…";
    status.hidden = false;
    try {
      const d = await chartData(symbol, range);
      if (mine !== seq) return;
      data = d;
      index = byTime();
      status.hidden = true;
      draw();
      opts.onData?.(d);
    } catch {
      if (mine !== seq) return;
      if (range === "1D" || range === "5D") {
        intraday = false;
        range = "1M";
        return load();
      }
      status.textContent = "The chart is not available right now.";
    }
  }
  load();
  return {
    setSymbol(s: string) {
      if (s === symbol) return;
      symbol = s;
      load();
    },
  };
}

// Several series rebased to 100 on the same dates (the dashboard's holdings against the index).
export function compareChart(host: HTMLElement, dates: string[], series: { name: string; values: number[]; color: string }[], height = 300) {
  const legend = add(h("div", "mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted"),
    ...series.map((s) => {
      const sw = h("span", "inline-block h-[3px] w-4 rounded-full align-middle");
      sw.style.background = s.color;
      return add(h("span", "inline-flex items-center gap-1.5"), sw, s.name);
    }));
  const box = h("div");
  box.style.height = `${height}px`;
  host.replaceChildren(legend, box);
  const chart = baseChart(box);
  for (const s of series) {
    const line = chart.addSeries(LineSeries, { color: s.color, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
      priceFormat: { type: "price", precision: 1, minMove: 0.1 } });
    line.setData(dates.map((d, i) => ({ time: d as Time, value: s.values[i] })));
  }
  chart.timeScale().fitContent();
  return chart;
}

// A tiny chart for cards: no axes, no interaction.
export function miniChart(host: HTMLElement, bars: { time: string | number; value: number }[], rising: boolean, height = 64) {
  host.style.height = `${height}px`;
  const chart = createChart(host, {
    autoSize: true, localization: { locale: "en-US" }, layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: C.text, attributionLogo: false },
    grid: { vertLines: { visible: false }, horzLines: { visible: false } },
    rightPriceScale: { visible: false }, timeScale: { visible: false }, crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
    handleScale: false, handleScroll: false,
  });
  const s = chart.addSeries(AreaSeries, { lineColor: rising ? C.up : C.down, topColor: rising ? C.up2 : C.down2, bottomColor: "rgba(0,0,0,0)",
    lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
  s.setData(bars.map((b) => ({ time: (typeof b.time === "number" ? (b.time as UTCTimestamp) : b.time) as Time, value: b.value })));
  chart.timeScale().fitContent();
  return chart;
}
