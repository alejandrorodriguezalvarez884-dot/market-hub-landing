// Renders the library of news covers into the site: site/public/covers/news/<scope>-<tone>-<n>.jpg
// (and a small <scope>-<tone>-<n>-s.jpg for the lists), and the index the site picks from
// (site/src/lib/news-covers.json).
//
//   node render.mjs                         every cover
//   node render.mjs --only Energy           the covers of one scope
//   node render.mjs --only Energy:bullish:1 one cover
//   node render.mjs --sheet                 also a contact sheet per scope in covers/out/, to look them over
//
// The scenes are drawn by the Chrome on this machine (FILM_BROWSER=msedge for Edge), with its
// software renderer when there is no graphics card: slower, and the same picture.

import { createServer } from "node:http";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, extname, join, normalize, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const target = join(here, "..", "site", "public", "covers", "news");
const index = join(here, "..", "site", "src", "lib", "news-covers.json");
const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript" };
const VIEWS = [1, 2];
const slug = (scope) => scope.toLowerCase().replaceAll(" ", "-");
const only = process.argv.includes("--only") ? process.argv[process.argv.indexOf("--only") + 1].split(":") : [];

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

const browser = await chromium.launch({ channel: process.env.FILM_BROWSER ?? "chrome", headless: true,
  args: ["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--use-angle=swiftshader"] });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  page.on("pageerror", (e) => console.error("page error:", e.message));
  page.on("console", (m) => m.type() === "error" && console.error("console:", m.text().slice(0, 200)));
  await page.goto(`http://127.0.0.1:${server.address().port}/covers.html`);
  await page.waitForFunction(() => window.covers);
  const { scopes, tones } = await page.evaluate(() => ({ scopes: window.covers.scopes, tones: window.covers.tones }));
  await mkdir(target, { recursive: true });
  for (const scope of scopes) {
    if (only[0] && only[0] !== scope) continue;
    const made = [];
    for (const view of VIEWS) for (const tone of tones) {
      if ((only[1] && only[1] !== tone) || (only[2] && +only[2] !== view)) continue;
      const started = Date.now();
      const [data, small] = await page.evaluate(([s, t, v]) => window.covers.make(s, t, v), [scope, tone, view]);
      const name = `${slug(scope)}-${tone}-${view}.jpg`;
      await writeFile(join(target, name), Buffer.from(data.split(",")[1], "base64"));
      await writeFile(join(target, name.replace(".jpg", "-s.jpg")), Buffer.from(small.split(",")[1], "base64"));
      made.push(data);
      console.log(`  ${name}  ${((Date.now() - started) / 1000).toFixed(1)}s`);
    }
    if (process.argv.includes("--sheet") && made.length) {
      // The covers of a scope on one image, three tones across and its two views down.
      const sheet = await page.evaluate(async (images) => {
        const c = document.createElement("canvas");
        c.width = 640 * 3;
        c.height = 360 * Math.ceil(images.length / 3);
        const g = c.getContext("2d");
        for (const [i, src] of images.entries()) {
          const img = new Image();
          img.src = src;
          await img.decode();
          g.drawImage(img, (i % 3) * 640, Math.floor(i / 3) * 360, 640, 360);
        }
        return c.toDataURL("image/jpeg", 0.88);
      }, made);
      await mkdir(join(here, "out"), { recursive: true });
      await writeFile(join(here, "out", `${slug(scope)}.jpg`), Buffer.from(sheet.split(",")[1], "base64"));
    }
  }
  // How many covers there are of each kind: all the site needs to know to pick one.
  const files = new Set(await readdir(target));
  const counts = Object.fromEntries(scopes.map((scope) => [scope, Object.fromEntries(tones.map((tone) =>
    [tone, VIEWS.filter((v) => files.has(`${slug(scope)}-${tone}-${v}.jpg`)).length]))]));
  await writeFile(index, JSON.stringify(counts, null, 2) + "\n");
  console.log(`index: ${Object.values(counts).reduce((n, c) => n + Object.values(c).reduce((a, b) => a + b, 0), 0)} covers`);
} finally {
  await browser.close();
  server.close();
}
