// How a news item is drawn, on the news page and wherever a few items are shown.
import { add, h, linkTo } from "./dom";
import { timeAgo } from "./format";
import type { NewsItem } from "./market";
import { link } from "./site";
import { quoteHref } from "./widgets";

// The item's own address: a document or an article opens in a new tab, a page of the portal in
// this one. Anything that is neither is not linked.
function linked(n: NewsItem, cls: string): HTMLElement {
  const url = n.url ?? "";
  if (url.startsWith("/")) return linkTo(link(url), cls, n.title);
  if (!/^https?:\/\//.test(url)) return h("span", cls, n.title);
  const a = linkTo(url, cls, n.title);
  a.target = "_blank";
  a.rel = "noopener";
  return a;
}

// When it was published and where it comes from. The owner chose not to say on the page how an
// item was written.
function byline(n: NewsItem): HTMLElement {
  const el = add(h("p", "flex flex-wrap items-baseline gap-x-2 text-[12.5px] text-muted"),
    h("time", "num", timeAgo(n.published_utc)), h("span", "", n.source));
  (el.firstChild as HTMLTimeElement).dateTime = n.published_utc;
  (el.firstChild as HTMLElement).title = new Date(n.published_utc).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
  return el;
}

const chips = (n: NewsItem) => (n.tickers.length ? add(h("p", "mt-2 flex flex-wrap gap-1.5"), ...n.tickers.slice(0, 6).map((t) => linkTo(quoteHref(t), "chip", t))) : null);

// A full item: byline, title, summary, the instruments it is about.
export function newsItem(n: NewsItem): HTMLElement {
  return add(h("article", "border-b border-line py-4 first:pt-1"),
    byline(n),
    add(h("h3", "mt-1 max-w-[44rem] text-[1.0625rem] font-medium leading-snug text-ink-strong"), linked(n, "hover:underline")),
    n.summary ? h("p", "mt-1.5 max-w-[44rem] text-sm text-ink", n.summary) : null,
    chips(n));
}

// A short one, for a side column: byline and title.
export function newsLine(n: NewsItem): HTMLElement {
  return add(h("article", "border-b border-line py-2.5 last:border-0"), byline(n),
    add(h("h3", "mt-0.5 text-sm leading-snug text-ink-strong"), linked(n, "hover:underline")));
}

// "Today", "Yesterday" or the date, in the reader's own time zone.
export function dayLabel(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const days = Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() - new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

// Items under a heading per day, newest day first (they arrive newest first).
export function byDay(items: NewsItem[]): HTMLElement[] {
  const out: HTMLElement[] = [];
  let label = "";
  for (const n of items) {
    const day = dayLabel(n.published_utc);
    if (day !== label) out.push(h("h2", "mt-8 text-[13px] text-muted first:mt-0", (label = day)));
    out.push(newsItem(n));
  }
  return out;
}
