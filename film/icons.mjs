// Draws the site's icon at the sizes browsers and search engines look for, from the one source
// of truth, site/public/favicon.svg:
//   favicon.ico           16, 32 and 48 px in one file, for whatever asks for /favicon.ico
//   favicon-192.png       the icon Google Search shows next to a result (a multiple of 48 px)
//   apple-touch-icon.png  180 px, square and opaque: iOS rounds the corners itself
//   logo.png              512 px, the Organization logo in the structured data
//
// It drives the Chrome installed on this machine, as share.mjs does (FILM_BROWSER=msedge for
// Edge), and writes into site/public.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const pub = join(here, "..", "site", "public");
const svg = readFileSync(join(pub, "favicon.svg"), "utf8");
const BACKGROUND = "#0b0c0d";

// The icon at `size` px; `opaque` fills the rounded corners with the background colour.
async function draw(page, size, opaque) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(`<!doctype html><html><head><style>
    html, body { margin: 0; width: ${size}px; height: ${size}px; background: ${opaque ? BACKGROUND : "transparent"}; }
    svg { display: block; width: ${size}px; height: ${size}px; }
  </style></head><body>${svg}</body></html>`);
  return page.screenshot({ type: "png", omitBackground: !opaque });
}

// An ICO that holds PNG images, which every browser since IE Vista reads.
function ico(images) {
  const header = Buffer.alloc(6 + 16 * images.length);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);
  let offset = header.length;
  images.forEach(({ size, png }, i) => {
    const at = 6 + 16 * i;
    header.writeUInt8(size >= 256 ? 0 : size, at);
    header.writeUInt8(size >= 256 ? 0 : size, at + 1);
    header.writeUInt8(0, at + 2);
    header.writeUInt8(0, at + 3);
    header.writeUInt16LE(1, at + 4);
    header.writeUInt16LE(32, at + 6);
    header.writeUInt32LE(png.length, at + 8);
    header.writeUInt32LE(offset, at + 12);
    offset += png.length;
  });
  return Buffer.concat([header, ...images.map((im) => im.png)]);
}

const browser = await chromium.launch({ channel: process.env.FILM_BROWSER ?? "chrome", headless: true });
try {
  const page = await browser.newPage();
  const small = [];
  for (const size of [16, 32, 48]) small.push({ size, png: await draw(page, size, false) });
  const files = {
    "favicon.ico": ico(small),
    "favicon-192.png": await draw(page, 192, false),
    "apple-touch-icon.png": await draw(page, 180, true),
    "logo.png": await draw(page, 512, true),
  };
  for (const [name, data] of Object.entries(files)) {
    writeFileSync(join(pub, name), data);
    console.log(join(pub, name));
  }
} finally {
  await browser.close();
}
