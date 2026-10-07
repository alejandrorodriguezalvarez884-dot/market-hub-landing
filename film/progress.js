// A second cut of the film, to a solemn score that keeps moving forward (progress-audio.js): the
// same pictures as film.js, moved onto its pulse. Nothing of film.js is redrawn here. Its clock is
// bent instead: every moment the picture marks (a row landing, a headline arriving, a part
// opening) is given a place on the score's grid, and the film runs faster or slower in between to
// get there on time. Over that, the frame leans on the great drum, and a line along the bottom
// carries the dot from the first part to the last.

import { DURATION, EVENTS as PLAYED, H, T, W, draw as plain } from "./film.js";

export { DURATION, FPS, H, W } from "./film.js";

// The grid: 128 pulses a minute, in bars of four, thirty-two of them in the film's sixty seconds.
// The score is felt at half of that, slow and wide; the pulse is what the low strings bow.
export const BPM = 128;
export const BEAT = 60 / BPM;
export const BAR = 4 * BEAT;
export const BARS = Math.round(DURATION / BAR);
const EIGHTH = BEAT / 2, SIXTEENTH = BEAT / 4;
// The second a beat falls on: bars count from 0, beats within a bar from 1.
export const at = (bar, beat = 1) => bar * BAR + (beat - 1) * BEAT;

// --- The score's plan, which the picture follows -------------------------------------------------

// The bar each part opens on.
export const PARTS = { intro: 0, today: 4, lede: 6, markets: 8, news: 12, hub: 16, year: 19, tools: 22, jobs: 25, outro: 28, name: 29 };

// The harmony, a bar each: the bass note and the chord, low, as MIDI numbers. The bass climbs,
// D, F, B flat, C, and starts again from D: each turn is a step up, and the last one comes home to F.
const Dm = { bass: 38, notes: [50, 57, 62, 65] }, F = { bass: 41, notes: [53, 57, 60, 65] };
const Bb = { bass: 46, notes: [53, 58, 62, 65] }, C = { bass: 48, notes: [52, 55, 60, 67] };
export const HARMONY = [
  Dm, Dm, Dm, Dm,          // the mark: one low note, and the strings begin to bow
  Dm, Dm, F, F,            // Today
  Bb, Bb, C, C,            // Markets
  Dm, Dm, F, F,            // News
  Bb, Bb, C, C, Dm, C,     // My Hub: the horns take the tune
  Dm, Dm, F, F,            // the tools
  Bb, C,                   // the climb
  C, F, F, F,              // the mark again, and home
];

// How much of the orchestra plays in a bar, from 0 to 1: the film grows as it goes.
export const drive = (bar) => (bar < 4 ? 0.2 + bar * 0.08 : bar < 8 ? 0.55 : bar < 12 ? 0.7 : bar < 16 ? 0.75 : bar < 22 ? 0.9 : bar < 28 ? 1 : bar < 29 ? 0.8 : 1);

// The beats of a bar the great drum falls on: seldom at first, then closer. The picture leans on
// the same list.
export function drum(bar) {
  if (bar < 2 || bar > 29) return [];
  if (bar < 8) return [1];
  if (bar < 16) return [1, 3];
  if (bar < 22) return [1, 2.5, 3];
  if (bar < 28) return [1, 2.5, 3, 4];
  return [1];
}

// Where a part lands with everything at once: [bar, weight].
export const HITS = [[4, 0.6], [8, 0.8], [12, 0.6], [16, 1], [22, 0.9], [28, 0.7], [29, 1.2]];

// --- The clock, bent ------------------------------------------------------------------------------

// Moments of film.js and the beat each one is moved to: [second there, second here]. The parts
// open on a bar; inside the opening, each move of the dot lands on a beat.
const PLACED = [
  [0, 0], [1.62, at(1)], [3.08, at(1, 4)], [4.38, at(2, 3)], [5.48, at(3)], [6.9, at(PARTS.today)],
  [T.lede, at(PARTS.lede)], [T.markets, at(PARTS.markets)], [T.news, at(PARTS.news)], [T.hub, at(PARTS.hub)], [36.2, at(PARTS.year)],
  [T.tools, at(PARTS.tools)], [47.1, at(PARTS.jobs)], [T.outro, at(PARTS.outro)], [54.45, at(PARTS.name)], [DURATION, DURATION],
];

function between(pairs, value, from, to) {
  let i = 1;
  while (i < pairs.length - 1 && pairs[i][from] < value) i++;
  const [a, b] = [pairs[i - 1], pairs[i]];
  const k = (value - a[from]) / (b[from] - a[from]);
  return a[to] + (b[to] - a[to]) * Math.min(1, Math.max(0, k));
}

// Every note the picture plays gets the nearest free place on the grid: an eighth note when one
// is near, else a sixteenth. A place is taken only if the film does not have to run at more than
// twice its pace, or less than half of it, to reach it.
export const ANCHORS = (() => {
  const struck = [...new Set(PLAYED.filter((e) => e.kind === "pluck" || e.kind === "tick").map((e) => e.t))].sort((a, b) => a - b);
  const out = [];
  let next = 0;  // the placed moment still ahead
  let last = PLACED[0];
  out.push(last);
  for (const there of struck) {
    while (next < PLACED.length - 1 && PLACED[next][0] <= there + 0.05) {
      if (PLACED[next][0] > last[0]) out.push((last = PLACED[next]));
      next++;
    }
    if (there - last[0] < 0.05) continue;  // struck with the one before: they move together
    const ahead = PLACED[next];
    const guess = between(PLACED, there, 0, 1);
    const snap = (grid) => Math.round(guess / grid) * grid;
    const free = (here) => here > last[1] + 1e-6 && here < ahead[1] - SIXTEENTH / 2 && Math.abs(here - guess) <= 0.15;
    const pace = (here) => (there - last[0]) / (here - last[1]);
    const here = [snap(EIGHTH), snap(SIXTEENTH), (Math.floor(last[1] / SIXTEENTH + 1e-6) + 1) * SIXTEENTH].find((c) => free(c) && pace(c) > 0.5 && pace(c) < 2);
    if (here !== undefined) out.push((last = [there, here]));
  }
  for (; next < PLACED.length; next++) if (PLACED[next][0] > last[0]) out.push((last = PLACED[next]));
  return out;
})();

// A second of this cut, as a second of film.js; and back.
export const toFilm = (t) => between(ANCHORS, t, 1, 0);
export const toCut = (t) => between(ANCHORS, t, 0, 1);

// What the picture plays, at this cut's times.
export const EVENTS = PLAYED.map((e) => ({ ...e, t: toCut(e.t), ...(e.length ? { length: toCut(e.t + e.length) - toCut(e.t) } : {}) }));

// --- The frame --------------------------------------------------------------------------------------

const clamp = (v) => Math.min(1, Math.max(0, v));

// How hard the last stroke of the drum still pushes, and the last landing, each from 1 down to 0.
function push(t) {
  const bar = Math.floor(t / BAR);
  let beat = 0, landing = 0;
  for (const b of [bar - 1, bar]) for (const n of drum(b)) if (t >= at(b, n)) beat = Math.max(beat, Math.exp(-(t - at(b, n)) * 6));
  for (const [b, weight] of HITS) if (t >= at(b)) landing = Math.max(landing, weight * Math.exp(-(t - at(b)) * 4.5));
  return [beat, landing];
}

// The line the film travels: the logo's own figure, a stem from a start and a dot at its end,
// drawn along the bottom from the first part to the last, with a mark where each part opens.
const ROAD = { y: 1058, x0: 140, x1: 1780, from: at(PARTS.today), to: at(PARTS.outro) };
function road(ctx, t, beat) {
  const shown = Math.min(clamp((t - ROAD.from + 0.4) / 0.4), 1 - clamp((t - ROAD.to + 0.6) / 0.5));
  if (shown <= 0) return;
  const xAt = (time) => ROAD.x0 + ((ROAD.x1 - ROAD.x0) * (time - ROAD.from)) / (ROAD.to - ROAD.from);
  const x = xAt(Math.min(ROAD.to, Math.max(ROAD.from, t)));
  const stroke = (x0, y0, x1, y1, color, width) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.lineCap = "round";
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
  };
  ctx.save();
  ctx.globalAlpha = shown;
  stroke(ROAD.x0, ROAD.y, ROAD.x1, ROAD.y, "#222528", 2);
  for (const part of ["markets", "news", "hub", "tools", "outro"]) {
    const px = xAt(at(PARTS[part]));
    stroke(px, ROAD.y - 7, px, ROAD.y + 7, px <= x ? "#8c8b86" : "#3a3e42", 2);
  }
  stroke(ROAD.x0, ROAD.y, x, ROAD.y, "#f2f0ea", 3);
  ctx.fillStyle = "#f2f0ea";
  ctx.beginPath();
  ctx.arc(x, ROAD.y, 7 + 4 * beat, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export function draw(ctx, t) {
  const [beat, landing] = push(t);
  // The whole frame swells a little on the drum, and more where a part lands.
  const scale = 1 + 0.007 * beat + 0.022 * landing;
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(scale, scale);
  ctx.translate(-W / 2, -H / 2);
  plain(ctx, toFilm(t));
  ctx.restore();
  ctx.globalAlpha = 1;
  if (landing > 0.02) {
    ctx.save();
    ctx.globalAlpha = 0.06 * Math.min(1, landing);
    ctx.fillStyle = "#f2f0ea";
    ctx.fillRect(0, 0, W, H);
    ctx.restore();
  }
  road(ctx, t, beat);
}
