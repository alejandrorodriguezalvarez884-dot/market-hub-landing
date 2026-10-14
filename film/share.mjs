// Draws the picture a shared link to the site shows (Open Graph and Twitter Card, 1200 x 630):
// the mark, the name, what the site is, and its address, as the film ends. It is the picture of
// every page that has none of its own; an opinion article shows its cover instead.
//
// It drives the Chrome installed on this machine, as render.mjs does (FILM_BROWSER=msedge for
// Edge), and writes site/public/share.png.

import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "..", "site", "public", "share.png");

const card = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans:wght@400;600&display=block" rel="stylesheet">
<style>
  html, body { margin: 0; width: 1200px; height: 630px; background: #0b0c0d; color: #f2f0ea; }
  body { display: flex; flex-direction: column; align-items: center; justify-content: center; font-family: "IBM Plex Sans", sans-serif; }
  .brand { display: flex; align-items: center; gap: 36px; }
  .brand svg { width: 132px; height: 132px; }
  .name { font-size: 92px; font-weight: 600; letter-spacing: -0.02em; }
  .what { margin-top: 44px; font-size: 40px; color: #c9c7c1; }
  .where { margin-top: 28px; font-family: "IBM Plex Mono", monospace; font-size: 26px; color: #8c8b86; }
</style></head><body>
  <div class="brand">
    <svg viewBox="0 0 20 20" fill="none" stroke="#f2f0ea" stroke-width="2" stroke-linecap="round"><path d="M4 2v16M4 10h8"/><circle cx="14.5" cy="10" r="2.75" fill="#f2f0ea" stroke="none"/></svg>
    <span class="name">The Market Hub</span>
  </div>
  <p class="what">Your portfolio, read by AI.</p>
  <p class="where">themarkethub.app</p>
</body></html>`;

const browser = await chromium.launch({ channel: process.env.FILM_BROWSER ?? "chrome", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 630 } });
  await page.setContent(card, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: out, type: "png" });
  console.log(out);
} finally {
  await browser.close();
}
