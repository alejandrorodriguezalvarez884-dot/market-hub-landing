// Pieces the pages of My Hub share: the page's head, the note that figures are sample ones, the
// sentences that read the portfolio back, and the small marks (a share of the whole, a place on
// a scale) that the tables are built from.
import { api } from "./api";
import { add, h, linkTo } from "./dom";
import { pct, signedPct } from "./format";
import { link } from "./site";
import type { Dashboard, Insights, N } from "./types";

export const tone = (v: N | undefined) => (v == null ? "text-ink" : v > 0 ? "up" : v < 0 ? "down" : "text-ink");
export const cell = (text: string, cls = "text-ink") => h("td", cls, text);
// A difference between two percentages is in points, not in percent.
export const points = (v: N | undefined, digits = 1) => (v == null ? "—" : `${v >= 0 ? "+" : "−"}${(Math.abs(v) * 100).toFixed(digits)} pts`);
export const ordinal = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th"}`;

// The provider did not answer: what is shown is sample data, and the page says so next to its title.
export function sampleNote(): HTMLElement {
  const el = h("span", "rounded-sm border border-warn/40 bg-warn-soft px-1.5 py-0.5 text-[12px] text-warn", "sample figures");
  el.title = "The market data provider is not answering: prices, returns and everything worked out from them are placeholders, not the market.";
  return el;
}

// The head of a page of My Hub: where you are, the page's title, a line under it, and what you can do.
export function pageHead(title: string, note: string, opts: { sample?: boolean; action?: HTMLElement | null } = {}): HTMLElement {
  return add(h("div", "flex flex-wrap items-end justify-between gap-3"),
    add(h("div", "min-w-0"),
      add(h("p", "label flex items-center gap-2"), "My Hub", opts.sample ? sampleNote() : null),
      h("h1", "mt-1 text-2xl font-bold text-ink-strong", title),
      h("p", "mt-0.5 max-w-2xl text-[13px] text-muted", note)),
    opts.action ?? null);
}

export const getDashboard = () => api<Dashboard>("/api/dashboard");

// --- The portfolio read back -------------------------------------------------------------------

const KINDS: Record<string, [string, string]> = {
  // what the sentence is about, and its mark: a few strokes in the manner of the site's own
  performance: ["Against the index", "M3 17l5-5 4 3 9-9M15 6h6v6"],
  concentration: ["Concentration", "M12 3v18M3 12h18M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0-8 0"],
  sector: ["Sectors", "M4 20V10m6 10V4m6 16v-8m4 8H2"],
  risk: ["How it moves", "M2 12h4l3-8 4 16 3-8h6"],
  geography: ["Where", "M12 21a9 9 0 1 0 0-18a9 9 0 0 0 0 18ZM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"],
  today: ["Today", "M12 7v5l3 2M12 21a9 9 0 1 0 0-18a9 9 0 0 0 0 18Z"],
  income: ["Dividends", "M12 21a9 9 0 1 0 0-18a9 9 0 0 0 0 18ZM14.5 9.5H11a1.25 1.25 0 0 0 0 2.5h2a1.25 1.25 0 0 1 0 2.5H9.5M12 8v8"],
};

function insightItem(kind: string, text: string): HTMLElement {
  const [label, mark] = KINDS[kind] ?? ["", ""];
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  for (const [k, v] of Object.entries({ viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.6", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" }))
    icon.setAttribute(k, v);
  icon.setAttribute("class", "h-4 w-4 flex-none text-muted");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", mark);
  icon.append(path);
  return add(h("div", "border-t border-line pt-3"),
    add(h("p", "label flex items-center gap-2"), icon, label),
    h("p", "mt-1.5 text-[15px] leading-relaxed text-ink", text));
}

// The sentences are there at once (the server writes them from the figures); the page then asks
// for the fuller reading and puts it in their place when it comes.
export function insightPanel(first: Insights): HTMLElement {
  const body = h("div", "transition-opacity duration-500");
  const draw = (said: Insights) => body.replaceChildren(
    h("p", "max-w-[46rem] text-[1.375rem] font-medium leading-snug tracking-tight text-ink-strong sm:text-[1.625rem]", said.headline),
    add(h("div", "mt-6 grid gap-x-10 gap-y-5 md:grid-cols-2"), ...said.items.map((i) => insightItem(i.kind, i.text))));
  draw(first);
  api<Insights>("/api/insights")
    .then((said) => {
      if (!said.written || !said.items.length) return;
      body.style.opacity = "0";
      setTimeout(() => (draw(said), (body.style.opacity = "1")), 320);
    })
    .catch(() => {});
  return add(h("section", "panel p-5 sm:p-7"), h("h2", "label mb-3", "Your portfolio, read back"), body);
}

// --- Marks -------------------------------------------------------------------------------------

// A share of the whole: a line as long as the share.
export function shareBar(weight: N | undefined, cls = "w-24"): HTMLElement {
  const fill = h("span", "block h-full rounded-full bg-ink-strong");
  fill.style.width = `${Math.max(1.5, Math.min(100, (weight ?? 0) * 100))}%`;
  const el = add(h("span", `inline-block h-[5px] rounded-full bg-raised align-middle ${cls}`), fill);
  el.setAttribute("aria-hidden", "true");
  return el;
}

// The parts of a whole on one line, the largest first and the lightest last.
export function stackedBar(parts: { label: string; weight: number }[]): HTMLElement {
  const el = h("div", "flex h-3 w-full gap-px overflow-hidden rounded-sm");
  el.setAttribute("role", "img");
  el.setAttribute("aria-label", parts.map((p) => `${p.label} ${pct(p.weight, 0)}`).join(", "));
  parts.forEach((p, i) => {
    const seg = h("span", "block h-full bg-ink-strong");
    seg.style.width = `${p.weight * 100}%`;
    seg.style.opacity = String(Math.max(0.16, 1 - i * (0.84 / Math.max(1, parts.length - 1)) * 0.92));
    seg.title = `${p.label} ${pct(p.weight)}`;
    el.append(seg);
  });
  return el;
}

// A figure and its tone, as a table cell.
export const moveCell = (v: N | undefined, digits = 1) => cell(signedPct(v, digits), `num ${tone(v)}`);

export const tickerChips = (tickers: string[], max = 8) => add(h("span", "flex flex-wrap gap-1"),
  ...tickers.slice(0, max).map((t) => linkTo(link(`/quote/?t=${encodeURIComponent(t)}`), "chip", t)),
  tickers.length > max ? h("span", "text-[12px] text-muted", `+${tickers.length - max}`) : null);

// Shown where a page needs positions and there are none.
export function empty(text: string): HTMLElement {
  return add(h("div", "panel p-8 text-center"), h("p", "text-ink", text),
    add(h("p", "mt-4"), linkTo(link("/portfolio/"), "btn btn-primary", "Add your positions")));
}

export function failure(root: HTMLElement, e: unknown) {
  root.replaceChildren(h("p", "rounded-md border border-down/40 bg-down-soft p-4 text-[13px] text-down", e instanceof Error ? e.message : "This page failed to load."));
}
