// Site-wide constants and links.
// The name of the site, wherever it is named: the mark at the top of every page, titles, shared
// links, search engines.
export const SITE_NAME = "The Market Hub";
export const AUTHOR_URL = "https://alejandrorodriguez.dev/";
// Where readers reach us: published on /contact/, which the app and its store pages link to.
export const CONTACT_EMAIL = "alejandrorodriguezalvarez884@gmail.com";

// The analysis tools are sections of the portal on its subdomains: the header names them and a
// company's page links to the same company in each.
const site = (v: string | undefined, fallback: string) => (v ?? fallback).replace(/\/$/, "");
export const FUNDAMENTALS_URL = site(import.meta.env.PUBLIC_FUNDAMENTALS_URL, "https://fundamentals.themarkethub.app");
export const RADAR_URL = site(import.meta.env.PUBLIC_RADAR_URL, "https://radar.themarkethub.app");
export const PEERS_URL = site(import.meta.env.PUBLIC_PEERS_URL, "https://peers.themarkethub.app");
export const PLAYGROUND_URL = site(import.meta.env.PUBLIC_PLAYGROUND_URL, "https://playground.themarkethub.app");
export const OPTIONS_URL = site(import.meta.env.PUBLIC_OPTIONS_URL, "https://options.themarkethub.app");
// The bot competition has its own site: the kit, the keys and the whole board are there.
export const BOT_LEAGUE_URL = site(import.meta.env.PUBLIC_BOT_LEAGUE_URL, "https://bots.themarkethub.app");
// The phone app's page on the App Store: where the iPhone app is downloaded from.
export const APP_STORE_URL = "https://apps.apple.com/app/id6822290220";
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
