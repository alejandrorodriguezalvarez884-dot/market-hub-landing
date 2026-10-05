// The market in a sentence or two, written from the overview's own figures. It only says what
// the numbers say (up, down, by how much): no reasons, no outlook.
import { add, h } from "./dom";
import { level, pct } from "./format";
import type { Overview, Snapshot } from "./market";

const FLAT = 0.001; // within a tenth of a percent, a market is "little changed"
const dir = (v: number) => (v > FLAT ? 1 : v < -FLAT ? -1 : 0);
const tone = (v: number) => (dir(v) > 0 ? "up" : dir(v) < 0 ? "down" : "");

type Part = Node | string;
type Pick = (s: Snapshot) => void;

// A figure in the sentence; with `s`, it opens that instrument in the chart below.
function fig(text: string, cls = "", s?: Snapshot, pick?: Pick): HTMLElement {
  if (!s || !pick) return h("span", `fig ${cls}`, text);
  const b = h("button", `fig ${cls}`, text);
  b.type = "button";
  b.addEventListener("click", () => pick(s));
  return b;
}

// A word that carries a direction takes its colour; it stays in the sentence's own type.
const word = (text: string, cls: string) => h("span", cls, text);

// "up 0.64%", "down 1.41%", "little changed"
const move = (v: number): Part[] => (dir(v) ? [word(v > 0 ? "up " : "down ", tone(v)), fig(pct(Math.abs(v), 2), tone(v))] : ["little changed"]);

function sentence(...parts: (Part | Part[])[]): Part[] {
  return [...parts.flat(), ". "];
}

function list(items: Part[][]): Part[] {
  return items.flatMap((x, i) => (i === 0 ? x : [i === items.length - 1 ? " and " : ", ", ...x]));
}

export function lede(o: Overview, pick?: Pick): HTMLElement {
  const by = (group: Snapshot[], symbol: string) => group.find((s) => s.symbol === symbol);
  const out: Part[] = [];

  const us = ["SPX", "NDX", "DJI", "RUT"].map((s) => by(o.indices, s)).filter((s): s is Snapshot => !!s);
  if (us.length) {
    const dirs = us.map((s) => dir(s.change_pct));
    const all = (d: number) => dirs.every((x) => x === d);
    const state = all(1) ? "higher" : all(-1) ? "lower" : all(0) ? "little changed" : "mixed";
    out.push(...sentence("US stocks are ", word(state, all(1) ? "up" : all(-1) ? "down" : "text-ink-strong")));
  }

  const spx = by(o.indices, "SPX");
  if (spx) {
    const parts: Part[] = ["The S&P 500 is ", ...move(spx.change_pct), " at ", fig(level(spx.price, spx.kind), "", spx, pick)];
    const rising = o.sectors.filter((s) => s.change_pct > 0);
    if (o.sectors.length) {
      const n = o.sectors.length;
      const best = [...o.sectors].sort((a, b) => b.change_pct - a.change_pct)[0];
      const worst = [...o.sectors].sort((a, b) => a.change_pct - b.change_pct)[0];
      if (rising.length === n) parts.push(`, and all ${n} sectors are rising, led by ${best.name}`);
      else if (!rising.length) parts.push(`, and all ${n} sectors are falling, ${worst.name} the most`);
      else parts.push(`, with ${rising.length} of ${n} sectors rising, led by ${best.name}`);
    }
    out.push(...sentence(parts));
  }

  const rest: Part[][] = [];
  const ten = by(o.rates, "US10Y");
  if (ten) rest.push(["the 10-year Treasury yields ", fig(`${ten.price.toFixed(2)}%`)]);
  const gold = by(o.commodities, "GOLD");
  if (gold) rest.push(["gold is ", ...move(gold.change_pct)]);
  const btc = by(o.crypto, "BTCUSD");
  if (btc) rest.push(["bitcoin is ", ...move(btc.change_pct)]);
  if (rest.length) {
    const joined = list(rest);
    if (typeof joined[0] === "string") joined[0] = joined[0].charAt(0).toUpperCase() + joined[0].slice(1);
    out.push(...sentence(joined));
  }

  // A comma or a full stop stays on the line of the figure before it.
  const glued: Part[] = [];
  for (const part of out) {
    const before = glued[glued.length - 1];
    if (typeof part === "string" && /^[,.]/.test(part) && before instanceof HTMLElement) {
      glued[glued.length - 1] = add(h("span", "whitespace-nowrap"), before, part[0]);
      if (part.length > 1) glued.push(part.slice(1));
    } else glued.push(part);
  }
  return add(h("span"), ...glued);
}
