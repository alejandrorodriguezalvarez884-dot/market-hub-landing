// Number formatting, in the page's language. Every formatter takes null and returns an em dash for
// it. English "$1.2B", "+30.5%", "Nov 4, 2026"; Spanish "1,2 mil M$", "+30,5 %", "4 nov 2026"
// (docs/i18n.md). In Spanish the space before a unit is a non-breaking one, so "%" or "$" never
// ends up alone on the next line.
import { lang, locale } from "../i18n";

export type N = number | null | undefined;
const DASH = "—";
const NB = String.fromCharCode(160); // a non-breaking space
const ok = (v: N): v is number => typeof v === "number" && Number.isFinite(v);
const es = () => lang() === "es";
// A number with a fixed count of decimals and the page's decimal mark (no thousands separator).
const fixed = (v: number, digits: number) => (es() ? v.toFixed(digits).replace(".", ",") : v.toFixed(digits));
// A number with the page's separators.
const grouped = (v: number, min: number, max = min) => v.toLocaleString(locale(), { minimumFractionDigits: min, maximumFractionDigits: max });
const percent = () => (es() ? `${NB}%` : "%");

export function money(v: N, digits = 1): string {
  if (!ok(v)) return DASH;
  const a = Math.abs(v);
  const sign = v < 0 ? "−" : "";
  if (es()) {
    // Spanish: millones (M), miles de millones (mil M), billones (bill.), the dollar after.
    if (a >= 1e12) return `${sign}${fixed(a / 1e12, digits + 1)}${NB}bill.${NB}$`;
    if (a >= 1e9) return `${sign}${fixed(a / 1e9, digits)}${NB}mil${NB}M$`;
    if (a >= 1e6) return `${sign}${fixed(a / 1e6, digits)}${NB}M$`;
    if (a >= 1e3) return `${sign}${fixed(a / 1e3, digits)}${NB}mil${NB}$`;
    return `${sign}${fixed(a, 2)}${NB}$`;
  }
  if (a >= 1e12) return `${sign}$${(a / 1e12).toFixed(digits + 1)}T`;
  if (a >= 1e9) return `${sign}$${(a / 1e9).toFixed(digits)}B`;
  if (a >= 1e6) return `${sign}$${(a / 1e6).toFixed(digits)}M`;
  if (a >= 1e3) return `${sign}$${(a / 1e3).toFixed(digits)}K`;
  return `${sign}$${a.toFixed(2)}`;
}

export function price(v: N): string {
  if (!ok(v)) return DASH;
  return es() ? `${grouped(v, 2)}${NB}$` : `$${grouped(v, 2)}`;
}

export function pct(v: N, digits = 1, signed = false): string {
  if (!ok(v)) return DASH;
  const s = fixed(v * 100, digits);
  return `${signed && v > 0 ? "+" : ""}${s.replace("-", "−")}${percent()}`;
}

export const signedPct = (v: N, digits = 1) => pct(v, digits, true);

export function mult(v: N, digits = 1): string {
  return ok(v) ? `${fixed(v, digits)}×` : DASH;
}

export function num(v: N, digits = 2): string {
  return ok(v) ? grouped(v, 0, digits) : DASH;
}

export function count(v: N): string {
  return ok(v) ? grouped(Math.round(v), 0) : DASH;
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  // Spanish "4 nov 2026": the short month without its full stop.
  if (es()) return d.toLocaleDateString("es-ES", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }).replace(".", "");
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
}

// The formatter for each kind of figure, so tables and charts agree.
export type Kind = "money" | "pct" | "spct" | "mult" | "num" | "price" | "count";
export function fmt(kind: Kind, v: N): string {
  switch (kind) {
    case "money":
      return money(v);
    case "pct":
      return pct(v);
    case "spct":
      return signedPct(v);
    case "mult":
      return mult(v);
    case "price":
      return price(v);
    case "count":
      return count(v);
    default:
      return num(v);
  }
}

// A quote in its own unit: dollars for stocks and commodities, points for indices, a yield for
// rates, four decimals for currency pairs.
export function level(v: N, kind: string): string {
  if (!ok(v)) return DASH;
  if (kind === "rate") return `${fixed(v, 3)}${percent()}`;
  if (kind === "fx") return fixed(v, v < 10 ? 4 : 2);
  const s = grouped(v, 2);
  if (kind === "stock" || kind === "etf") return es() ? `${s}${NB}$` : `$${s}`;
  return s;
}

export function change(v: N, kind: string): string {
  if (!ok(v)) return DASH;
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  const a = Math.abs(v);
  return `${sign}${kind === "fx" && a < 1 ? fixed(a, 4) : grouped(a, 2)}`;
}

export function compact(v: N): string {
  if (!ok(v)) return DASH;
  const a = Math.abs(v);
  if (es()) {
    if (a >= 1e9) return `${fixed(v / 1e9, 2)}${NB}mil${NB}M`;
    if (a >= 1e6) return `${fixed(v / 1e6, 2)}${NB}M`;
    if (a >= 1e3) return `${fixed(v / 1e3, 1)}${NB}mil`;
    return String(Math.round(v));
  }
  if (a >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(Math.round(v));
}

export function timeAgo(iso: string, now = Date.now()): string {
  const m = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
  const hrs = Math.round(m / 60);
  const d = Math.round(hrs / 24);
  if (es()) {
    if (m < 1) return "ahora mismo";
    if (m < 60) return `hace ${m} min`;
    if (hrs < 24) return `hace ${hrs} h`;
    return `hace ${d} d`;
  }
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (hrs < 24) return `${hrs}h ago`;
  return `${d}d ago`;
}

// "3 stocks" / "3 acciones": the count and the right form of the word, given in the page's language.
export const plural = (n: number, one: string, many = `${one}s`) => `${count(n)} ${n === 1 ? one : many}`;

export const toneClass = (v: N) => (ok(v) ? (v > 0 ? "up" : v < 0 ? "down" : "text-muted") : "text-muted");
