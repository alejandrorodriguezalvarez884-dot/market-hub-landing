// The film on the landing page: a minute of drawing, with no recording of the site in it.
//
// It starts from the logo, which is the site's own figure (a zero line and a move to its
// right), and turns that mark into each part of Market Hub: the day, the markets, the news, your
// own portfolio and the AI tools. `draw(ctx, t)` paints the frame at
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

// When each part starts, in seconds.
const T = { intro: 0, today: 6.5, lede: 11.6, markets: 15.5, news: 23.5, hub: 31, tools: 41.5, outro: 52.5, end: DURATION };

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
// begins: [time, from, to]. The first one leaves from the end of the sentence, set when it is drawn.
const TRAVELS = [
  [T.markets, [1300, 700], [LEFT, 880]],
  [T.news, [1180, 700], [LEFT, 376]],
  [T.hub, [LEFT, 900], [330, 706]],
  [T.tools, [RIGHT, 900], [800, 680]],
  [T.outro, [960, 670], [960, 470]],
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
  title(ctx, t, "And the day, in one sentence.", T.lede + 0.1, T.markets - 0.2);

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

// The sentence the Today page opens with. A word is [text, style]: figures are set in mono.
const LEDE = [
  [["US"], ["stocks"], ["are"], ["higher."], ["The"], ["S&P"], ["500"], ["is"]],
  [["up"], ["0.87%", "up"], ["at"], ["5,712.40.", "fig"], ["Gold"], ["is"], ["up"], ["0.65%,", "up"]],
  [["and"], ["crude"], ["oil"], ["is"], ["down"], ["1.80%.", "down"]],
];
const LEDE_START = 12.1, LEDE_STEP = 0.085;

function lede(ctx, t) {
  faded(ctx, 1 - prog(t, T.markets - 0.6, T.markets - 0.2), () => {
    let n = 0;
    LEDE.forEach((words, row) => {
      let x = LEFT;
      const y = 480 + row * 124;
      for (const [word, style] of words) {
        const at = LEDE_START + n++ * LEDE_STEP;
        const o = style ? { size: 76, mono: true, color: style === "fig" ? C.strong : C[style] } : { size: 88, weight: 500, color: C.ink };
        const a = prog(t, at, at + 0.2);
        faded(ctx, a, () => text(ctx, word, x, y + (1 - out3(a)) * 16, o));
        x += width(ctx, word, o) + 24;
      }
      if (row === LEDE.length - 1) TRAVELS[0][1] = [x + 14, y - 26];  // the dot leaves from the full stop
    });
  });
}

// --- 3. Markets --------------------------------------------------------------------------------

const CANDLES = (() => {
  const r = rng(7);
  let close = 1;
  const out = [];
  for (let i = 0; i < 150; i++) {
    const open = close;
    close = open * (1 + (r() - 0.455) * 0.022);
    const high = Math.max(open, close) * (1 + r() * 0.007);
    const low = Math.min(open, close) * (1 - r() * 0.007);
    out.push({ open, close, high, low });
  }
  const k = 5712.4 / close;  // the last close is the level the film has been quoting
  return out.map((c) => ({ open: c.open * k, close: c.close * k, high: c.high * k, low: c.low * k }));
})();
const CHART = { x0: LEFT, wide: RIGHT, narrow: 1180, y0: 486, y1: 884 };
const CANDLE_START = 16.3, CANDLE_DRAW = 2.3, ZOOM = [19.6, 20.5];
const range = (from) => CANDLES.slice(from).reduce(([lo, hi], c) => [Math.min(lo, c.low), Math.max(hi, c.high)], [Infinity, -Infinity]);
const [NEAR, FAR] = [range(100), range(0)];
const SPARKS = [["Gold", 0.0065], ["Crude oil", -0.018], ["EUR/USD", -0.0021], ["Bitcoin", 0.024], ["Technology", 0.0131], ["Energy", -0.0112]]
  .map(([name, v], i) => {
    const r = rng(40 + i);
    const path = [0];
    for (let j = 1; j < 24; j++) path.push(path[j - 1] + (r() - 0.5) + Math.sign(v) * 0.16);
    return { name, v, path };
  });
const sparkTime = (i) => 20.8 + i * 0.22;

function markets(ctx, t) {
  const a = heading(ctx, t, T.markets, T.news, "Markets", "Every market, every sector, charted.");
  faded(ctx, a, () => {
    // A month of candles across the frame; then the chart steps back to a year and makes room.
    const zoom = inOut(prog(t, ZOOM[0], ZOOM[1]));
    const shown = lerp(50, 150, zoom);
    const first = 150 - shown;
    const x1 = lerp(CHART.wide, CHART.narrow, zoom);
    const lo = lerp(NEAR[0], FAR[0], zoom), hi = lerp(NEAR[1], FAR[1], zoom);
    const yOf = (p) => CHART.y1 - ((p - lo) / (hi - lo)) * (CHART.y1 - CHART.y0);
    const step = (x1 - CHART.x0) / shown;
    let last = CANDLES[100];
    seg(ctx, CHART.x0, yOf(CANDLES[100].open), x1, yOf(CANDLES[100].open), C.lineStrong, 2, [3, 10]);
    CANDLES.forEach((c, j) => {
      if (j < Math.floor(first)) return;
      const born = CANDLE_START + ((j - 100) / 50) * CANDLE_DRAW;
      const k = j >= 100 ? out3(prog(t, born, born + 0.25)) : prog(t, ZOOM[0], ZOOM[1]);
      if (k <= 0) return;
      last = j >= 100 ? c : last;
      const x = CHART.x0 + (j - first + 0.5) * step;
      const color = c.close >= c.open ? C.up : C.down;
      const mid = (yOf(c.open) + yOf(c.close)) / 2;
      const at = (p) => lerp(mid, yOf(p), k);
      faded(ctx, j >= 100 ? 1 : k, () => {
        seg(ctx, x, at(c.high), x, at(c.low), color, Math.max(1.5, step * 0.1));
        bar(ctx, x - step * 0.31, Math.min(at(c.open), at(c.close)), step * 0.62, Math.max(2, Math.abs(at(c.open) - at(c.close))), color, 1.5);
      });
    });
    // The figure above the chart follows the candle being drawn.
    const n = text(ctx, "S&P 500", LEFT, 420, { size: 42, color: C.ink });
    const w = text(ctx, last.close.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }), LEFT + n + 30, 422, { size: 60, mono: true, color: C.strong });
    faded(ctx, prog(t, CANDLE_START + CANDLE_DRAW, CANDLE_START + CANDLE_DRAW + 0.3), () => text(ctx, "+0.87%", LEFT + n + w + 58, 420, { size: 40, mono: true, color: C.up }));
    // The ranges under it: a month, then a year.
    const picked = lerp(2, 5, zoom);
    ["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y"].forEach((s, i) => text(ctx, s, LEFT + i * 112, 962, { size: 32, mono: true, color: Math.abs(i - picked) < 0.5 ? C.strong : C.muted }));
    seg(ctx, LEFT + picked * 112, 980, LEFT + picked * 112 + 38, 980, C.strong, 3);

    SPARKS.forEach(({ name, v, path }, i) => {
      const at = sparkTime(i);
      const y = 500 + i * 82;
      faded(ctx, prog(t, at, at + 0.3), () => {
        text(ctx, name, 1300, y + 14, { size: 40, color: C.strong });
        text(ctx, signed(v), RIGHT, y + 12, { size: 32, mono: true, align: "right", color: tone(v) });
        const [low, high] = [Math.min(...path), Math.max(...path)];
        const upTo = out3(prog(t, at + 0.1, at + 0.8)) * (path.length - 1);
        ctx.strokeStyle = C.ink;
        ctx.lineWidth = 3;
        ctx.lineJoin = "round";
        ctx.beginPath();
        let end = [0, 0];
        for (let j = 0; j <= Math.floor(upTo); j++) {
          end = [1530 + (j / (path.length - 1)) * 110, y + 20 - ((path[j] - low) / (high - low)) * 40];
          j ? ctx.lineTo(...end) : ctx.moveTo(...end);
        }
        ctx.stroke();
        dot(ctx, end[0], end[1], 6, tone(v));
      });
    });
  });
}

// --- 4. News -----------------------------------------------------------------------------------

const NEWS = [
  ["2h ago", "SEC filing", "Costco reports September sales results", ["COST"]],
  ["4h ago", "Federal Reserve", "Federal Reserve issues FOMC statement", []],
  ["6h ago", "Bureau of Labor Statistics", "Payrolls change little in September", []],
  ["Today", "Market Hub", "S&P 500 up 0.87% at 5,712.40", ["SPX", "NDX", "DJI"]],
];
const newsTime = (i) => 24.5 + i * 0.75;
const PRESS = (() => { const r = rng(91); return Array.from({ length: 6 }, () => [0.6 + r() * 0.4, 0.3 + r() * 0.5]); })();
const pressTime = (i) => 26.7 + i * 0.2;
// The kinds of news, and a reader trying two of them: [when, which kind]. Each item has its kind.
const KINDS = ["All", "Markets", "Economy", "Companies", "Earnings"];
const PICKS = [[27.9, 0], [28.4, 3], [29.3, 2], [30.2, 0]];
const KIND_OF = [3, 2, 2, 1];

function news(ctx, t) {
  const a = heading(ctx, t, T.news, T.hub, "News", "What was filed and published today.");
  faded(ctx, a, () => {
    let pick = 0;
    PICKS.forEach(([at], i) => { if (t >= at) pick = i; });
    const [since, kind] = PICKS[pick], before = PICKS[Math.max(0, pick - 1)][1];
    const turn = out3(prog(t, since, since + 0.3));
    const lit = (which, i) => (which === 0 || KIND_OF[i] === which ? 1 : 0.2);
    const places = [];
    let tx = LEFT;
    for (const name of KINDS) places.push([tx, width(ctx, name, { size: 32 })]), (tx += places.at(-1)[1] + 46);
    faded(ctx, prog(t, PICKS[0][0], PICKS[0][0] + 0.4), () => {
      KINDS.forEach((name, i) => text(ctx, name, places[i][0], 334, { size: 32, color: i === kind ? C.strong : C.muted }));
      seg(ctx, lerp(places[before][0], places[kind][0], turn), 350, lerp(places[before][0] + places[before][1], places[kind][0] + places[kind][1], turn), 350, C.strong, 3);
    });
    NEWS.forEach(([when, source, line, chips], i) => {
      const at = newsTime(i);
      const k = prog(t, at, at + 0.4);
      const y = 404 + i * 168 + (1 - out3(k)) * 22;
      faded(ctx, k * lerp(lit(before, i), lit(kind, i), turn), () => {
        const w = text(ctx, when, LEFT, y, { size: 30, mono: true, color: C.muted });
        text(ctx, source, LEFT + w + 22, y, { size: 30, color: C.muted });
        text(ctx, line, LEFT, y + 64, { size: 54, weight: 500, color: C.strong });
        let x = LEFT;
        for (const chip of chips) {
          const cw = width(ctx, chip, { size: 26, mono: true }) + 26;
          ctx.strokeStyle = C.lineStrong;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.roundRect(x, y + 84, cw, 38, 4);
          ctx.stroke();
          text(ctx, chip, x + 13, y + 112, { size: 26, mono: true, color: C.ink });
          x += cw + 12;
        }
        if (!chips.length) bar(ctx, LEFT, y + 96, 700 + i * 110, 13, "rgba(201,199,193,0.16)");
        seg(ctx, LEFT, y + 132, 1340, y + 132, C.line, 2);
      });
    });
    // Beside them, the press: headlines as lines, for nothing of theirs is reproduced here.
    faded(ctx, prog(t, 26.4, 26.8), () => {
      text(ctx, "In the press", 1460, 394, { size: 34, weight: 600, color: C.strong });
      seg(ctx, 1460, 418, RIGHT, 418, C.lineStrong, 2);
    });
    PRESS.forEach(([first, second], i) => {
      const at = pressTime(i);
      const y = 456 + i * 90;
      faded(ctx, prog(t, at, at + 0.3), () => {
        bar(ctx, 1460, y, 320 * first * out3(prog(t, at, at + 0.5)), 14, "rgba(201,199,193,0.36)");
        bar(ctx, 1460, y + 30, 320 * second * out3(prog(t, at + 0.1, at + 0.6)), 14, "rgba(201,199,193,0.18)");
        seg(ctx, 1460, y + 66, RIGHT, y + 66, C.line, 2);
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
  title(ctx, t, "Unique tools, built on AI.", T.tools + 0.3, JOBS_AT - 0.2);
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
  const line = "At last, all the information and all the power in your hands.";
  const first = "At last,";
  const o = { size: 54, color: C.ink };
  const lx = (W - width(ctx, line, o)) / 2;
  faded(ctx, prog(t, 55.4, 55.9), () => text(ctx, first, lx, 690, o));
  faded(ctx, prog(t, 56.2, 56.7), () => text(ctx, line.slice(first.length), lx + width(ctx, first, o), 690, o));
  faded(ctx, prog(t, 57.1, 57.6), () => text(ctx, "themarkethub.app", 960, 800, { size: 38, mono: true, color: C.muted, align: "center" }));
}

// --- The frame ---------------------------------------------------------------------------------

export function draw(ctx, t) {
  ctx.globalAlpha = 1;
  ctx.fillStyle = C.page;
  ctx.fillRect(0, 0, W, H);
  ctx.save();
  ctx.globalAlpha = span(t, 0, 0.3, T.end - 0.7, T.end - 0.05);
  if (t < T.today) leadMark(ctx, t), intro(ctx, t);
  else if (t < T.markets) today(ctx, t), t >= T.lede && lede(ctx, t);
  if (t >= T.markets - 0.1 && t < T.news) markets(ctx, t);
  if (t >= T.news - 0.1 && t < T.hub) news(ctx, t);
  if (t >= T.hub - 0.1 && t < T.tools) hub(ctx, t);
  if (t >= T.tools - 0.1 && t < T.outro) tools(ctx, t);
  if (t >= T.outro) outro(ctx, t);
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
  e.push({ t: T.lede + 0.2, kind: "pluck", step: 3, gain: 0.6 });
  LEDE.flat().forEach(([, style], n) => e.push({ t: LEDE_START + n * LEDE_STEP, kind: style ? "pluck" : "tick", step: style === "down" ? 1 : 6, gain: style ? 0.65 : 0.5 }));
  for (const [at] of TRAVELS) e.push({ t: at - 0.35, kind: "whoosh", length: 0.9 });
  // Markets: the chart is played as it is drawn, a note every fifth candle, at the height of its close.
  for (let j = 100; j < 150; j += 5) {
    const height = (CANDLES[j].close - NEAR[0]) / (NEAR[1] - NEAR[0]);
    e.push({ t: CANDLE_START + ((j - 100) / 50) * CANDLE_DRAW, kind: "pluck", step: 1 + Math.round(height * 7), gain: 0.6, pan: pan(CHART.x0 + (j - 100) * 33) });
  }
  e.push({ t: ZOOM[0], kind: "whoosh", length: 1.0 });
  SPARKS.forEach(({ v }, i) => e.push({ t: sparkTime(i) + 0.1, kind: "pluck", step: v > 0 ? 6 : 2, gain: 0.55, pan: 0.5 }));
  NEWS.forEach((_, i) => e.push({ t: newsTime(i), kind: "pluck", step: [3, 5, 4, 7][i], gain: 0.85, pan: -0.3 }));
  PICKS.slice(1).forEach(([at], i) => e.push({ t: at, kind: "tick", gain: 0.9, pan: -0.5 }, { t: at + 0.04, kind: "pluck", step: [6, 4, 2][i], gain: 0.7, pan: -0.4 }));
  PRESS.forEach((_, i) => e.push({ t: pressTime(i), kind: "tick", gain: 0.5, pan: 0.5 }));
  // My Hub: the lock closing, a note per position, the year drawn as one rising note, the news.
  e.push({ t: 32.0, kind: "tick", gain: 0.9, pan: -0.6 }, { t: 32.8, kind: "pluck", step: 0, gain: 0.9, pan: -0.6 });
  e.push({ t: 32.1, kind: "shimmer", length: 1.7 });
  HELD.forEach(([, , , v], i) => e.push({ t: heldTime(i) + 0.1, kind: "pluck", step: v > 0 ? 5 + i : 2, gain: 0.75, pan: 0.5 }));
  e.push({ t: 36.2, kind: "pluck", step: 4, gain: 0.6 }, { t: YEAR[0], kind: "glide", from: 1, to: 7, length: YEAR[1] - YEAR[0] - 0.2 }, { t: YEAR[1], kind: "pluck", step: 7, gain: 0.8, pan: 0.1 });
  OWN_NEWS.forEach((_, i) => e.push({ t: ownNewsTime(i), kind: "pluck", step: [5, 3, 6][i], gain: 0.7, pan: 0.5 }));
  // The tools: the reading, an answer each time it reaches a line, then one note per tool.
  e.push({ t: SCAN[0], kind: "shimmer", length: SCAN[1] - SCAN[0] });
  ASKED.forEach((q, i) => e.push({ t: askedTime(q), kind: "pluck", step: 4 + i * 2, gain: 0.9, pan: 0.4 }, { t: askedTime(q) + 0.3, kind: "tick", gain: 0.6, pan: 0.5 }));
  e.push({ t: JOBS_AT - 0.3, kind: "whoosh", length: 0.8 });
  JOBS.forEach((_, i) => e.push({ t: jobTime(i), kind: "pluck", step: [5, 3, 1, 4, 7][i], gain: 0.85, pan: (jobX(i) / W) * 1.4 - 0.7 }));
  // The logo, assembled: the line, the move, and the chord the film has been heading for.
  e.push({ t: 53.0, kind: "swell", length: 0.8 }, { t: 53.7, kind: "glide", from: 2, to: 5, length: 0.8 });
  [0, 2, 3, 5, 7].forEach((step, i) => e.push({ t: 54.45 + i * 0.09, kind: "pluck", step, gain: 1.0, pan: -0.4 + i * 0.2 }));
  e.push({ t: 55.4, kind: "pluck", step: 3, gain: 0.6 }, { t: 56.2, kind: "pluck", step: 5, gain: 0.6 }, { t: 57.1, kind: "pluck", step: 8, gain: 0.4 });
  return e.sort((a, b) => a.t - b.t);
})();

// The harmony changes with the parts: [second, bass, notes], as MIDI numbers.
export const CHORDS = [
  [0, 41, [53, 57, 60, 67]], [T.today + 1, 38, [53, 57, 60, 62]], [T.markets, 34, [53, 57, 58, 62]], [T.news, 36, [55, 60, 62, 65]],
  [T.hub, 41, [53, 57, 60, 67]], [36.2, 38, [53, 57, 60, 62]], [T.tools, 34, [53, 57, 58, 62]], [JOBS_AT, 38, [53, 57, 60, 62]], [T.outro, 36, [55, 60, 62, 65]],
  [54.4, 41, [53, 57, 60, 65, 69]],
];
