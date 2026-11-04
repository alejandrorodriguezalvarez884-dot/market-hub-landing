// The reader's choice of language: the switch in the foot, and a quiet bar offering the other
// language when the browser asks for it and nothing has been chosen yet. The choice is the cookie
// mh_lang on .themarkethub.app, so the portal and every tool open in the same language; the head
// of each page (Layout.astro) reads it and moves to the chosen language before anything is drawn.
import { COOKIE, type Lang } from ".";
import { offer } from "./layout";

export function chosen(): Lang | null {
  const m = document.cookie.match(new RegExp(`(?:^|;\\s*)${COOKIE}=(en|es)`));
  return m ? (m[1] as Lang) : null;
}

export function choose(l: Lang): void {
  const shared = /(^|\.)themarkethub\.app$/.test(location.hostname) ? "; domain=.themarkethub.app" : "";
  document.cookie = `${COOKIE}=${l}; path=/; max-age=31536000; SameSite=Lax${secure()}${shared}`;
}
const secure = () => (location.protocol === "https:" ? "; Secure" : "");

// The browser's first language, as one of ours, or null.
function asked(): Lang | null {
  const first = (navigator.languages?.[0] ?? navigator.language ?? "").toLowerCase();
  return first.startsWith("es") ? "es" : first.startsWith("en") ? "en" : null;
}

// The page in the other language: its address, with the query and the anchor kept.
const there = (alt: string) => `${alt}${location.search}${location.hash}`;

// Wire the switch (links marked data-lang) and, when it fits, show the offer.
export function languageChoice(): void {
  const root = document.documentElement;
  const here = (root.lang === "es" ? "es" : "en") as Lang;
  const alt = root.dataset.alt;
  for (const a of document.querySelectorAll<HTMLAnchorElement>("a[data-lang]")) {
    a.addEventListener("click", (e) => {
      const l = a.dataset.lang as Lang;
      choose(l);
      if (l === here) return e.preventDefault();
      if (alt) (e.preventDefault(), location.assign(there(alt)));
    });
  }
  const want = asked();
  if (!alt || chosen() || !want || want === here) return;
  const w = offer[want];
  const bar = document.createElement("div");
  bar.className = "lang-offer";
  bar.setAttribute("role", "region");
  bar.setAttribute("aria-label", w.ask);
  bar.lang = want;
  const text = Object.assign(document.createElement("span"), { textContent: w.ask, className: "lang-offer-ask" });
  const yes = Object.assign(document.createElement("a"), { textContent: w.yes, href: there(alt), className: "btn btn-primary py-1 text-[13px]" });
  const no = Object.assign(document.createElement("button"), { textContent: w.no, type: "button", className: "btn btn-ghost py-1 text-[13px]" });
  yes.addEventListener("click", () => choose(want));
  no.addEventListener("click", () => (choose(here), bar.remove()));
  bar.append(text, yes, no);
  document.body.append(bar);
}
