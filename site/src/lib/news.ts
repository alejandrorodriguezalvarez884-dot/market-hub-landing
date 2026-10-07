// How a news item is drawn, on the news page and wherever a few items are shown. A headline
// opens the item's own page on the portal, where its article is and, from there, its source. A
// headline of the press is the exception: nothing of it is here but the headline, so it opens at
// its publisher.
import { add, h, linkTo, svg } from "./dom";
import { timeAgo } from "./format";
import type { NewsItem } from "./market";
import covers from "./news-covers.json";
import { link } from "./site";
import { quoteHref } from "./widgets";

export const articleHref = (n: NewsItem) => link(`/news/article/?id=${encodeURIComponent(n.id)}`);

function linked(n: NewsItem, cls: string): HTMLElement {
  if (n.layer !== "press") return linkTo(articleHref(n), cls, n.title);
  if (!/^https?:\/\//.test(n.url ?? "")) return h("span", cls, n.title);
  const a = linkTo(n.url!, cls, n.title);
  a.target = "_blank";
  a.rel = "noopener";
  return a;
}

// The picture of an item: one from the library (covers/ draws it) for what the item touches and
// how it reads. Which of them is told by the item's id, so an item keeps its picture wherever it
// is shown. A headline of the press, which has neither a scope nor a reading, has none.
export function cover(n: NewsItem, small = false): string | null {
  const count = (covers as Record<string, Record<string, number>>)[n.scope ?? ""]?.[n.sentiment ?? ""] ?? 0;
  if (!count) return null;
  let turn = 0;
  for (const c of n.id) turn = (turn * 31 + c.charCodeAt(0)) >>> 0;
  return link(`/covers/news/${n.scope!.toLowerCase().replaceAll(" ", "-")}-${n.sentiment}-${(turn % count) + 1}${small ? "-s" : ""}.jpg`);
}

// A picture in its frame. It says nothing the text does not, so it has no words of its own.
export function picture(src: string, cls: string, alt = ""): HTMLImageElement {
  const img = h("img", `rounded-md bg-line object-cover ${cls}`);
  Object.assign(img, { src, alt, loading: "lazy", decoding: "async" });
  return img;
}

// How the news reads, drawn with the site's own mark: right of the line is bullish, left of it is
// bearish, on it is neutral. Nothing when nobody has said.
const TONES = { bullish: ["Bullish", "text-up", 1], bearish: ["Bearish", "text-down", -1], neutral: ["Neutral", "text-muted", 0] } as const;
export function tone(n: NewsItem): HTMLElement | null {
  const known = n.sentiment && TONES[n.sentiment];
  if (!known) return null;
  const [label, color, side] = known;
  const mark = svg("svg", { viewBox: "0 0 22 12", class: "h-3 w-[22px] flex-none", fill: "none", stroke: "currentColor", "stroke-width": 1.8, "stroke-linecap": "round", "aria-hidden": "true" });
  mark.append(svg("path", { d: `M11 1v10${side ? `M11 6h${side * 6}` : ""}` }), svg("circle", { cx: 11 + side * 7.5, cy: 6, r: 2.6, fill: "currentColor", stroke: "none" }));
  return add(h("span", `inline-flex items-center gap-1.5 font-medium ${color}`), mark, label);
}

// What it touches: a sector, or the economy as a whole.
const scope = (n: NewsItem) => (n.scope ? h("span", "chip !font-sans", n.scope) : null);

// When it was published, where it comes from, how it reads and what it touches. The owner chose
// not to say on the page how an item was written.
export function byline(n: NewsItem): HTMLElement {
  const el = add(h("p", "flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12.5px] text-muted"),
    h("time", "num", timeAgo(n.published_utc)), h("span", "", n.source), tone(n), scope(n));
  (el.firstChild as HTMLTimeElement).dateTime = n.published_utc;
  (el.firstChild as HTMLElement).title = new Date(n.published_utc).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
  return el;
}

export const tickers = (n: NewsItem) => (n.tickers.length ? add(h("p", "mt-2 flex flex-wrap gap-1.5"), ...n.tickers.slice(0, 6).map((t) => linkTo(quoteHref(t), "chip", t))) : null);

// A full item: byline, title, summary, the instruments it is about, and its picture beside them.
export function newsItem(n: NewsItem): HTMLElement {
  const src = cover(n, true);
  const shown = src ? add(linkTo(articleHref(n), "order-last flex-none self-start"), picture(src, "aspect-video w-24 sm:w-44")) : null;
  if (shown) (shown.tabIndex = -1), shown.setAttribute("aria-hidden", "true");
  return add(h("article", "flex gap-4 border-b border-line py-4 first:pt-1 sm:gap-6"),
    add(h("div", "min-w-0 flex-1"),
      byline(n),
      add(h("h3", "mt-1.5 max-w-[44rem] text-[1.0625rem] font-medium leading-snug text-ink-strong"), linked(n, "hover:underline")),
      n.summary ? h("p", "mt-1.5 max-w-[44rem] text-sm text-ink", n.summary) : null,
      tickers(n)),
    shown);
}

// A short one, for a side column: byline and title.
export function newsLine(n: NewsItem): HTMLElement {
  return add(h("article", "border-b border-line py-2.5 last:border-0"), byline(n),
    add(h("h3", "mt-1 text-sm leading-snug text-ink-strong"), linked(n, "hover:underline")));
}

// "Today", "Yesterday" or the date, in the reader's own time zone.
export function dayLabel(iso: string, now = new Date()): string {
  const d = new Date(iso);
  const days = Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() - new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()) / 86400000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
}

// The day an item belongs to, in the reader's own time zone, as YYYY-MM-DD: what the day filter
// of the news page compares.
export function dayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
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
