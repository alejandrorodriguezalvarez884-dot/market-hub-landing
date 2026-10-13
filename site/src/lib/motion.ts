// Motion for a page that is told as it is scrolled: parts that come in when they are reached,
// figures that count to their value, and what follows the scroll itself. A reader who asked for
// less motion gets every part in its place at once.

export const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

const clamp = (v: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
export const easeOut = (t: number) => 1 - (1 - clamp(t)) ** 3;

// Calls `then` once, the first time `el` is on screen. `ahead` is how far inside the window it
// has to be, as a fraction of the window's height.
export function reached(el: Element, then: () => void, ahead = 0.12) {
  if (still() || !("IntersectionObserver" in window)) return then();
  const seen = new IntersectionObserver((entries) => {
    if (!entries.some((e) => e.isIntersecting)) return;
    seen.disconnect();
    then();
  }, { rootMargin: `0px 0px -${Math.round(ahead * 100)}% 0px` });
  seen.observe(el);
}

// Everything marked `data-rv` under `root` comes in when it is reached (the page's styles say
// how). `--i` on an element is its turn among its neighbours.
export function reveal(root: ParentNode = document, ahead?: number) {
  root.querySelectorAll<HTMLElement>('[data-rv=""]').forEach((el) => {
    el.dataset.rv = "watched";
    reached(el, () => el.classList.add("in"), ahead);
  });
}

// Marks `el` as a part that comes in, the `turn`-th of its group.
export function rv<T extends HTMLElement | SVGElement>(el: T, turn = 0): T {
  el.setAttribute("data-rv", "");
  if (turn) el.style.setProperty("--i", String(turn));
  return el;
}

// A figure that counts from one value to another. What it shows on the way is formatted like
// what it ends on, so its width does not jump.
export function count(el: HTMLElement, from: number, to: number, format: (v: number) => string, ms = 900) {
  if (still() || from === to) return void (el.textContent = format(to));
  const start = performance.now();
  const step = (now: number) => {
    const t = (now - start) / ms;
    el.textContent = format(t >= 1 ? to : from + (to - from) * easeOut(t));
    if (t < 1) requestAnimationFrame(step);
  };
  el.textContent = format(from);
  requestAnimationFrame(step);
}

// One listener for the scroll and the window's size, and at most one pass a frame.
const followers = new Set<() => void>();
let waiting = false;
function pass() {
  waiting = false;
  followers.forEach((f) => f());
}
export function onScroll(follow: () => void) {
  if (!followers.size) {
    const ask = () => waiting || ((waiting = true), requestAnimationFrame(pass));
    addEventListener("scroll", ask, { passive: true });
    addEventListener("resize", ask, { passive: true });
  }
  followers.add(follow);
  follow();
}

// Runs every follower again: for when the page has changed size without the window doing so.
export const scrolled = () => pass();
