// The film on the landing page: a minute of drawing, with no recording of the site in it.
//
// It starts from the logo, which is the site's own figure (a zero line and a move to its
// right), and turns that mark into the day's market, and then into what My Hub holds: your own
// portfolio and the five AI tools, each named and shown at its job. It ends on the way in: the
// logo, "powered by AI", and the button that opens My Hub. `draw(ctx, t)` paints the frame at
// second `t`; EVENTS lists what happens when, so the soundtrack (audio.js) is played by the
// picture. Every figure on screen is an illustration, the same in every render.

export const W = 1920;
export const H = 1080;
export const FPS = 30;
export const DURATION = 60;

// The site's colours (site/src/styles/global.css). Green and red only ever mean a move.
const C = {
  page: "#0b0c0d", ink: "#c9c7c1", strong: "#f2f0ea", muted: "#8c8b86", faint: "#5f5f5b",
  line: "#222528", lineStrong: "#3a3e42", up: "#35c98f", down: "#ff6b57",
};
const SANS = '"IBM Plex Sans", system-ui, sans-serif';
const MONO = '"IBM Plex Mono", ui-monospace, monospace';
const LEFT = 140, RIGHT = 1780;  // the margins everything sits between

// When each part starts, in seconds. My Hub and the reading of the tools were drawn on a longer
// film's clock (T); they are played SHIFT seconds earlier in this one (NOW).
export const T = { intro: 0, today: 6.5, lede: 11.6, markets: 15.5, news: 23.5, hub: 31, tools: 41.5, outro: 52.5, end: DURATION };
export const NOW = { intro: 0, today: 6.5, hub: 11.6, tools: 22.1, named: 27.7, home: 47.5, outro: 52.5, end: DURATION };
const SHIFT = T.hub - NOW.hub;

// --- Time and number helpers -------------------------------------------------------------------

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, k) => a + (b - a) * k;
const prog = (t, a, b) => clamp((t - a) / (b - a));
const out3 = (k) => 1 - (1 - k) ** 3;
const inOut = (k) => (k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2);
const back = (k) => 1 + 2.9 * (k - 1) ** 3 + 1.9 * (k - 1) ** 2;
// 0 before a, up to 1 at b, down from c to 0 at d.
const span = (t, a, b, c, d) => Math.min(prog(t, a, b), 1 - prog(t, c, d));

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let x = Math.imul(s ^ (s >>> 15), 1 | s);
    x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
    return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
  };
}

const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
function mix(a, b, k) {
  const [x, y] = [rgb(a), rgb(b)];
  return `rgb(${x.map((v, i) => Math.round(lerp(v, y[i], clamp(k)))).join(",")})`;
}
const tone = (v) => (v > 0 ? C.up : v < 0 ? C.down : C.muted);
const signed = (v, digits = 2) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(digits)}%`;
const money = (v) => `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// --- Drawing helpers ---------------------------------------------------------------------------

function face(ctx, o) {
  ctx.font = `${o.weight ?? 400} ${o.size ?? 36}px ${o.mono ? MONO : SANS}`;
  ctx.letterSpacing = `${o.ls ?? (o.mono ? -0.03 : -0.012) * (o.size ?? 36)}px`;
}

function width(ctx, s, o = {}) {
  face(ctx, o);
  return ctx.measureText(s).width;
}

function text(ctx, s, x, y, o = {}) {
  face(ctx, o);
  ctx.fillStyle = o.color ?? C.ink;
  ctx.textAlign = o.align ?? "left";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(s, x, y);
  return ctx.measureText(s).width;
}

function seg(ctx, x0, y0, x1, y1, color, w = 2, dash = null) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = w;
  ctx.lineCap = "round";
  if (dash) ctx.setLineDash(dash);
  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.lineTo(x1, y1);
  ctx.stroke();
  ctx.restore();
}

function dot(ctx, x, y, r, color) {
  if (r <= 0) return;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}

function bar(ctx, x, y, w, h, color, radius = h / 2) {
  if (w <= 0 || h <= 0) return;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, Math.min(radius, w / 2, h / 2));
  ctx.fill();
}

// Paint with an opacity on top of whatever opacity is already in force.
function faded(ctx, alpha, paint) {
  if (alpha <= 0.002) return;
  ctx.save();
  ctx.globalAlpha *= clamp(alpha);
  paint();
  ctx.restore();
}

// The mark itself: a stem from a zero line to a dot. Left of zero is down, right is up.
function move(ctx, zeroX, y, px, color, r = 12, stem = 4) {
  seg(ctx, zeroX, y, zeroX + px, y, color, stem);
  dot(ctx, zeroX + px, y, r, color);
}

// Each part opens the same way: its name, and one line on what it is.
const TITLE = { size: 84, weight: 500, color: C.strong };
function title(ctx, t, s, from, to) {
  faded(ctx, span(t, from, from + 0.5, to - 0.4, to), () =>
    text(ctx, s, LEFT, 250 + (1 - out3(prog(t, from, from + 0.6))) * 20, { ...TITLE, size: Math.min(TITLE.size, (TITLE.size * (RIGHT - LEFT)) / width(ctx, s, TITLE)) }));
}
function heading(ctx, t, from, to, label, line) {
  const a = span(t, from + 0.3, from + 0.8, to - 0.6, to - 0.2);
  faded(ctx, a, () => text(ctx, label, LEFT, 144, { size: 36, color: C.muted }));
  title(ctx, t, line, from + 0.3, to - 0.2);
  return a;
}

// --- The dot between parts ---------------------------------------------------------------------

// When a part ends, what is on screen gives way to the dot, which travels to where the next part
// begins: [time, from, to]. The first leaves from the ruler's first row, for the lock's keyhole;
// the next from My Hub for the dot that reads; then on to the tools, into My Hub's window, and to
// the logo.
const TRAVELS = [
  [NOW.hub, [1326, 420], [330, 706]],
  [NOW.tools, [RIGHT, 900], [800, 680]],
  [NOW.named, [800, 680], [1360, 610]],
  [NOW.home, [1360, 610], [1146, 410]],
  [NOW.outro, [1380, 650], [960, 470]],
];

function travel(ctx, t) {
  for (const [at, from, to] of TRAVELS) {
    const a = span(t, at - 0.55, at - 0.3, at + 0.45, at + 0.65);
    if (a <= 0) continue;
    const place = (time) => {
      const k = inOut(prog(time, at - 0.3, at + 0.45));
      return [lerp(from[0], to[0], k), lerp(from[1], to[1], k)];
    };
    const [x, y] = place(t);
    const [px, py] = place(t - 0.05);
    faded(ctx, a, () => {
      faded(ctx, 0.55, () => seg(ctx, px, py, x, y, C.strong, 6));  // its stem, behind it
      dot(ctx, x, y, 13, C.strong);
    });
  }
}

// --- 1. The mark, and 2. Today -----------------------------------------------------------------

const RULER = [
  ["S&P 500", "5,712.40", 0.0087], ["Nasdaq 100", "20,104.55", 0.012], ["Dow Jones", "42,310.80", -0.001],
  ["Gold", "2,655.10", 0.0065], ["Crude oil", "71.24", -0.018], ["EUR/USD", "1.0915", -0.0021], ["Bitcoin", "64,210.00", 0.024],
];
const ZERO_X = 1230, ROW_Y = 420, ROW_H = 80, HALF = 330, SCALE = 0.03;  // the ruler: ±3% over ±330 px
const rowTime = (i) => 7.2 + i * 0.36;
const rulerPx = (v) => clamp(v / SCALE, -1, 1) * HALF;

// The logo, large, and then the same mark as the first row of the ruler.
function leadMark(ctx, t) {
  const big = { x: 960, y: 480, half: 208, lineW: 42, r: 71, reach: 273, stem: 42 };
  const grow = out3(prog(t, 0.4, 1.4));
  if (grow <= 0) return;
  // The dot: on the line, out to the right, across to the left, and back.
  let side = inOut(prog(t, 2.3, 3.1));
  side -= 2 * inOut(prog(t, 3.6, 4.4));
  side += 2 * inOut(prog(t, 4.7, 5.5));
  const color = t < 4.5 ? mix(C.strong, C.down, prog(t, 3.9, 4.1)) : mix(C.down, C.up, prog(t, 5.0, 5.2));
  // From the logo to a row of the ruler.
  const k = inOut(prog(t, 5.9, 7.0));
  const x = lerp(big.x, ZERO_X, k);
  const y = lerp(big.y, ROW_Y, k);
  const top = lerp(big.y - big.half * grow, ROW_Y - 52, k);
  const bottom = lerp(big.y + big.half * grow, ROW_Y + ROW_H * (RULER.length - 1) + 52, k);
  seg(ctx, x, top, x, bottom, mix(C.strong, C.lineStrong, k), lerp(big.lineW, 2.5, k));
  const r = lerp(big.r, 12, k) * back(prog(t, 1.6, 2.05));
  if (r <= 0) return;
  move(ctx, x, y, lerp(big.reach * side, rulerPx(RULER[0][2]), k), color, r, lerp(big.stem, 4, k));
}

function intro(ctx, t) {
  const say = (s, a, b, c, d) => faded(ctx, span(t, a, b, c, d), () => text(ctx, s, 960, 900, { size: 60, align: "center" }));
  say("This is zero.", 0.9, 1.3, 2.1, 2.4);
  say("This is a move.", 2.6, 3.0, 3.4, 3.7);
  say("Left is down.", 3.9, 4.2, 4.6, 4.85);
  say("Right is up.", 5.1, 5.4, 5.9, 6.2);
}

function today(ctx, t) {
  faded(ctx, span(t, T.today + 0.3, T.today + 0.8, T.markets - 0.6, T.markets - 0.2), () => text(ctx, "Today", LEFT, 144, { size: 36, color: C.muted }));
  title(ctx, t, "Every move of the day, on one scale.", T.today + 0.3, T.lede - 0.1);
  title(ctx, t, "And where the market is, right now.", T.lede + 0.1, T.markets - 0.2);

  faded(ctx, 1 - prog(t, T.lede - 0.5, T.lede - 0.1), () => {
    leadMark(ctx, t);
    faded(ctx, prog(t, 7.0, 7.5), () => {
      const axis = { size: 26, mono: true, color: C.muted, align: "center" };
      text(ctx, "−3%", ZERO_X - HALF, 338, axis);
      text(ctx, "0", ZERO_X, 338, axis);
      text(ctx, "+3%", ZERO_X + HALF, 338, axis);
    });
    RULER.forEach(([name, level, v], i) => {
      const at = i ? rowTime(i) : 6.9;
      const y = ROW_Y + i * ROW_H;
      const grow = i ? out3(prog(t, at + 0.05, at + 0.6)) : 1;
      faded(ctx, prog(t, at, at + 0.3), () => {
        text(ctx, name, LEFT, y + 15, { size: 42, color: C.strong });
        text(ctx, level, 800, y + 12, { size: 34, mono: true, align: "right" });
        text(ctx, signed(v * grow), RIGHT, y + 13, { size: 36, mono: true, align: "right", color: tone(v) });
        if (i) move(ctx, ZERO_X, y, rulerPx(v) * grow, tone(v));
      });
    });
  });
}

// --- 5. My Hub: your own portfolio -------------------------------------------------------------

const HELD = [
  ["AAPL", "Apple Inc.", 18144.0, 0.0081], ["MSFT", "Microsoft Corp.", 14612.5, -0.0042],
  ["KO", "Coca-Cola Co.", 6417.0, 0.0031], ["SPY", "SPDR S&P 500 ETF", 9037.05, 0.0086],
];
const heldTime = (i) => 33.8 + i * 0.28;
const YEAR = [36.6, 38.7];  // when the year of the portfolio is drawn
// A year of the holdings and of the index, both from the same start. Shapes, not anybody's returns.
const [MINE, INDEX] = [[11, 0.0105], [12, 0.0085]].map(([seed, drift]) => {
  const r = rng(seed);
  const path = [0];
  for (let i = 1; i < 60; i++) path.push(path[i - 1] + (r() - 0.5) * 0.05 + drift);
  return path;
});
const OWN_NEWS = ["AAPL", "KO", "MSFT"].map((ticker, i) => { const r = rng(70 + i); return [ticker, 0.7 + r() * 0.3, 0.35 + r() * 0.4]; });
const ownNewsTime = (i) => 38.9 + i * 0.4;

function hub(ctx, t) {
  faded(ctx, span(t, T.hub + 0.3, T.hub + 0.8, T.tools - 0.6, T.tools - 0.2), () => text(ctx, "My Hub", LEFT, 144, { size: 36, color: C.muted }));
  title(ctx, t, "Your own portfolio, on a private page.", T.hub + 0.3, 36.0);
  title(ctx, t, "Its value, its moves, its news. Only yours.", 36.2, T.tools - 0.2);
  faded(ctx, span(t, T.hub + 0.3, T.hub + 0.8, T.tools - 0.6, T.tools - 0.2), () => {
    // A lock, drawn around the dot: the dot and its stem are the keyhole.
    ctx.strokeStyle = C.strong;
    ctx.lineWidth = 10;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    faded(ctx, prog(t, 31.7, 32.2), () => { ctx.beginPath(); ctx.roundRect(226, 626, 208, 178, 22); ctx.stroke(); });
    const closing = out3(prog(t, 32.0, 32.8));
    if (closing > 0) {
      ctx.beginPath();
      ctx.moveTo(268, 626);
      ctx.lineTo(268, lerp(626, 584, clamp(closing * 5)));
      if (closing > 0.2) ctx.arc(330, 584, 62, Math.PI, Math.PI + Math.PI * clamp((closing - 0.2) / 0.6));
      if (closing > 0.8) ctx.lineTo(392, lerp(584, 626, (closing - 0.8) * 5));
      ctx.stroke();
    }
    seg(ctx, 330, 706, 330, 706 + 38 * prog(t, 31.6, 32.0), C.strong, 10);
    dot(ctx, 330, 706, 17, C.strong);
    faded(ctx, prog(t, 33.0, 33.5), () => text(ctx, "Only you see it.", 330, 892, { size: 38, color: C.muted, align: "center" }));

    // What it is worth, and what it did today.
    const counted = out3(prog(t, 32.1, 33.8));
    faded(ctx, prog(t, 31.9, 32.3), () => {
      text(ctx, "Portfolio value", 640, 436, { size: 36, color: C.muted });
      text(ctx, money(48210.55 * counted), 632, 572, { size: 140, mono: true, color: C.strong, ls: -7 });
    });
    faded(ctx, prog(t, 33.5, 33.9), () => text(ctx, "+$590.38 (+1.24%) today", 640, 644, { size: 42, mono: true, color: C.up }));

    // Each position, with its move of the day on the same ruler as everything else.
    faded(ctx, 1 - prog(t, 35.9, 36.3), () => {
      faded(ctx, prog(t, 33.7, 34.1), () => seg(ctx, 1600, 700, 1600, 986, C.lineStrong, 2.5));
      HELD.forEach(([ticker, name, value, v], i) => {
        const at = heldTime(i);
        const y = 736 + i * 74;
        const grow = out3(prog(t, at + 0.05, at + 0.6));
        faded(ctx, prog(t, at, at + 0.3), () => {
          text(ctx, ticker, 640, y + 13, { size: 40, mono: true, color: C.strong });
          text(ctx, name, 800, y + 12, { size: 34, color: C.muted });
          text(ctx, money(value), 1430, y + 12, { size: 34, mono: true, align: "right" });
          move(ctx, 1600, y, (v / 0.012) * 90 * grow, tone(v), 10, 4);
          text(ctx, signed(v * grow), RIGHT, y + 12, { size: 30, mono: true, align: "right", color: tone(v) });
        });
      });
    });

    // Then its year against the index, and the news of the companies in it.
    faded(ctx, prog(t, 36.3, 36.7), () => {
      const [x0, x1, y0, y1] = [640, 1180, 770, 980];
      const [low, high] = [Math.min(...MINE, ...INDEX), Math.max(...MINE, ...INDEX)];
      const upTo = out3(prog(t, YEAR[0], YEAR[1])) * (MINE.length - 1);
      const line = (path, color, w) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = w;
        ctx.lineJoin = "round";
        ctx.beginPath();
        let end = [x0, y1];
        for (let j = 0; j <= Math.floor(upTo); j++) {
          end = [x0 + (j / (path.length - 1)) * (x1 - x0), y1 - ((path[j] - low) / (high - low)) * (y1 - y0)];
          j ? ctx.lineTo(...end) : ctx.moveTo(...end);
        }
        ctx.stroke();
        dot(ctx, end[0], end[1], w * 2.2, color);
      };
      seg(ctx, x0, y1 + 8, x1, y1 + 8, C.line, 2);
      line(INDEX, C.faint, 3);
      line(MINE, C.strong, 4.5);
      dot(ctx, 650, 706, 8, C.strong);
      const w = text(ctx, "Your holdings", 670, 716, { size: 30, color: C.strong });
      dot(ctx, 700 + w, 706, 8, C.faint);
      text(ctx, "S&P 500, one year", 720 + w, 716, { size: 30, color: C.muted });
    });
    faded(ctx, prog(t, 38.6, 39.0), () => {
      text(ctx, "News on your stocks", 1290, 716, { size: 34, weight: 600, color: C.strong });
      seg(ctx, 1290, 740, RIGHT, 740, C.lineStrong, 2);
    });
    OWN_NEWS.forEach(([ticker, first, second], i) => {
      const at = ownNewsTime(i);
      const y = 772 + i * 76;
      faded(ctx, prog(t, at, at + 0.3), () => {
        const cw = width(ctx, ticker, { size: 26, mono: true }) + 26;
        ctx.strokeStyle = C.lineStrong;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(1290, y, cw, 38, 4);
        ctx.stroke();
        text(ctx, ticker, 1303, y + 28, { size: 26, mono: true, color: C.ink });
        bar(ctx, 1400, y + 4, 380 * first * out3(prog(t, at, at + 0.5)), 13, "rgba(201,199,193,0.36)");
        bar(ctx, 1400, y + 26, 380 * second * out3(prog(t, at + 0.1, at + 0.6)), 13, "rgba(201,199,193,0.18)");
      });
    });
  });
}

// --- 6. The tools ------------------------------------------------------------------------------

// The film names no tool: they change. It shows what they are: something is read, a question is
// answered, and each tool is made for one job.
const DOC = (() => { const r = rng(55); return Array.from({ length: 15 }, (_, i) => (i % 5 === 4 ? 0.45 + r() * 0.2 : 0.8 + r() * 0.2)); })();
const SCAN = [42.5, 45.6], SCAN_Y = [456, 966];
const lineY = (i) => 478 + i * 32;
const CORE = [800, 680];  // where the dot sits while it reads
const ASKED = [["What do the numbers say?", 3], ["What did the company just say?", 7], ["What changed since last time?", 11]]
  .map(([question, line], i) => { const r = rng(120 + i); return { question, line, first: 0.75 + r() * 0.25, second: 0.4 + r() * 0.4 }; });
// A question is answered when the reading reaches its line.
const askedTime = ({ line }) => lerp(SCAN[0], SCAN[1], (lineY(line) - SCAN_Y[0]) / (SCAN_Y[1] - SCAN_Y[0]));
const JOBS = ["Numbers", "Filings", "Valuation", "Comparison", "More to come"];
const JOBS_AT = 47.1;
const jobTime = (i) => JOBS_AT + 0.4 + [2, 1, 0, 1, 2][i] * 0.28 + (i > 2 ? 0.14 : 0);  // from the middle outwards
const jobX = (i) => 300 + i * 330;
const JOB_Y = 670;

function glyph(ctx, i, x, y) {
  if (i === 0) {  // numbers: bars, and the dot above the last
    [[-42, 40], [-10, 62], [22, 84]].forEach(([dx, h]) => bar(ctx, x + dx, y + 46 - h, 24, h, C.faint, 2));
    dot(ctx, x + 34, y - 54, 9, C.strong);
  } else if (i === 1) {  // filings: lines of text, and the dot where the reading is
    [[-28, 92], [0, 76], [28, 54]].forEach(([dy, w]) => bar(ctx, x - 46, y + dy - 5, w, 10, "rgba(201,199,193,0.5)"));
    dot(ctx, x + 22, y + 28, 9, C.strong);
  } else if (i === 2) {  // valuation: a band, and the line that ends at the dot
    bar(ctx, x - 58, y - 28, 116, 56, "rgba(242,240,234,0.08)", 2);
    ctx.strokeStyle = C.strong;
    ctx.lineWidth = 4;
    ctx.lineJoin = "round";
    ctx.beginPath();
    [[-58, 16], [-34, -12], [-14, 8], [0, 0]].forEach(([dx, dy], j) => (j ? ctx.lineTo(x + dx, y + dy) : ctx.moveTo(x + dx, y + dy)));
    ctx.stroke();
  } else if (i === 3) {  // comparison: two moves on one zero line
    seg(ctx, x, y - 50, x, y + 50, C.lineStrong, 3);
    move(ctx, x, y - 24, 40, C.up, 9, 4);
    move(ctx, x, y + 24, -28, C.down, 9, 4);
  } else {  // and the ones still to come
    seg(ctx, x - 24, y, x + 24, y, C.muted, 5);
    seg(ctx, x, y - 24, x, y + 24, C.muted, 5);
  }
}

function tools(ctx, t) {
  faded(ctx, span(t, T.tools + 0.3, T.tools + 0.8, T.outro - 0.6, T.outro - 0.2), () => text(ctx, "AI tools", LEFT, 144, { size: 36, color: C.muted }));
  title(ctx, t, "And inside it, five AI tools.", T.tools + 0.3, JOBS_AT - 0.2);
  title(ctx, t, "Efficient and specific: each made for one job.", JOBS_AT, T.outro - 0.2);

  // The dot reads, and answers.
  faded(ctx, span(t, T.tools + 0.4, T.tools + 0.9, JOBS_AT - 0.5, JOBS_AT - 0.1), () => {
    ctx.strokeStyle = C.lineStrong;
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.roundRect(LEFT, 372, 500, 616, 6);
    ctx.stroke();
    const scan = lerp(SCAN_Y[0], SCAN_Y[1], prog(t, SCAN[0], SCAN[1]));
    const key = new Set(ASKED.map((q) => q.line));
    DOC.forEach((w, i) => {
      const read = scan >= lineY(i);
      bar(ctx, 176, lineY(i), 428 * w, 12, key.has(i) && read ? C.strong : `rgba(201,199,193,${read ? 0.4 : 0.15})`);
    });
    if (t > SCAN[0]) faded(ctx, 1 - prog(t, SCAN[1], SCAN[1] + 0.3), () => {
      bar(ctx, 150, scan - 26, 480, 32, "rgba(242,240,234,0.07)", 3);
      seg(ctx, 150, scan + 6, 630, scan + 6, C.strong, 2.5);
    });
    ASKED.forEach((q, i) => {
      const at = askedTime(q);
      const y = 470 + i * 172;
      const k = out3(prog(t, at, at + 0.7));
      faded(ctx, prog(t, at, at + 0.25), () => {
        // From the line that was read, through the dot, to the answer.
        seg(ctx, 640, lineY(q.line) + 6, lerp(640, CORE[0], k), lerp(lineY(q.line) + 6, CORE[1], k), C.lineStrong, 2);
        seg(ctx, CORE[0], CORE[1], lerp(CORE[0], 940, k), lerp(CORE[1], y - 14, k), C.lineStrong, 2);
        text(ctx, q.question, 970, y, { size: 46, weight: 500, color: C.strong });
        bar(ctx, 970, y + 30, 760 * q.first * out3(prog(t, at + 0.3, at + 1.0)), 13, "rgba(201,199,193,0.42)");
        bar(ctx, 970, y + 56, 760 * q.second * out3(prog(t, at + 0.5, at + 1.2)), 13, "rgba(201,199,193,0.22)");
      });
    });
  });

  // The dot, reading; then it becomes one tool among several, each with its job.
  const k = inOut(prog(t, JOBS_AT - 0.3, JOBS_AT + 0.4));
  const [x, y] = [lerp(CORE[0], jobX(2), k), lerp(CORE[1], JOB_Y, k)];
  faded(ctx, span(t, T.tools + 0.45, T.tools + 0.5, T.outro - 0.35, T.outro - 0.3), () => {
    const beat = (t * 1.1) % 1;
    faded(ctx, 0.45 * (1 - beat) * (1 - k), () => { ctx.strokeStyle = C.strong; ctx.lineWidth = 2.5; ctx.beginPath(); ctx.arc(x, y, 15 + beat * 34, 0, Math.PI * 2); ctx.stroke(); });
    dot(ctx, x, y, lerp(15, 11, k), C.strong);
  });
  faded(ctx, span(t, JOBS_AT, JOBS_AT + 0.3, T.outro - 0.6, T.outro - 0.2), () => {
    JOBS.forEach((job, i) => {
      const at = jobTime(i);
      const grown = prog(t, at, at + 0.45);
      if (grown <= 0) return;
      ctx.strokeStyle = C.lineStrong;
      ctx.lineWidth = 3;
      ctx.setLineDash(i === 4 ? [10, 12] : []);
      ctx.beginPath();
      ctx.arc(jobX(i), JOB_Y, 112 * back(grown), 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      faded(ctx, prog(t, at + 0.15, at + 0.5), () => {
        glyph(ctx, i, jobX(i), JOB_Y);
        text(ctx, job, jobX(i), JOB_Y + 180, { size: 34, color: i === 4 ? C.muted : C.ink, align: "center" });
      });
    });
  });
}

// --- 7. The mark again, with its name ----------------------------------------------------------

const LOGO = { y: 450, half: 104, lineW: 21, reach: 136, r: 36, gap: 62 };
const NAME = { size: 128, weight: 600, color: C.strong, ls: -3.5 };

function outro(ctx, t) {
  if (t < T.outro + 0.3) return;
  const name = width(ctx, "Market Hub", NAME);
  const whole = LOGO.reach + LOGO.r + LOGO.gap + name;
  const x = lerp(960, (W - whole) / 2, inOut(prog(t, 53.6, 54.5)));  // the dot arrived at the centre
  const y = lerp(470, LOGO.y, inOut(prog(t, 53.6, 54.5)));
  const grow = out3(prog(t, 53.0, 53.7));
  const reach = LOGO.reach * inOut(prog(t, 53.7, 54.5));
  seg(ctx, x, y - LOGO.half * grow, x, y + LOGO.half * grow, C.strong, lerp(6, LOGO.lineW, grow));
  seg(ctx, x, y, x + reach, y, C.strong, LOGO.lineW);
  dot(ctx, x + reach, y, lerp(13, LOGO.r, out3(prog(t, 52.95, 53.5))), C.strong);
  const shown = prog(t, 54.4, 55.2);
  if (shown > 0) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(x + LOGO.reach + LOGO.r, 0, (LOGO.gap + name + 20) * out3(shown), H);
    ctx.clip();
    text(ctx, "Market Hub", x + LOGO.reach + LOGO.r + LOGO.gap, y + 45, NAME);
    ctx.restore();
  }
  // What it is, and the way in: the site's own button, drawn.
  faded(ctx, prog(t, 55.2, 55.7), () => text(ctx, "Your portfolio, powered by AI.", 960, 668 + (1 - out3(prog(t, 55.2, 55.8))) * 14, { size: 60, weight: 500, color: C.ink, align: "center" }));
  const press = prog(t, 56.0, 56.5);
  if (press > 0) {
    const label = "Open My Hub — it's free";
    const o = { size: 42, weight: 500, color: C.page, align: "center" };
    const w = width(ctx, label, o) + 104, h = 96;
    const s = back(press) * 0.06 + 0.94;
    faded(ctx, press, () => {
      ctx.save();
      ctx.translate(960, 790);
      ctx.scale(s, s);
      bar(ctx, -w / 2, -h / 2, w, h, C.strong, 6);
      text(ctx, label, 0, 15, o);
      ctx.restore();
    });
    // A ring goes out from the button once, as if it were pressed.
    const ring = prog(t, 57.6, 58.6);
    if (ring > 0 && ring < 1) faded(ctx, 0.5 * (1 - ring), () => {
      ctx.strokeStyle = C.strong;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.roundRect(960 - w / 2 - ring * 28, 790 - h / 2 - ring * 28, w + ring * 56, h + ring * 56, 6 + ring * 20);
      ctx.stroke();
    });
  }
  faded(ctx, prog(t, 56.9, 57.4), () => text(ctx, "themarkethub.app", 960, 920, { size: 36, mono: true, color: C.muted, align: "center" }));
}

// --- 7. The five tools, by name ----------------------------------------------------------------

// Each tool in turn: what it is about, its name and a line on the left, and on the right the tool
// at its job, drawn. A row along the bottom says which of the five is on screen.
const NAMED = [
  ["The numbers", "Fundamentals Lab", "Statements, valuation and an AI reading of any US company."],
  ["The results release", "Earnings Radar", "What a company just told its investors, read for you."],
  ["Who does the same thing", "Peer Map", "1,500 US companies, each beside the ones most like it."],
  ["Options, read in detail", "Options Lab", "Volatility, the Greeks and strategies, with their payoff."],
  ["A board you ask for", "Playground", "Ask in plain words. Get the charts and tables you want."],
];
const EACH = (NOW.home - NOW.named) / NAMED.length;
const toolAt = (i) => NOW.named + i * EACH;
const BOX = { x0: 960, x1: RIGHT, y0: 330, y1: 900 };

function wrap(ctx, s, max, o) {
  const lines = [""];
  for (const word of s.split(" ")) {
    const next = lines.at(-1) ? `${lines.at(-1)} ${word}` : word;
    if (width(ctx, next, o) > max && lines.at(-1)) lines.push(word);
    else lines[lines.length - 1] = next;
  }
  return lines;
}

// Fundamentals Lab: eight years of revenue as bars, the margin above them, and the AI's reading.
const YEARS = [1, 1.12, 1.2, 1.38, 1.5, 1.71, 1.86, 2.1];
const MARGIN = [0.22, 0.24, 0.23, 0.26, 0.27, 0.29, 0.3, 0.31];
function numbers(ctx, u) {
  const base = 880, top = 520, step = (BOX.x1 - BOX.x0) / YEARS.length;
  const xOf = (i) => BOX.x0 + (i + 0.5) * step;
  YEARS.forEach((v, i) => {
    const h = (v / 2.1) * (base - top) * out3(prog(u, 0.35 + i * 0.1, 0.8 + i * 0.1));
    bar(ctx, xOf(i) - step * 0.3, base - h, step * 0.6, h, i === YEARS.length - 1 ? C.strong : "rgba(201,199,193,0.32)", 3);
    faded(ctx, prog(u, 0.35 + i * 0.1, 0.6 + i * 0.1), () => text(ctx, String(2018 + i), xOf(i), base + 34, { size: 22, mono: true, color: C.faint, align: "center" }));
  });
  const drawn = out3(prog(u, 1.3, 2.0)) * (MARGIN.length - 1);
  const yOf = (m) => 500 - (m - 0.2) * 900;
  if (drawn > 0) {
    ctx.strokeStyle = C.up;
    ctx.lineWidth = 3.5;
    ctx.lineJoin = "round";
    ctx.beginPath();
    for (let i = 0; i <= Math.floor(drawn); i++) (i ? ctx.lineTo : ctx.moveTo).call(ctx, xOf(i), yOf(MARGIN[i]));
    ctx.stroke();
    for (let i = 0; i <= Math.floor(drawn); i++) dot(ctx, xOf(i), yOf(MARGIN[i]), 6, C.up);
  }
  faded(ctx, prog(u, 1.3, 1.6), () => text(ctx, "Operating margin", BOX.x1, yOf(MARGIN.at(-1)) - 26, { size: 24, color: C.up, align: "right" }));
  faded(ctx, prog(u, 2.0, 2.3), () => {
    text(ctx, "AI reading", BOX.x0, 262, { size: 26, weight: 600, color: C.strong });
    bar(ctx, BOX.x0, 282, 780 * out3(prog(u, 2.1, 2.7)), 12, "rgba(201,199,193,0.42)");
    bar(ctx, BOX.x0, 306, 520 * out3(prog(u, 2.3, 2.9)), 12, "rgba(201,199,193,0.22)");
  });
}

// Earnings Radar: the release is read line by line, and three of its lines become what it says.
const RELEASE = (() => { const r = rng(311); return Array.from({ length: 14 }, (_, i) => (i % 5 === 4 ? 0.45 + r() * 0.2 : 0.8 + r() * 0.2)); })();
const SAYS = [[2, "Guidance", "Raised", C.up], [6, "Demand", "Steady", C.ink], [10, "Margins", "Under pressure", C.down]];
const releaseY = (i) => 388 + i * 36;
const SCAN_U = [0.4, 2.4];
const saidAt = (line) => lerp(...SCAN_U, (releaseY(line) - releaseY(0) + 10) / (releaseY(RELEASE.length - 1) - releaseY(0) + 20));
function radar(ctx, u) {
  ctx.strokeStyle = C.lineStrong;
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.roundRect(BOX.x0, BOX.y0, 400, 570, 6);
  ctx.stroke();
  text(ctx, "Q3 results release", BOX.x0 + 28, 366, { size: 24, color: C.muted });
  const scan = lerp(releaseY(0) - 10, releaseY(RELEASE.length - 1) + 10, prog(u, ...SCAN_U));
  const key = new Set(SAYS.map(([line]) => line));
  RELEASE.forEach((w, i) => {
    const read = scan >= releaseY(i);
    bar(ctx, BOX.x0 + 28, releaseY(i) + 12, 340 * w, 11, key.has(i) && read ? C.strong : `rgba(201,199,193,${read ? 0.4 : 0.15})`);
  });
  if (u > SCAN_U[0]) faded(ctx, 1 - prog(u, SCAN_U[1], SCAN_U[1] + 0.3), () => seg(ctx, BOX.x0 + 10, scan + 18, BOX.x0 + 390, scan + 18, C.strong, 2.5));
  SAYS.forEach(([line, what, said, color], i) => {
    const at = saidAt(line);
    const k = out3(prog(u, at, at + 0.5));
    const y = 450 + i * 170;
    faded(ctx, prog(u, at, at + 0.25), () => {
      seg(ctx, BOX.x0 + 400, releaseY(line) + 18, lerp(BOX.x0 + 400, 1416, k), lerp(releaseY(line) + 18, y - 14, k), C.lineStrong, 2);
      text(ctx, what, 1446, y - 40, { size: 28, color: C.muted });
      dot(ctx, 1456, y - 14, 9, color);
      text(ctx, said, 1480, y, { size: 42, weight: 500, color });
    });
  });
}

// Peer Map: the companies come in as points, each coloured by its move, and one of them is joined
// to the ones that describe their business most like it.
const POINTS = (() => {
  const r = rng(404);
  const centres = Array.from({ length: 7 }, () => [lerp(BOX.x0 + 60, BOX.x1 - 60, r()), lerp(BOX.y0 + 50, BOX.y1 - 50, r())]);
  return Array.from({ length: 150 }, (_, j) => {
    const [cx, cy] = centres[j % centres.length];
    const a = r() * Math.PI * 2, d = (r() ** 0.7) * 120;
    return { x: clamp(cx + Math.cos(a) * d * 1.4, BOX.x0, BOX.x1), y: clamp(cy + Math.sin(a) * d, BOX.y0, BOX.y1), v: (r() - 0.45) * 0.06, born: r() };
  });
})();
const PICKED = POINTS.reduce((best, p, j) => (Math.hypot(p.x - 1360, p.y - 610) < Math.hypot(POINTS[best].x - 1360, POINTS[best].y - 610) ? j : best), 0);
const NEAREST = POINTS.map((p, j) => [j, Math.hypot(p.x - POINTS[PICKED].x, p.y - POINTS[PICKED].y)]).filter(([j]) => j !== PICKED).sort((a, b) => a[1] - b[1]).slice(0, 7).map(([j]) => j);
function peers(ctx, u) {
  const focus = prog(u, 1.5, 1.9);
  POINTS.forEach((p, j) => {
    const k = out3(prog(u, 0.3 + p.born, 0.6 + p.born));
    const near = j === PICKED || NEAREST.includes(j);
    faded(ctx, k * (near ? 1 : lerp(0.8, 0.35, focus)), () => dot(ctx, p.x, p.y, 7 * k, p.v >= 0 ? C.up : C.down));
  });
  const pk = POINTS[PICKED];
  NEAREST.forEach((j, i) => {
    const q = POINTS[j];
    const k = out3(prog(u, 1.7 + i * 0.08, 2.1 + i * 0.08));
    if (k > 0) seg(ctx, pk.x, pk.y, lerp(pk.x, q.x, k), lerp(pk.y, q.y, k), C.strong, 2);
  });
  faded(ctx, focus, () => {
    dot(ctx, pk.x, pk.y, 15, C.strong);
    text(ctx, "NVDA", pk.x + 26, pk.y - 22, { size: 30, mono: true, color: C.strong });
  });
  faded(ctx, prog(u, 2.2, 2.5), () => text(ctx, "Its closest peers, by what each says it does", BOX.x0, 950, { size: 26, color: C.muted }));
}

// Options Lab: a call's payoff drawn across the prices, its breakeven, and its Greeks.
function options(ctx, u) {
  const zero = 700, strike = 1300, loss = 60, slope = 400 / 480;
  const yAt = (x) => (x < strike ? zero + loss : zero + loss - (x - strike) * slope);
  const even = strike + loss / slope;
  faded(ctx, prog(u, 0.2, 0.5), () => {
    seg(ctx, BOX.x0, zero, BOX.x1, zero, C.lineStrong, 2.5);
    seg(ctx, strike, 420, strike, 880, C.faint, 2, [6, 10]);
    text(ctx, "Strike", strike, 912, { size: 24, mono: true, color: C.muted, align: "center" });
    text(ctx, "Price at expiry →", BOX.x1, 912, { size: 24, color: C.muted, align: "right" });
    text(ctx, "0", BOX.x0 - 16, zero + 8, { size: 24, mono: true, color: C.muted, align: "right" });
  });
  const reach = lerp(BOX.x0, BOX.x1, out3(prog(u, 0.4, 1.7)));
  // Loss below the line, profit above it, shaded as the payoff is drawn.
  const shade = (from, to, color) => {
    if (to <= from) return;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(from, zero);
    for (let x = from; x < to; x += 8) ctx.lineTo(x, yAt(x));
    ctx.lineTo(to, yAt(to));
    ctx.lineTo(to, zero);
    ctx.closePath();
    ctx.fill();
  };
  shade(BOX.x0, Math.min(reach, even), "rgba(255,107,87,0.16)");
  shade(even, reach, "rgba(53,201,143,0.16)");
  ctx.strokeStyle = C.strong;
  ctx.lineWidth = 4.5;
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(BOX.x0, yAt(BOX.x0));
  if (reach > strike) ctx.lineTo(strike, yAt(strike));
  ctx.lineTo(reach, yAt(reach));
  ctx.stroke();
  faded(ctx, prog(u, 1.4, 1.7), () => {
    dot(ctx, even, zero, 11, C.strong);
    text(ctx, "Breakeven", even + 22, zero + 44, { size: 28, color: C.strong });
  });
  [["Delta", "0.54"], ["Gamma", "0.031"], ["Theta", "−0.12"], ["Vega", "0.21"]].forEach(([g, v], i) => faded(ctx, prog(u, 1.9 + i * 0.18, 2.2 + i * 0.18), () => {
    const w = text(ctx, g, BOX.x0 + i * 205, 360, { size: 26, color: C.muted });
    text(ctx, v, BOX.x0 + i * 205 + w + 10, 360, { size: 28, mono: true, color: C.strong });
  }));
}

// Playground: a question typed in plain words, and the board it asks for, tile by tile.
const ASK = "Compare NVDA and AMD this year";
const TYPE_U = [0.3, 1.4];
const PAIR = [[501, 0.012], [502, 0.006]].map(([seed, drift]) => { const r = rng(seed); const p = [0]; for (let i = 1; i < 40; i++) p.push(p[i - 1] + (r() - 0.5) * 0.06 + drift); return p; });
const tileAt = (k) => 1.6 + k * 0.22;
function playground(ctx, u) {
  ctx.strokeStyle = C.lineStrong;
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.roundRect(BOX.x0, BOX.y0, BOX.x1 - BOX.x0, 80, 10);
  ctx.stroke();
  const typed = ASK.slice(0, Math.floor(prog(u, ...TYPE_U) * ASK.length));
  const w = text(ctx, typed, BOX.x0 + 30, BOX.y0 + 52, { size: 34, color: C.strong });
  if (u < TYPE_U[1] + 0.3 && Math.floor(u * 3) % 2 === 0) bar(ctx, BOX.x0 + 36 + w, BOX.y0 + 22, 3, 40, C.strong, 1);
  const [tw, th, gap] = [(BOX.x1 - BOX.x0 - 20) / 2, 215, 20];
  for (let k = 0; k < 4; k++) {
    const at = tileAt(k);
    const g = prog(u, at, at + 0.35);
    if (g <= 0) continue;
    const [x, y] = [BOX.x0 + (k % 2) * (tw + gap), 440 + Math.floor(k / 2) * (th + gap)];
    faded(ctx, g, () => {
      ctx.save();
      ctx.translate(0, (1 - out3(g)) * 18);
      ctx.fillStyle = "#101213";
      ctx.strokeStyle = C.line;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(x, y, tw, th, 6);
      ctx.fill();
      ctx.stroke();
      if (k === 0) {  // the two prices over the year, from the same start
        const [low, high] = [Math.min(...PAIR[0], ...PAIR[1]), Math.max(...PAIR[0], ...PAIR[1])];
        const upTo = out3(prog(u, at + 0.2, at + 1.0)) * (PAIR[0].length - 1);
        PAIR.forEach((p, n) => {
          ctx.strokeStyle = n ? C.muted : C.strong;
          ctx.lineWidth = n ? 2.5 : 3.5;
          ctx.beginPath();
          for (let j = 0; j <= Math.floor(upTo); j++) (j ? ctx.lineTo : ctx.moveTo).call(ctx, x + 24 + (j / (p.length - 1)) * (tw - 48), y + th - 30 - ((p[j] - low) / (high - low)) * (th - 80));
          ctx.stroke();
        });
        text(ctx, "NVDA", x + 24, y + 38, { size: 22, mono: true, color: C.strong });
        text(ctx, "AMD", x + 104, y + 38, { size: 22, mono: true, color: C.muted });
      } else if (k === 1) {  // the moves of the day, on one zero line
        const zx = x + tw / 2;
        seg(ctx, zx, y + 30, zx, y + th - 24, C.lineStrong, 2);
        [0.018, -0.007, 0.011, -0.013].forEach((v, n) => move(ctx, zx, y + 56 + n * 40, (v / 0.02) * 150 * out3(prog(u, at + 0.2 + n * 0.08, at + 0.6 + n * 0.08)), tone(v), 7, 3));
      } else if (k === 2) {  // a table of figures
        [["NVDA", 0.42], ["AMD", 0.17], ["SOXX", 0.21]].forEach(([s, v], n) => {
          text(ctx, s, x + 24, y + 58 + n * 56, { size: 24, mono: true, color: C.strong });
          bar(ctx, x + 130, y + 44 + n * 56, 200 * (0.4 + n * 0.2), 10, "rgba(201,199,193,0.3)");
          text(ctx, signed(v, 1), x + tw - 24, y + 58 + n * 56, { size: 24, mono: true, color: C.up, align: "right" });
        });
      } else {  // one figure, large
        text(ctx, "NVDA ahead of AMD, this year", x + 24, y + 48, { size: 22, color: C.muted });
        text(ctx, "+25.0 pts", x + 24, y + 150, { size: 72, mono: true, color: C.strong, ls: -3 });
      }
      ctx.restore();
    });
  }
}

const SCENES = [numbers, radar, peers, options, playground];

function named(ctx, t) {
  faded(ctx, span(t, NOW.named + 0.2, NOW.named + 0.6, NOW.home - 0.6, NOW.home - 0.2), () => {
    text(ctx, "AI tools", LEFT, 144, { size: 36, color: C.muted });
    // Which of the five is on screen: the row along the bottom, underlined under the one shown.
    const slot = (RIGHT - LEFT) / NAMED.length;
    const now = clamp(Math.floor((t - NOW.named) / EACH), 0, NAMED.length - 1);
    NAMED.forEach(([, name], i) => text(ctx, name, LEFT + i * slot, 1010, { size: 28, color: i === now ? C.strong : i < now ? C.muted : C.faint }));
    const k = now > 0 ? inOut(prog(t - toolAt(now), 0, 0.45)) : 1;
    const from = Math.max(0, now - 1);
    const lit = lerp(from, now, k);
    const w = lerp(width(ctx, NAMED[from][1], { size: 28 }), width(ctx, NAMED[now][1], { size: 28 }), k);
    seg(ctx, LEFT + lit * slot, 1030, LEFT + lit * slot + w, 1030, C.strong, 3);
  });
  NAMED.forEach(([about, name, line], i) => {
    const a = toolAt(i), u = t - a;
    const last = i === NAMED.length - 1;
    const shown = span(t, a + 0.1, a + 0.45, a + EACH - (last ? 0.6 : 0.4), a + EACH - (last ? 0.2 : 0.05));
    if (shown <= 0) return;
    faded(ctx, shown, () => {
      const rise = (1 - out3(prog(u, 0.1, 0.7))) * 22;
      text(ctx, about, LEFT, 420 + rise, { size: 34, color: C.muted });
      text(ctx, name, LEFT, 520 + rise, { size: 92, weight: 500, color: C.strong });
      faded(ctx, prog(u, 0.35, 0.75), () => wrap(ctx, line, 700, { size: 42 }).forEach((s, n) => text(ctx, s, LEFT, 610 + n * 58, { size: 42, color: C.ink })));
      SCENES[i](ctx, u);
    });
  });
}

// --- 8. All of it in My Hub --------------------------------------------------------------------

const SPACE = ["Overview", "Analysis", "Watchlist", "Community", "Portfolio"];
const WIN = { x: 1080, y: 290, w: 600, h: 700 };
const HOME_POINTS = ["Your portfolio, in plain words.", "Five AI tools, one click away.", "Only you see it."];
const homeAt = (i) => NOW.home + 0.9 + i * 0.4;
const lightAt = (i) => NOW.home + 1.0 + i * 0.32;

function home(ctx, t) {
  const a = span(t, NOW.home + 0.2, NOW.home + 0.6, NOW.outro - 0.6, NOW.outro - 0.2);
  faded(ctx, a, () => text(ctx, "My Hub", LEFT, 144, { size: 36, color: C.muted }));
  title(ctx, t, "All of it in My Hub. Free.", NOW.home + 0.2, NOW.outro - 0.2);
  faded(ctx, a, () => {
    HOME_POINTS.forEach((s, i) => faded(ctx, prog(t, homeAt(i), homeAt(i) + 0.35), () => {
      dot(ctx, LEFT + 12, 486 + i * 110, 10, C.up);
      text(ctx, s, LEFT + 46, 502 + i * 110, { size: 46, color: C.strong });
    }));
    // The window: My Hub's sidebar as the site draws it.
    const k = out3(prog(t, NOW.home + 0.3, NOW.home + 0.9));
    faded(ctx, k, () => {
      ctx.save();
      ctx.translate(0, (1 - k) * 30);
      const { x, y, w, h } = WIN;
      ctx.fillStyle = "#070808";
      ctx.strokeStyle = C.lineStrong;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, 12);
      ctx.fill();
      ctx.stroke();
      seg(ctx, x, y + 46, x + w, y + 46, C.line, 2);
      [0, 1, 2].forEach((n) => dot(ctx, x + 26 + n * 22, y + 23, 6, C.lineStrong));
      text(ctx, "themarkethub.app/dashboard", x + 110, y + 31, { size: 18, mono: true, color: C.faint });
      // The brand, with the logo the dot has just become.
      seg(ctx, x + 46, y + 102, x + 46, y + 138, C.strong, 4);
      seg(ctx, x + 46, y + 120, x + 62, y + 120, C.strong, 4);
      dot(ctx, x + 66, y + 120, 7, C.strong);
      const bw = text(ctx, "The Market Hub", x + 92, y + 130, { size: 26, weight: 600, color: C.strong });
      ctx.strokeStyle = C.lineStrong;
      ctx.beginPath();
      ctx.roundRect(x + 104 + bw, y + 104, 86, 32, 4);
      ctx.stroke();
      text(ctx, "My Hub", x + 147 + bw, y + 127, { size: 18, color: C.muted, align: "center" });
      bar(ctx, x + 28, y + 164, w - 56, 44, "#101213", 6);
      dot(ctx, x + 50, y + 186, 5, C.up);
      text(ctx, "Private area. Only you see it.", x + 66, y + 193, { size: 19, color: C.muted });
      text(ctx, "YOUR SPACE", x + 40, y + 244, { size: 17, color: C.faint, ls: 1.5 });
      SPACE.forEach((s, i) => {
        if (i === 0) bar(ctx, x + 28, y + 256, w - 56, 36, "#191b1d", 5);
        text(ctx, s, x + 40, y + 282 + i * 38, { size: 22, weight: 600, color: i === 0 ? C.strong : C.ink });
      });
      text(ctx, "TOOLS", x + 40, y + 484, { size: 17, color: C.faint, ls: 1.5 });
      NAMED.forEach(([, name], i) => {
        const lit = prog(t, lightAt(i), lightAt(i) + 0.25);
        const ty = y + 522 + i * 38 - 26;
        if (lit > 0) faded(ctx, lit * (1 - prog(t, lightAt(i) + 0.4, lightAt(i) + 0.9)), () => bar(ctx, x + 28, ty, w - 56, 36, "#191b1d", 5));
        text(ctx, name, x + 40, y + 522 + i * 38, { size: 22, weight: 600, color: mix(C.ink, C.strong, lit) });
        faded(ctx, lit, () => {
          bar(ctx, x + w - 84, ty + 8, 44, 24, "rgba(53,201,143,0.14)", 4);
          text(ctx, "AI", x + w - 62, ty + 26, { size: 16, color: C.up, align: "center" });
        });
      });
      ctx.restore();
    });
  });
}

// --- The frame ---------------------------------------------------------------------------------

export function draw(ctx, t) {
  ctx.globalAlpha = 1;
  ctx.fillStyle = C.page;
  ctx.fillRect(0, 0, W, H);
  ctx.save();
  ctx.globalAlpha = span(t, 0, 0.3, NOW.end - 0.7, NOW.end - 0.05);
  if (t < NOW.today) leadMark(ctx, t), intro(ctx, t);
  else if (t < NOW.hub) faded(ctx, 1 - prog(t, NOW.hub - 0.5, NOW.hub - 0.1), () => today(ctx, t));
  if (t >= NOW.hub - 0.1 && t < NOW.tools) hub(ctx, t + SHIFT);
  if (t >= NOW.tools - 0.1 && t < NOW.named) faded(ctx, 1 - prog(t, NOW.named - 0.6, NOW.named - 0.2), () => tools(ctx, t + SHIFT));
  if (t >= NOW.named - 0.1 && t < NOW.home) named(ctx, t);
  if (t >= NOW.home - 0.1 && t < NOW.outro) home(ctx, t);
  if (t >= NOW.outro) outro(ctx, t);
  travel(ctx, t);
  ctx.restore();
}

// --- What happens when: the score ----------------------------------------------------------------

// {t, kind, ...}. `step` is a degree of the scale (higher is higher), `pan` runs from -1 to 1.
export const EVENTS = (() => {
  const e = [];
  const pan = (x) => (x / W) * 1.4 - 0.7;
  e.push({ t: 0.35, kind: "swell", length: 1.3 });
  e.push({ t: 1.62, kind: "pluck", step: 2, gain: 1.0 });
  e.push({ t: 2.3, kind: "glide", from: 2, to: 4, length: 0.8 }, { t: 3.08, kind: "pluck", step: 4, gain: 0.8, pan: 0.4 });
  e.push({ t: 3.6, kind: "glide", from: 4, to: 0, length: 0.8 }, { t: 4.38, kind: "pluck", step: 0, pan: -0.5 });
  e.push({ t: 4.7, kind: "glide", from: 0, to: 5, length: 0.8 }, { t: 5.48, kind: "pluck", step: 5, pan: 0.5 });
  e.push({ t: 5.9, kind: "whoosh", length: 1.0 });
  // Today: a note per row, higher for a rise and lower for a fall.
  RULER.forEach(([, , v], i) => i && e.push({ t: rowTime(i) + 0.1, kind: "pluck", step: 4 + Math.round(clamp(v / SCALE, -1, 1) * 4), pan: pan(ZERO_X + rulerPx(v)), gain: 0.85 }));
  for (const [at] of TRAVELS) e.push({ t: at - 0.35, kind: "whoosh", length: 0.9 });
  // My Hub and the dot that reads, on the longer film's clock: the lock closing, a note per
  // position, the year drawn as one rising note, the news; then an answer each time the reading
  // reaches a line.
  const shifted = [];
  shifted.push({ t: 32.0, kind: "tick", gain: 0.9, pan: -0.6 }, { t: 32.8, kind: "pluck", step: 0, gain: 0.9, pan: -0.6 });
  shifted.push({ t: 32.1, kind: "shimmer", length: 1.7 });
  HELD.forEach(([, , , v], i) => shifted.push({ t: heldTime(i) + 0.1, kind: "pluck", step: v > 0 ? 5 + i : 2, gain: 0.75, pan: 0.5 }));
  shifted.push({ t: 36.2, kind: "pluck", step: 4, gain: 0.6 }, { t: YEAR[0], kind: "glide", from: 1, to: 7, length: YEAR[1] - YEAR[0] - 0.2 }, { t: YEAR[1], kind: "pluck", step: 7, gain: 0.8, pan: 0.1 });
  OWN_NEWS.forEach((_, i) => shifted.push({ t: ownNewsTime(i), kind: "pluck", step: [5, 3, 6][i], gain: 0.7, pan: 0.5 }));
  shifted.push({ t: SCAN[0], kind: "shimmer", length: SCAN[1] - SCAN[0] });
  ASKED.forEach((q, i) => shifted.push({ t: askedTime(q), kind: "pluck", step: 4 + i * 2, gain: 0.9, pan: 0.4 }, { t: askedTime(q) + 0.3, kind: "tick", gain: 0.6, pan: 0.5 }));
  shifted.forEach((ev) => e.push({ ...ev, t: ev.t - SHIFT }));
  // The five tools: a note as each one is named, a step higher each time, and what each one does.
  NAMED.forEach((_, i) => e.push({ t: toolAt(i) + 0.12, kind: "tick", gain: 0.7, pan: -0.6 }, { t: toolAt(i) + 0.15, kind: "pluck", step: 2 + i, gain: 0.95, pan: -0.5 }));
  const [at0, at1, at2, at3, at4] = NAMED.map((_, i) => toolAt(i));
  YEARS.forEach((v, i) => e.push({ t: at0 + 0.4 + i * 0.1, kind: "pluck", step: 1 + Math.round((v - 1) * 6), gain: 0.5, pan: pan(BOX.x0 + (i + 0.5) * 102) }));
  e.push({ t: at0 + 1.3, kind: "glide", from: 3, to: 6, length: 0.6 }, { t: at0 + 2.1, kind: "shimmer", length: 0.9 });
  e.push({ t: at1 + SCAN_U[0], kind: "shimmer", length: SCAN_U[1] - SCAN_U[0] });
  SAYS.forEach(([line], i) => e.push({ t: at1 + saidAt(line), kind: "pluck", step: [7, 4, 1][i], gain: 0.85, pan: 0.5 }));
  for (let n = 0; n < 8; n++) e.push({ t: at2 + 0.35 + n * 0.13, kind: "tick", gain: 0.35, pan: -0.2 + n * 0.1 });
  e.push({ t: at2 + 1.5, kind: "pluck", step: 6, gain: 0.9, pan: 0.1 });
  NEAREST.forEach((_, i) => e.push({ t: at2 + 1.75 + i * 0.08, kind: "pluck", step: 3 + (i % 3), gain: 0.4, pan: 0.2 }));
  e.push({ t: at3 + 0.4, kind: "glide", from: 1, to: 7, length: 1.2 }, { t: at3 + 1.45, kind: "pluck", step: 5, gain: 0.85 });
  [0, 1, 2, 3].forEach((i) => e.push({ t: at3 + 1.95 + i * 0.18, kind: "tick", gain: 0.55, pan: -0.1 + i * 0.15 }));
  for (let n = 0; n < ASK.length; n += 3) e.push({ t: at4 + TYPE_U[0] + (n / ASK.length) * (TYPE_U[1] - TYPE_U[0]), kind: "tick", gain: 0.3, pan: 0.3 });
  [0, 1, 2, 3].forEach((k) => e.push({ t: at4 + tileAt(k), kind: "pluck", step: [4, 5, 6, 8][k], gain: 0.75, pan: k % 2 ? 0.5 : 0.2 }));
  // My Hub's window: a note as each tool lights in it, and as each point is said.
  e.push({ t: NOW.home + 0.3, kind: "shimmer", length: 1.2 });
  NAMED.forEach((_, i) => e.push({ t: lightAt(i), kind: "pluck", step: 3 + i, gain: 0.6, pan: 0.5 }));
  HOME_POINTS.forEach((_, i) => e.push({ t: homeAt(i), kind: "pluck", step: [2, 4, 6][i], gain: 0.55, pan: -0.5 }));
  // The logo, assembled: the line, the move, and the chord the film has been heading for; then the
  // line, the button, the address, and the button pressed.
  e.push({ t: 53.0, kind: "swell", length: 0.8 }, { t: 53.7, kind: "glide", from: 2, to: 5, length: 0.8 });
  [0, 2, 3, 5, 7].forEach((step, i) => e.push({ t: 54.45 + i * 0.09, kind: "pluck", step, gain: 1.0, pan: -0.4 + i * 0.2 }));
  e.push({ t: 55.2, kind: "pluck", step: 3, gain: 0.6 }, { t: 56.0, kind: "pluck", step: 5, gain: 0.75 }, { t: 56.9, kind: "pluck", step: 8, gain: 0.4 });
  e.push({ t: 57.6, kind: "tick", gain: 0.8 }, { t: 57.62, kind: "pluck", step: 7, gain: 0.7 });
  return e.sort((a, b) => a.t - b.t);
})();

// The harmony changes with the parts: [second, bass, notes], as MIDI numbers.
export const CHORDS = [
  [0, 41, [53, 57, 60, 67]], [NOW.today + 1, 38, [53, 57, 60, 62]],
  [NOW.hub, 41, [53, 57, 60, 67]], [36.2 - SHIFT, 38, [53, 57, 60, 62]], [NOW.tools, 34, [53, 57, 58, 62]],
  [toolAt(0), 38, [53, 57, 60, 62]], [toolAt(1), 36, [55, 60, 62, 65]], [toolAt(2), 41, [53, 57, 60, 67]], [toolAt(3), 34, [53, 57, 58, 62]], [toolAt(4), 36, [55, 60, 62, 65]],
  [NOW.home, 38, [53, 57, 60, 62]], [NOW.outro, 36, [55, 60, 62, 65]],
  [54.4, 41, [53, 57, 60, 65, 69]],
];
