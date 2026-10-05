// Tiny DOM helpers. Everything that comes from the API or the address bar goes in as text, never
// as markup.
export function h<K extends keyof HTMLElementTagNameMap>(tag: K, cls = "", text?: string): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

export function add<T extends Element>(parent: T, ...children: (Node | string | null | undefined | false)[]): T {
  for (const c of children) if (c) parent.append(c);
  return parent;
}

export function svg<K extends keyof SVGElementTagNameMap>(tag: K, attrs: Record<string, string | number> = {}): SVGElementTagNameMap[K] {
  const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  return e;
}

// A titled panel: the building block of every section.
export function card(title: string, subtitle?: string, cls = ""): { el: HTMLElement; body: HTMLElement; head: HTMLElement } {
  const el = h("section", `panel ${cls}`);
  const head = add(h("header", "panel-head"), add(h("div", "min-w-0"), h("h2", "panel-title", title),
    subtitle ? h("p", "mt-0.5 text-xs text-muted", subtitle) : null));
  const body = h("div", "p-4");
  add(el, head, body);
  return { el, body, head };
}

// A small figure: label above, value below.
export function stat(label: string, value: string, note?: string, tone: "up" | "down" | "" = ""): HTMLElement {
  const color = tone === "up" ? "text-up" : tone === "down" ? "text-down" : "text-ink-strong";
  return add(
    h("div", "min-w-0"),
    h("div", "label", label),
    h("div", `mt-1 text-xl font-semibold tabular-nums ${color}`, value),
    note ? h("div", "mt-0.5 text-xs text-muted", note) : null,
  );
}

export const toneOf = (v: number | null | undefined): "up" | "down" | "" =>
  typeof v === "number" ? (v > 0 ? "up" : v < 0 ? "down" : "") : "";

export function linkTo(href: string, cls: string, text?: string): HTMLAnchorElement {
  const a = h("a", cls, text);
  a.href = href;
  return a;
}
