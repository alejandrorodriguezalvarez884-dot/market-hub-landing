// TradingView's free widgets on the public pages: the price chart and the map of the market.
// A widget is a frame TradingView fills with its own data, under its own terms: nothing of it
// passes through this site's server, and it carries TradingView's name.
import { add, h, linkTo } from "./dom";
import { priceChart } from "./lwc";
import { link } from "./site";

const EMBED = "https://s3.tradingview.com/external-embedding";

// The site's symbols for what is not a stock -> TradingView's. Its widgets do not carry the
// indices themselves (nor the futures of the commodities): each one is charted by a contract that
// follows it, which is what TradingView offers for them. Stocks and funds go by their ticker.
const SYMBOLS: Record<string, string> = {
  SPX: "FOREXCOM:SPXUSD", NDX: "FOREXCOM:NSXUSD", DJI: "FOREXCOM:DJI", RUT: "FOREXCOM:US2000", VIX: "CAPITALCOM:VIX",
  SX5E: "FOREXCOM:EU50", UKX: "FOREXCOM:UKXGBP", N225: "FOREXCOM:JPXJPY",
  GOLD: "TVC:GOLD", SILVER: "TVC:SILVER", WTI: "TVC:USOIL", NATGAS: "CAPITALCOM:NATURALGAS", COPPER: "CAPITALCOM:COPPER",
  EURUSD: "FX:EURUSD", GBPUSD: "FX:GBPUSD", USDJPY: "FX:USDJPY", BTCUSD: "BITSTAMP:BTCUSD", ETHUSD: "BITSTAMP:ETHUSD",
};
// TradingView's widgets have no chart for these: they keep the site's own.
const NONE = new Set(["US10Y", "US2Y"]);

export function tvSymbol(symbol: string): string | null {
  const s = symbol.toUpperCase();
  return NONE.has(s) ? null : SYMBOLS[s] ?? s.replace("-", ".");
}

// The ticker of a symbol as TradingView writes it ("NASDAQ:AAPL", "NYSE:BRK.B"): its widgets
// hand it to the page they link to.
export const fromTv = (symbol: string) => (symbol.split(":").pop() ?? "").trim().toUpperCase().replace(".", "-");

// One widget: TradingView's script reads its settings from its own text and puts the frame next to it.
function widget(name: string, settings: Record<string, unknown>, credit: string): HTMLElement {
  const script = document.createElement("script");
  script.src = `${EMBED}/embed-widget-${name}.js`;
  script.async = true;
  script.text = JSON.stringify(settings);
  const by = linkTo("https://www.tradingview.com/", "hover:text-ink-strong", "TradingView");
  by.target = "_blank";
  by.rel = "noopener nofollow";
  return add(h("div", "tradingview-widget-container flex h-full w-full flex-col"),
    h("div", "tradingview-widget-container__widget min-h-0 w-full flex-1"),
    add(h("p", "pt-2 text-[12.5px] text-muted"), `${credit} `, by, "."),
    script);
}

export type Chart = { setSymbol(symbol: string): void };

// The price chart of a symbol. `range` is the span it opens on: "1D" or "12M".
export function tvChart(host: HTMLElement, opts: { symbol: string; range?: "1D" | "12M"; height?: number }): Chart {
  const range = opts.range ?? "12M";
  let own: Chart | null = null; // the site's own chart, for what TradingView has none
  function show(symbol: string) {
    const tv = tvSymbol(symbol);
    if (!tv) {
      host.style.height = "";
      if (own) own.setSymbol(symbol);
      else own = priceChart(host, { symbol, range: "1Y", height: (opts.height ?? 460) - 60 });
      return;
    }
    own = null;
    host.style.height = `${opts.height ?? 460}px`;
    host.replaceChildren(widget("advanced-chart", {
      autosize: true, symbol: tv, interval: range === "1D" ? "5" : "D", range, timezone: "America/New_York",
      theme: "dark", style: "1", locale: "en", backgroundColor: "#0b0c0d", gridColor: "rgba(242, 240, 234, 0.06)",
      hide_side_toolbar: true, hide_top_toolbar: false, allow_symbol_change: false, save_image: false,
      withdateranges: true, calendar: false, details: false, hotlist: false, support_host: "https://www.tradingview.com",
    }, "Chart by"));
  }
  show(opts.symbol);
  return { setSymbol: show };
}

// The S&P 500 as a map: a block per company, sized by its market value, coloured by its move
// of the day and grouped by sector. A block opens the company's page here.
export function tvHeatmap(host: HTMLElement, height = 560) {
  host.style.height = `${height}px`;
  host.replaceChildren(widget("stock-heatmap", {
    dataSource: "SPX500", grouping: "sector", blockSize: "market_cap_basic", blockColor: "change", exchanges: [],
    locale: "en", colorTheme: "dark", hasTopBar: false, isDataSetEnabled: false, isZoomEnabled: true, hasSymbolTooltip: true,
    isMonoSize: false, symbolUrl: new URL(link("/quote/"), location.href).href, width: "100%", height: "100%",
  }, "Map by"));
}
