// The words of the charts: the price chart (lib/lwc.ts), TradingView's widgets (lib/tv.ts) and the
// quote page's charts below the price (lib/quotecharts.ts).
import { words } from ".";

export const charts = words(
  {
    spans: { "1D": "Today", "5D": "Five days", "1M": "One month", "6M": "Six months", YTD: "This year", "1Y": "One year", "5Y": "Five years" } as Record<string, string>,
    ranges: { "1D": "1D", "5D": "5D", "1M": "1M", "6M": "6M", YTD: "YTD", "1Y": "1Y", "5Y": "5Y" } as Record<string, string>,
    line: "Line",
    candles: "Candles",
    ohlc: { O: "O", H: "H", L: "L", C: "C" },
    vsPrev: "vs. previous close",
    vsStart: "vs. start",
    prevClose: "Prev close",
    loading: "Loading…",
    unavailable: "The chart is not available right now.",
    chartBy: "Chart by",
    mapBy: "Map by",
    tvLocale: "en",
    // quotecharts
    versus: (symbol: string, ahead: boolean, points: string, since: string) =>
      `${symbol} ${ahead ? "ahead of" : "behind"} the S&P 500 by ${points} percentage points since ${since}.`,
  },
  {
    spans: { "1D": "Hoy", "5D": "Cinco días", "1M": "Un mes", "6M": "Seis meses", YTD: "Este año", "1Y": "Un año", "5Y": "Cinco años" },
    ranges: { "1D": "1D", "5D": "5D", "1M": "1M", "6M": "6M", YTD: "YTD", "1Y": "1A", "5Y": "5A" },
    line: "Línea",
    candles: "Velas",
    ohlc: { O: "A", H: "Máx", L: "Mín", C: "C" },
    vsPrev: "frente al cierre anterior",
    vsStart: "desde el inicio",
    prevClose: "Cierre ant.",
    loading: "Cargando…",
    unavailable: "El gráfico no está disponible ahora mismo.",
    chartBy: "Gráfico de",
    mapBy: "Mapa de",
    tvLocale: "es",
    versus: (symbol: string, ahead: boolean, points: string, since: string) =>
      `${symbol} va ${points} puntos porcentuales ${ahead ? "por delante del" : "por detrás del"} S&P 500 desde el ${since}.`,
  },
);
