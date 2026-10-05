// Pieces shared by the public pages: quote rows, change pills, headlines, sectors and movers.
import { add, h, linkTo } from "./dom";
import { change, compact, level, signedPct, timeAgo, toneClass } from "./format";
import type { Mover, NewsItem, Sector, Snapshot } from "./market";
import { link } from "./site";
import { sparkline } from "./spark";

export const quoteHref = (symbol: string) => link(`/quote/?t=${encodeURIComponent(symbol)}`);

export function pill(v: number | null | undefined, digits = 2): HTMLElement {
  return h("span", typeof v === "number" && v < 0 ? "pill-down" : "pill-up", signedPct(v, digits));
}

// A compact row for side lists: name and symbol, last price, change.
export function quoteRow(s: Snapshot, onPick?: (s: Snapshot) => void): HTMLElement {
  const el = onPick ? h("button", "w-full text-left") : linkTo(quoteHref(s.symbol), "block");
  if (onPick) {
    (el as HTMLButtonElement).type = "button";
    el.addEventListener("click", () => onPick(s));
  }
  el.className += " grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 rounded px-2 py-1.5 hover:bg-raised";
  el.dataset.symbol = s.symbol;
  return add(el,
    add(h("span", "min-w-0"), h("span", "block truncate text-[13px] font-semibold text-ink-strong", s.name), h("span", "block text-[11px] text-muted", s.symbol)),
    h("span", "num text-right text-[13px] text-ink", level(s.price, s.kind)),
    pill(s.change_pct));
}

export function quoteGroup(title: string, items: Snapshot[], onPick?: (s: Snapshot) => void): HTMLElement {
  return add(h("div", "py-2"), h("div", "label px-2 pb-1", title), ...items.map((s) => quoteRow(s, onPick)));
}

// A table of instruments with returns over several periods.
export function quoteTable(items: Snapshot[]): HTMLElement {
  const t = h("table", "data-table");
  const head = ["Name", "Last", "Change", "Chg %", "1 month", "YTD", "1 year", "30 days"];
  add(t, add(h("thead"), add(h("tr"), ...head.map((x) => h("th", "", x)))),
    add(h("tbody"), ...items.map((s) => {
      const tr = add(h("tr", "row-link"),
        add(h("td"), linkTo(quoteHref(s.symbol), "font-semibold text-ink-strong hover:text-[#5b8cff]", s.name), h("div", "text-[11px] text-muted", s.symbol)),
        h("td", "text-ink-strong", level(s.price, s.kind)),
        h("td", toneClass(s.change), change(s.change, s.kind)),
        add(h("td"), pill(s.change_pct)),
        h("td", toneClass(s.return_1m), signedPct(s.return_1m)),
        h("td", toneClass(s.return_ytd), signedPct(s.return_ytd)),
        h("td", toneClass(s.return_1y), signedPct(s.return_1y)),
        add(h("td"), sparkline(s.spark, 88, 26)));
      tr.addEventListener("click", (e) => !(e.target as Element).closest("a") && (location.href = quoteHref(s.symbol)));
      return tr;
    })));
  return add(h("div", "overflow-x-auto"), t);
}

export function moversTable(items: Mover[]): HTMLElement {
  const t = h("table", "data-table");
  add(t, add(h("thead"), add(h("tr"), ...["Stock", "Price", "Chg %", "Volume"].map((x) => h("th", "", x)))),
    add(h("tbody"), ...items.map((m) => {
      const tr = add(h("tr", "row-link"),
        add(h("td"), linkTo(quoteHref(m.symbol), "font-semibold text-ink-strong hover:text-[#5b8cff]", m.symbol),
          h("div", "max-w-[10rem] truncate text-[11px] text-muted", m.name)),
        h("td", "text-ink", level(m.price, m.kind)),
        add(h("td"), pill(m.change_pct)),
        h("td", "text-muted", compact(m.volume)));
      tr.addEventListener("click", (e) => !(e.target as Element).closest("a") && (location.href = quoteHref(m.symbol)));
      return tr;
    })));
  return add(h("div", "overflow-x-auto"), t);
}

// Tabs over a few views of the same panel (gainers, losers, most active...).
export function tabbed(views: { label: string; render: () => HTMLElement }[], initial = 0): { tabs: HTMLElement; body: HTMLElement } {
  const tabs = h("div", "tabs");
  tabs.setAttribute("role", "tablist");
  const body = h("div");
  const show = (i: number) => {
    tabs.querySelectorAll("button").forEach((b, j) => b.setAttribute("aria-selected", String(i === j)));
    body.replaceChildren(views[i].render());
  };
  views.forEach((v, i) => {
    const b = h("button", "tab-btn", v.label);
    b.type = "button";
    b.setAttribute("role", "tab");
    b.addEventListener("click", () => show(i));
    tabs.append(b);
  });
  show(initial);
  return { tabs, body };
}

// Sectors as diverging bars around zero, sorted by the day's move.
export function sectorBars(sectors: Sector[]): HTMLElement {
  const sorted = [...sectors].sort((a, b) => b.change_pct - a.change_pct);
  const max = Math.max(...sorted.map((s) => Math.abs(s.change_pct)), 0.001);
  return add(h("div", "space-y-1.5"), ...sorted.map((s) => {
    const bar = h("div", `absolute top-0 h-full rounded-sm ${s.change_pct >= 0 ? "bg-up/70 left-1/2" : "bg-down/70 right-1/2"}`);
    bar.style.width = `${(Math.abs(s.change_pct) / max) * 50}%`;
    return add(h("div", "grid grid-cols-[9.5rem_minmax(0,1fr)_3.75rem] items-center gap-2 text-xs"),
      h("span", "truncate text-ink", s.name),
      add(h("div", "relative h-3.5 rounded-sm bg-raised/60"), h("div", "absolute left-1/2 top-0 h-full w-px bg-line-strong"), bar),
      h("span", `num text-right font-semibold ${toneClass(s.change_pct)}`, signedPct(s.change_pct, 2)));
  }));
}

// Sectors as a heatmap of tiles, coloured by the day's move.
export function heatmap(sectors: Sector[]): HTMLElement {
  const shade = (v: number) => {
    const a = Math.min(1, Math.abs(v) / 0.02);
    return v >= 0 ? `rgba(8,153,129,${0.18 + a * 0.7})` : `rgba(242,54,69,${0.18 + a * 0.7})`;
  };
  return add(h("div", "grid grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-4"), ...[...sectors].sort((a, b) => b.change_pct - a.change_pct).map((s) => {
    const tile = add(h("div", "flex min-h-[84px] flex-col justify-between rounded p-3"),
      h("span", "text-[13px] font-semibold text-white", s.name),
      add(h("div", "flex items-end justify-between gap-2"),
        h("span", "num text-lg font-bold text-white", signedPct(s.change_pct, 2)),
        h("span", "num text-[11px] text-white/75", `YTD ${signedPct(s.return_ytd)}`)));
    tile.style.background = shade(s.change_pct);
    return tile;
  }));
}

export function newsRow(n: NewsItem, opts: { summary?: boolean } = {}): HTMLElement {
  return add(h("article", "group border-b border-line py-3 last:border-0"),
    add(h("div", "mb-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted"),
      h("span", "font-semibold uppercase tracking-wide text-[#5b8cff]", n.category), h("span", "", "·"), h("span", "", n.source), h("span", "", "·"),
      h("time", "", timeAgo(n.published_utc))),
    h("h3", "text-[14px] font-semibold leading-snug text-ink-strong", n.title),
    opts.summary ? h("p", "mt-1 text-[13px] leading-relaxed text-muted", n.summary) : null,
    n.tickers.length ? add(h("div", "mt-2 flex flex-wrap gap-1"), ...n.tickers.map((t) => linkTo(quoteHref(t), "chip", t))) : null);
}

export function newsFeature(n: NewsItem): HTMLElement {
  return add(h("article", "relative self-start overflow-hidden rounded-md border border-line bg-gradient-to-br from-[#1b2a52] via-panel to-panel p-5"),
    add(h("div", "mb-2 flex items-center gap-2 text-[11px] text-muted"),
      h("span", "rounded bg-accent px-1.5 py-0.5 font-semibold uppercase tracking-wide text-white", n.category),
      h("span", "", n.source), h("span", "", "·"), h("time", "", timeAgo(n.published_utc))),
    h("h2", "text-xl font-bold leading-snug text-ink-strong sm:text-2xl", n.title),
    h("p", "mt-2 max-w-2xl text-[14px] leading-relaxed text-ink", n.summary),
    n.tickers.length ? add(h("div", "mt-3 flex flex-wrap gap-1"), ...n.tickers.map((t) => linkTo(quoteHref(t), "chip", t))) : null);
}

export function failed(el: HTMLElement, text = "Not available right now.") {
  el.replaceChildren(h("p", "p-4 text-sm text-muted", text));
}
