// What the film's page can do: play the film for someone watching, and, for render.mjs, hand
// over stills, the poster and the encoded files. The encoding is Chrome's own (WebCodecs), so no
// video tool has to be installed.

import { Muxer as Mp4Muxer, ArrayBufferTarget as Mp4Target } from "./node_modules/mp4-muxer/build/mp4-muxer.mjs";
import { Muxer as WebmMuxer, ArrayBufferTarget as WebmTarget } from "./node_modules/webm-muxer/build/webm-muxer.mjs";
import { RATE, levels, score as firstScore } from "./audio.js";
import { DURATION, FPS, H, W, draw as firstDraw } from "./film.js";

// Another cut of the film, asked for in the address (film.html?cut=adventure): the same pictures
// to another score, each with its own drawing and its own sound.
const CUTS = { adventure: ["./adventure.js", "./adventure-audio.js"] };
const cut = CUTS[new URLSearchParams(location.search).get("cut") ?? ""];
const [picture, cutSound] = cut ? await Promise.all(cut.map((file) => import(file))) : [null, null];
const draw = picture?.draw ?? firstDraw;
const score = cutSound?.score ?? firstScore;

const canvas = document.getElementById("stage");
const ctx = canvas.getContext("2d");
const FRAMES = DURATION * FPS;

// The film is set in the site's two typefaces. A frame drawn before they arrive would fall back
// to another font without saying so.
const FACES = ['400 30px "IBM Plex Sans"', '500 30px "IBM Plex Sans"', '600 30px "IBM Plex Sans"', '400 30px "IBM Plex Mono"', '500 30px "IBM Plex Mono"'];
const ready = (async () => {
  await Promise.all(FACES.map((face) => document.fonts.load(face, "Market Hub 0123456789 −%")));
  const missing = FACES.filter((face) => !document.fonts.check(face));
  if (missing.length) throw new Error(`fonts not loaded: ${missing.join(", ")}`);
})();

function base64(buffer) {
  const bytes = new Uint8Array(buffer);
  let out = "";
  for (let i = 0; i < bytes.length; i += 0x8000) out += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(out);
}

async function still(t, type = "image/png", quality) {
  await ready;
  draw(ctx, t);
  return canvas.toDataURL(type, quality);
}

// Several moments on one image, each with its second, to look over the film at a glance.
async function sheet(times, columns = 3) {
  await ready;
  const [w, h] = [640, 360];
  const board = document.createElement("canvas");
  board.width = w * columns;
  board.height = h * Math.ceil(times.length / columns);
  const b = board.getContext("2d");
  times.forEach((t, i) => {
    draw(ctx, t);
    const [x, y] = [(i % columns) * w, Math.floor(i / columns) * h];
    b.drawImage(canvas, x, y, w, h);
    b.fillStyle = "#e0b341";
    b.font = '500 18px "IBM Plex Mono"';
    b.fillText(`${t.toFixed(2)}s`, x + 10, y + 24);
    b.strokeStyle = "#3a3e42";
    b.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
  });
  return board.toDataURL("image/jpeg", 0.9);
}

const FORMATS = {
  webm: {
    video: { codec: "vp09.00.40.08", bitrate: 2_600_000 },
    audio: { codec: "opus", bitrate: 128_000 },
    muxer: (target) => new WebmMuxer({ target, video: { codec: "V_VP9", width: W, height: H, frameRate: FPS }, audio: { codec: "A_OPUS", numberOfChannels: 2, sampleRate: RATE } }),
    target: () => new WebmTarget(),
  },
  // For the browsers that do not play WebM (older Safari on iOS).
  mp4: {
    video: { codec: "avc1.640028", bitrate: 3_200_000, avc: { format: "avc" } },
    audio: { codec: "mp4a.40.2", bitrate: 128_000 },
    muxer: (target) => new Mp4Muxer({ target, video: { codec: "avc", width: W, height: H, frameRate: FPS }, audio: { codec: "aac", numberOfChannels: 2, sampleRate: RATE }, fastStart: "in-memory" }),
    target: () => new Mp4Target(),
  },
};

let scored;
const soundtrack = () => (scored ??= score());

async function encode(format) {
  await ready;
  const f = FORMATS[format];
  const videoConfig = { ...f.video, width: W, height: H, framerate: FPS, latencyMode: "quality" };
  const audioConfig = { ...f.audio, sampleRate: RATE, numberOfChannels: 2 };
  if (!(await VideoEncoder.isConfigSupported(videoConfig)).supported) return { skipped: `this browser does not encode ${f.video.codec}` };
  if (!(await AudioEncoder.isConfigSupported(audioConfig)).supported) return { skipped: `this browser does not encode ${f.audio.codec}` };
  const target = f.target();
  const muxer = f.muxer(target);
  let failed = null;
  const fail = (e) => (failed ??= e);

  const video = new VideoEncoder({ output: (chunk, meta) => muxer.addVideoChunk(chunk, meta), error: fail });
  video.configure(videoConfig);
  for (let i = 0; i < FRAMES && !failed; i++) {
    draw(ctx, i / FPS);
    const frame = new VideoFrame(canvas, { timestamp: Math.round((i * 1e6) / FPS), duration: Math.round(1e6 / FPS) });
    video.encode(frame, { keyFrame: i % (FPS * 3) === 0 });
    frame.close();
    while (video.encodeQueueSize > 4) await new Promise((r) => setTimeout(r, 4));
  }
  await video.flush();
  video.close();

  const sound = await soundtrack();
  const audio = new AudioEncoder({ output: (chunk, meta) => muxer.addAudioChunk(chunk, meta), error: fail });
  audio.configure(audioConfig);
  const [left, right] = [sound.getChannelData(0), sound.getChannelData(1)];
  for (let at = 0; at < left.length && !failed; at += RATE) {
    const n = Math.min(RATE, left.length - at);
    const data = new Float32Array(n * 2);
    data.set(left.subarray(at, at + n), 0);
    data.set(right.subarray(at, at + n), n);
    const block = new AudioData({ format: "f32-planar", sampleRate: RATE, numberOfFrames: n, numberOfChannels: 2, timestamp: Math.round((at / RATE) * 1e6), data });
    audio.encode(block);
    block.close();
  }
  await audio.flush();
  audio.close();
  if (failed) throw failed;
  muxer.finalize();
  return { base64: base64(target.buffer), bytes: target.buffer.byteLength };
}

// How loud the soundtrack is, second by second, and whether it ever reaches full scale.
async function listen() {
  const sound = await soundtrack();
  let peak = 0;
  for (const ch of [0, 1]) for (const v of sound.getChannelData(ch)) peak = Math.max(peak, Math.abs(v));
  // The pad alone and the played notes alone, before the final gain: which one carries the mix.
  const [pad, played] = [await score({ pad: true }), await score({ played: true })];
  const heard = { seconds: sound.duration, peak: Math.round(peak * 1000) / 1000, rms: levels(sound), pad: levels(pad), played: levels(played) };
  return cutSound?.balance ? { ...heard, balance: await cutSound.balance(sound) } : heard;
}

window.film = { ready, still, sheet, encode, listen };

// Played by hand: the same frames against the clock, with the same soundtrack.
document.getElementById("play").addEventListener("click", async (e) => {
  e.target.disabled = true;
  await ready;
  const ac = new AudioContext({ sampleRate: RATE });
  const src = ac.createBufferSource();
  src.buffer = await soundtrack();
  src.connect(ac.destination);
  const from = ac.currentTime + 0.1;
  src.start(from);
  const clock = document.getElementById("clock");
  const tick = () => {
    const t = ac.currentTime - from;
    if (t >= DURATION) return ac.close(), (e.target.disabled = false);
    if (t >= 0) draw(ctx, t), (clock.textContent = `${t.toFixed(1)} s`);
    requestAnimationFrame(tick);
  };
  tick();
});
ready.then(() => draw(ctx, 3.3));
