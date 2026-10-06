// Every news cover on one sheet (covers/out/overview-<n>.jpg), to look the library over at a glance:
// a row per scope, its two views of each tone across.   node overview.mjs [width of a cover]

import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, "..", "site", "public", "covers", "news");
const width = +(process.argv[2] ?? 320), height = Math.round((width * 9) / 16);
const files = (await readdir(source)).filter((f) => f.endsWith(".jpg") && !f.endsWith("-s.jpg")).sort();
const scopes = [...new Set(files.map((f) => f.replace(/-(bullish|bearish|neutral)-\d\.jpg$/, "")))];
const rows = scopes.map((scope) => ["bullish", "bearish", "neutral"].flatMap((tone) => [1, 2].map((n) => `${scope}-${tone}-${n}.jpg`)));

const browser = await chromium.launch({ channel: process.env.FILM_BROWSER ?? "chrome", headless: true });
try {
  const page = await browser.newPage();
  await mkdir(join(here, "out"), { recursive: true });
  for (let part = 0; part * 6 < rows.length; part++) {
    const images = [];
    for (const row of rows.slice(part * 6, part * 6 + 6)) for (const name of row)
      images.push(files.includes(name) ? `data:image/jpeg;base64,${(await readFile(join(source, name))).toString("base64")}` : null);
    const sheet = await page.evaluate(async ([images, w, h]) => {
      const c = document.createElement("canvas");
      c.width = w * 6;
      c.height = h * Math.ceil(images.length / 6);
      const g = c.getContext("2d");
      for (const [i, src] of images.entries()) {
        if (!src) continue;
        const img = new Image();
        img.src = src;
        await img.decode();
        g.drawImage(img, (i % 6) * w, Math.floor(i / 6) * h, w, h);
      }
      return c.toDataURL("image/jpeg", 0.85);
    }, [images, width, height]);
    await writeFile(join(here, "out", `overview-${part + 1}.jpg`), Buffer.from(sheet.split(",")[1], "base64"));
  }
  console.log(`${rows.length} scopes on ${Math.ceil(rows.length / 6)} sheets`);
} finally {
  await browser.close();
}
