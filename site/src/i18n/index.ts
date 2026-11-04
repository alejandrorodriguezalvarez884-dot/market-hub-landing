// The languages of the site. English lives at the root and Spanish under /es/, each page built
// once per language. The words of each part of the site live in a file of this folder, English and
// Spanish side by side (`words(en, es)`), so the type check fails if Spanish misses a key or turns
// a sentence into something else.
//
// The reader's choice is the cookie mh_lang ("en" or "es") on .themarkethub.app, shared with the
// portal and the tools: the head of every page sends the reader to their language (Layout.astro),
// a bar offers the other one when the browser asks for it and nothing was chosen (choice.ts), and
// the foot has the switch. Never by IP.

export type Lang = "en" | "es";
export const LANGS: Lang[] = ["en", "es"];
export const COOKIE = "mh_lang";

// The language of the page on screen, from <html lang>. On the server (building a page) there is
// no document: pages pass their language explicitly there.
export function lang(): Lang {
  return typeof document !== "undefined" && document.documentElement.lang === "es" ? "es" : "en";
}

// Both languages of a set of words. The Spanish must have the same keys and the same shapes.
export function words<T>(en: T, es: NoInfer<T>): Record<Lang, T> {
  return { en, es };
}

// The locale for Intl, by language.
export const locale = (l: Lang = lang()) => (l === "es" ? "es-ES" : "en-US");

// "/board/" in a language: "/board/" or "/es/board/". Paths are without the site's base.
export function inLang(path: string, l: Lang): string {
  const bare = stripLang(path);
  return l === "es" ? `/es${bare === "/" ? "/" : bare}` : bare;
}

// A path without its language: "/es/board/" -> "/board/".
export function stripLang(path: string): string {
  if (path === "/es" || path === "/es/") return "/";
  return path.startsWith("/es/") ? path.slice(3) : path;
}

// The language a path is in.
export const langOf = (path: string): Lang => (path === "/es" || path.startsWith("/es/") ? "es" : "en");
