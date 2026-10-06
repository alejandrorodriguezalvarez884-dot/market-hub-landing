// Checks the rendered files as a browser will play them: that each one opens, how long it is,
// that it carries sound, and what a few of its frames look like (film/out/check-<format>.jpg).

import { createServer } from "node:http";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const here = dirname(fileURLToPath(import.meta.url));
const site = join(here, "..", "site", "public");
const types = { webm: "video/webm", mp4: "video/mp4" };

const server = createServer(async (req, res) => {
  const name = req.url.slice(1);
  if (name === "") return res.writeHead(200, { "content-type": "text/html" }).end("<!doctype html><title>check</title>");
  const type = types[name.split(".").pop()];
  if (!type || !/^film\.\w+$/.test(name)) return res.writeHead(404).end();
  try {
    res.writeHead(200, { "content-type": type }).end(await readFile(join(site, name)));
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));

const browser = await chromium.launch({ channel: process.env.FILM_BROWSER ?? "chrome", headless: true, args: ["--autoplay-policy=no-user-gesture-required"] });
try {
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await mkdir(join(here, "out"), { recursive: true });
  for (const format of Object.keys(types)) {
    const found = await page.evaluate(async ({ url, times }) => {
      const head = await fetch(url, { method: "GET" });
      if (!head.ok) return null;
      const bytes = await head.arrayBuffer();
      const video = document.createElement("video");
      video.src = URL.createObjectURL(new Blob([bytes], { type: head.headers.get("content-type") }));
      await new Promise((ok, bad) => { video.onloadedmetadata = ok; video.onerror = () => bad(new Error("the browser cannot open it")); });
      const board = document.createElement("canvas");
      board.width = 640 * 4;
      board.height = 360 * Math.ceil(times.length / 4);
      const b = board.getContext("2d");
      for (const [i, t] of times.entries()) {
        // The frame is on screen a moment after the seek is: wait for it, not for the seek.
        const shown = new Promise((ok) => { video.requestVideoFrameCallback(ok); setTimeout(ok, 1500); });
        video.currentTime = t;
        await shown;
        b.drawImage(video, (i % 4) * 640, Math.floor(i / 4) * 360, 640, 360);
      }
      const ac = new AudioContext();
      const sound = await ac.decodeAudioData(bytes.slice(0));
      let peak = 0, sum = 0;
      for (let ch = 0; ch < sound.numberOfChannels; ch++) for (const v of sound.getChannelData(ch)) (peak = Math.max(peak, Math.abs(v))), (sum += v * v);
      return {
        megabytes: +(bytes.byteLength / 1e6).toFixed(1), seconds: +video.duration.toFixed(2), size: `${video.videoWidth}x${video.videoHeight}`,
        sound: { seconds: +sound.duration.toFixed(2), channels: sound.numberOfChannels, rate: sound.sampleRate, peak: +peak.toFixed(3), rmsDb: +(10 * Math.log10(sum / (sound.length * sound.numberOfChannels))).toFixed(1) },
        sheet: board.toDataURL("image/jpeg", 0.9),
      };
    }, { url: `/film.${format}`, times: [3, 9.5, 14.5, 18, 22, 29, 34, 43, 50.5, 55, 58, 59.7] });
    if (!found) {
      console.log(`film.${format}: not there`);
      continue;
    }
    await writeFile(join(here, "out", `check-${format}.jpg`), Buffer.from(found.sheet.split(",")[1], "base64"));
    delete found.sheet;
    console.log(`film.${format}:`, JSON.stringify(found));
  }
} finally {
  await browser.close();
  server.close();
}
