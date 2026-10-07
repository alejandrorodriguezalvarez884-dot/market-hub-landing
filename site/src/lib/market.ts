// The public market API. Prices come from the data provider; a part that is sample data says so
// (`sample: true`, or its name in the overview's `sample_sections`). The news comes from the
// portal's own desk: official documents, the day's figures and headlines from the press.
import { api } from "./api";

export type Kind = "index" | "stock" | "etf" | "rate" | "commodity" | "fx" | "crypto";
export type Snapshot = {
  symbol: string; name: string; kind: Kind; price: number; change: number; change_pct: number;
  return_1m: number | null; return_ytd: number | null; return_1y: number | null; spark: number[];
};
export type Mover = Snapshot & { volume: number | null; sector: string };
export type Sector = { name: string; change_pct: number; return_ytd: number | null; members: string[] };
export type Overview = {
  sample: boolean; sample_sections: string[]; source: string; as_of: string;
  intraday?: boolean; // false once the data plan has refused intraday bars: no 1D and 5D charts
  sectors_by?: "stocks" | "funds"; // a sector's move: the average of its stocks, or its fund's
  tape: Snapshot[]; indices: Snapshot[]; rates: Snapshot[]; commodities: Snapshot[]; currencies: Snapshot[]; crypto: Snapshot[];
  sectors: Sector[]; movers: { gainers: Mover[]; losers: Mover[]; active: Mover[] };
};
export type Bar = { time: string | number; open: number; high: number; low: number; close: number; volume: number };
export type ChartData = { sample: boolean; symbol: string; name: string; kind: Kind; range: string; interval: string; prev_close: number; bars: Bar[] };
export type NewsItem = {
  id: string; category: string; title: string; summary: string; tickers: string[]; source: string; published_utc: string;
  url?: string; // the document or the article; a path for the portal's own pages
  layer?: "official" | "market" | "press";
  written_by?: "source" | "code" | "model"; // who wrote the title: the source itself, the portal's code, or the AI model
  sentiment?: "bullish" | "bearish" | "neutral" | null; // how the news reads; null when nobody has said
  scope?: string | null; // the sector it touches, or "Macro"
  article?: string; // its paragraphs, separated by a blank line: only on an item asked for by its id
};
export type News = {
  sample: boolean; categories: string[]; items: NewsItem[];
  press: NewsItem[]; // headlines from publishers, as links; only with the unfiltered list
  refreshed_utc: string | null;
  stale: boolean; // older than the desk allows: the page asks for a refresh
};
export type Quote = Snapshot & {
  sample: boolean; exchange: string; sector: string; prev_close: number; open: number; day_low: number; day_high: number;
  year_low: number; year_high: number; volume: number; avg_volume: number; market_cap: number | null; pe: number | null;
  eps: number | null; dividend_yield: number | null; beta: number | null; return_6m: number | null; return_5y: number | null;
  news: NewsItem[];
};

export const RANGES = ["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y"] as const;

// The overview feeds several parts of a page (the ticker tape and the page itself): one request.
// `detail` adds the 1-month, YTD and 1-year returns (the markets page's tables).
const overviews = new Map<boolean, Promise<Overview>>();
export function overview(detail = false): Promise<Overview> {
  if (!overviews.has(detail)) overviews.set(detail, api<Overview>(`/api/public/overview${detail ? "?detail=1" : ""}`));
  return overviews.get(detail)!;
}
export const chartData = (symbol: string, range: string) =>
  api<ChartData>(`/api/public/chart?symbol=${encodeURIComponent(symbol)}&range=${encodeURIComponent(range)}`);
export const quote = (t: string) => api<Quote>(`/api/public/quote?t=${encodeURIComponent(t)}`);
export function news(opts: { category?: string; ticker?: string; limit?: number } = {}) {
  const q = new URLSearchParams();
  if (opts.category) q.set("category", opts.category);
  if (opts.ticker) q.set("ticker", opts.ticker);
  if (opts.limit) q.set("limit", String(opts.limit));
  return api<News>(`/api/public/news?${q}`);
}
export const myNews = () => api<News>("/api/news/mine");
export const newsItem = (id: string) => api<NewsItem>(`/api/public/news/item?id=${encodeURIComponent(id)}`);

// Nothing refreshes the news on a timer. A page draws what is stored; when that is stale it asks
// for the refresh itself, waits for it and draws again. `draw` is told whether one is under way.
export async function watchNews(load: () => Promise<News>, draw: (n: News, refreshing: boolean) => void) {
  const first = await load();
  draw(first, first.stale);
  if (!first.stale) return;
  const done = await api<{ refreshed: boolean }>("/api/public/news/refresh", { method: "POST" }).catch(() => null);
  draw(done?.refreshed ? await load().catch(() => first) : first, false);
}

// Indices, rates, currencies and commodities are not stocks: no company page tools for them.
export const isEquity = (k: Kind) => k === "stock" || k === "etf";
