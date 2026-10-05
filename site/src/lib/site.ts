// Site-wide constants and links.
export const SITE_NAME = "Market Hub";
export const REPO_URL = "https://github.com/alejandrorodriguezalvarez884-dot/market-hub-landing";
export const AUTHOR_URL = "https://alejandrorodriguez.dev/";

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
