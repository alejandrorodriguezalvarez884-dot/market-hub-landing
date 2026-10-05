// Site-wide constants and links.
export const SITE_NAME = "Market Hub";
export const REPO_URL = "https://github.com/alejandrorodriguezalvarez884-dot/market-hub-landing";
export const AUTHOR_URL = "https://alejandrorodriguez.dev/";

// The analysis tools are sections of the portal on its subdomains: the header names them and a
// company's page links to the same company in each.
const site = (v: string | undefined, fallback: string) => (v ?? fallback).replace(/\/$/, "");
export const FUNDAMENTALS_URL = site(import.meta.env.PUBLIC_FUNDAMENTALS_URL, "https://fundamentals.themarkethub.app");
export const RADAR_URL = site(import.meta.env.PUBLIC_RADAR_URL, "https://radar.themarkethub.app");
export const fundamentalsUrl = (ticker: string) => `${FUNDAMENTALS_URL}/stock/?t=${encodeURIComponent(ticker)}`;
export const radarUrl = (ticker: string) => `${RADAR_URL}/analyze/?ticker=${encodeURIComponent(ticker)}`;

export function link(path: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}${path}`;
}

// Company names as the SEC writes them ("APPLE INC") read better in title case.
export function tidyName(name: string): string {
  if (name !== name.toUpperCase()) return name;
  const keep = new Set(["LLC", "PLC", "NV", "SA", "AG", "SE", "LP", "ETF", "REIT", "USA", "II", "III", "S&P"]);
  return name
    .toLowerCase()
    .split(/(\s+|-|\/)/)
    .map((w) => (keep.has(w.toUpperCase()) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join("")
    .replace(/\b(Inc|Corp|Co|Ltd)\b(?!\.)/g, "$1.");
}
