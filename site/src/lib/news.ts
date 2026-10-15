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
export type Sentiment = keyof typeof TONES;
export const SENTIMENTS = Object.keys(TONES) as Sentiment[];
export const tone = (n: NewsItem): HTMLElement | null => (n.sentiment && TONES[n.sentiment] ? toneMark(n.sentiment) : null);

// The mark and its word alone: what an item carries, and what the news page's filter is chosen by.
export function toneMark(sentiment: Sentiment): HTMLElement {
  const [label, color, side] = TONES[sentiment];
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

// A card of the news feed: its picture, byline, title, summary and the instruments it is about.
// The whole card opens the item; the instruments keep their own links above it. The card that
// leads its day is wider, with its picture beside the text.
export function feedCard(n: NewsItem, lead = false): HTMLElement {
  const small = cover(n, true);
  let frame: HTMLElement | null = null;
  if (small) {
    const img = picture(small, `aspect-video w-full !rounded-none ${lead ? "sm:aspect-auto sm:h-full sm:min-h-56" : ""}`);
    img.srcset = `${small} 480w, ${cover(n)} 1280w`;
    img.sizes = lead ? "(min-width: 1024px) 420px, (min-width: 640px) 55vw, 100vw" : "(min-width: 1024px) 340px, (min-width: 640px) 45vw, 100vw";
    frame = add(h("div", `feed-frame flex-none overflow-hidden ${lead ? "sm:w-[56%]" : ""}`), img);
  }
  const shown = tickers(n);
  shown?.classList.add("relative", "z-10");
  return add(h("article", `feed-card group relative flex flex-col overflow-hidden rounded-md border border-line bg-panel transition-colors hover:border-line-strong ${lead ? "sm:col-span-2 sm:flex-row" : ""}`),
    frame,
    add(h("div", `flex min-w-0 flex-1 flex-col p-4 ${lead ? "sm:justify-center sm:p-6" : ""}`),
      byline(n),
      add(h("h3", lead ? "mt-2 text-[1.25rem] font-medium leading-tight tracking-tight text-ink-strong sm:text-[1.5rem]" : "mt-2 text-[1.0625rem] font-medium leading-snug text-ink-strong"),
        linked(n, "after:absolute after:inset-0 group-hover:underline")),
      n.summary ? h("p", `mt-2 text-sm text-ink ${lead ? "line-clamp-4" : "line-clamp-3"}`, n.summary) : null,
      shown));
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
