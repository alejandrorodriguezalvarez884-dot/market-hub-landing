// Renders the film (film.js, audio.js) into the site: film.webm, film.mp4 when this Chrome can
// encode it, and the poster. `--stills` writes contact sheets and loudness figures to film/out/
// instead, to look the film over without rendering it.
//
// It drives the Chrome installed on this machine (FILM_BROWSER=msedge for Edge): the page draws
// each frame and Chrome encodes it, so there is no video tool to install.

import { createServer } from "node:http";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
// `--cut=adventure` renders that cut instead, as a trial: into film/out/, not into the site.
const cut = process.argv.find((a) => a.startsWith("--cut="))?.slice(6) ?? "";
const site = cut ? join(here, "out") : join(here, "..", "site", "public");
const name = cut ? `film-${cut}` : "film";
const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript" };

const server = createServer(async (req, res) => {
  const path = normalize(join(here, decodeURIComponent(new URL(req.url, "http://x").pathname)));
  if (!path.startsWith(here + sep) || !types[extname(path)]) return res.writeHead(404).end();
  try {
    res.writeHead(200, { "content-type": types[extname(path)] }).end(await readFile(path));
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));

const browser = await chromium.launch({ channel: process.env.FILM_BROWSER ?? "chrome", headless: true });
try {
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.error("page error:", e.message));
  await mkdir(site, { recursive: true });
  await page.goto(`http://127.0.0.1:${server.address().port}/film.html${cut ? `?cut=${cut}` : ""}`);
  await page.waitForFunction(() => window.film);  // a cut is loaded before the page says what it can do
  await page.evaluate(() => window.film.ready);
  const save = async (path, dataUrl) => writeFile(path, Buffer.from(dataUrl.split(",")[1], "base64"));

  if (process.argv.includes("--stills")) {
    const out = join(here, "out");
    await mkdir(out, { recursive: true });
    // A frame every two seconds, twelve to a sheet, and the moments in between parts.
    const every = Array.from({ length: 30 }, (_, i) => i * 2 + 1);
    const turns = [0.9, 1.9, 2.7, 4.1, 5.3, 6.3, 6.8, 11.5, 15.4, 15.7, 19.9, 23.5, 31.1, 39.1, 46.6, 52.6, 53.4, 54.2, 54.8, 56.5, 58.5, 59.6];
    const sheets = { "sheet-1": every.slice(0, 12), "sheet-2": every.slice(12, 24), "sheet-3": every.slice(24), "sheet-turns-1": turns.slice(0, 12), "sheet-turns-2": turns.slice(12) };
    const tag = cut ? `${cut}-` : "";
    for (const [sheet, times] of Object.entries(sheets)) await save(join(out, `${tag}${sheet}.jpg`), await page.evaluate((t) => window.film.sheet(t), times));
    for (const t of (process.env.FILM_FRAMES ?? "").split(",").filter(Boolean).map(Number)) await save(join(out, `${tag}frame-${t}.png`), await page.evaluate((s) => window.film.still(s), t));
    const sound = await page.evaluate(() => window.film.listen());
    await writeFile(join(out, `${tag}sound.json`), JSON.stringify(sound));
    console.log(`stills in ${out}; soundtrack ${sound.seconds}s, peak ${sound.peak}`);
  } else {
    for (const format of ["webm", "mp4"]) {
      const started = Date.now();
      const made = await page.evaluate((f) => window.film.encode(f), format);
      if (made.skipped) {
        console.log(`${name}.${format}: skipped, ${made.skipped}`);
        continue;
      }
      await writeFile(join(site, `${name}.${format}`), Buffer.from(made.base64, "base64"));
      console.log(`${name}.${format}: ${(made.bytes / 1e6).toFixed(1)} MB in ${Math.round((Date.now() - started) / 1000)} s`);
    }
    await save(join(site, `${name}-poster.jpg`), await page.evaluate(() => window.film.still(58.2, "image/jpeg", 0.88)));
    console.log(`${name}-poster.jpg`);
  }
} finally {
  await browser.close();
  server.close();
}
