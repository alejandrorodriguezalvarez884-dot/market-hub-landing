// Opinion: the articles, their text and the comments under them. The articles are written in
// the market-hub-opinion repo; the comments are written here by signed-in readers.
import { API, api } from "./api";
import { add, h, linkTo } from "./dom";
import { link } from "./site";

export type Source = { title: string; url: string };
export type Cover = { alt: string; v: string };
export type Card = { slug: string; title: string; dek: string; kind: string; tags: string[]; tickers: string[]; published_utc: string; minutes: number; cover?: Cover | null };
export type Article = Card & { body: string; sources: Source[] };
export type Comment = { id: string; parent_id: string | null; depth: number; created_utc: string; deleted: boolean; name: string; text: string; mine: boolean };
export type Thread = { comments: Comment[]; signed_in: boolean; moderator: boolean };

export const articles = (limit = 50) => api<{ articles: Card[] }>(`/api/public/opinion?limit=${limit}`);
export const article = (slug: string) => api<Article>(`/api/public/opinion/item?slug=${encodeURIComponent(slug)}`);
export const thread = (slug: string) => api<Thread>(`/api/public/opinion/comments?slug=${encodeURIComponent(slug)}`);
export const comment = (slug: string, text: string, parent_id: string | null) =>
  api<Comment>("/api/opinion/comments", { method: "POST", body: JSON.stringify({ slug, text, parent_id }) });
export const removeComment = (id: string) => api<{ deleted: boolean }>(`/api/opinion/comments/${encodeURIComponent(id)}`, { method: "DELETE" });

export const articleHref = (slug: string) => link(`/opinion/article/?slug=${encodeURIComponent(slug)}`);
export const day = (iso: string) => new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" });

// The picture an article was published with, if it has one. Its address names its version, so a
// browser keeps it for good and a cover drawn again is asked for again.
export function cover(a: Card, cls: string): HTMLImageElement | null {
  if (!a.cover) return null;
  const img = h("img", `rounded-md bg-line object-cover ${cls}`);
  Object.assign(img, { src: `${API}/api/public/opinion/cover?slug=${encodeURIComponent(a.slug)}&v=${encodeURIComponent(a.cover.v)}`, alt: a.cover.alt, loading: "lazy", decoding: "async" });
  return img;
}

// The line over a title: what kind of piece it is, when it was published and how long it takes.
export function overline(a: Card): HTMLElement {
  return add(h("p", "flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12.5px] text-muted"),
    h("span", "font-medium text-ink-strong", a.kind), h("time", "", day(a.published_utc)), h("span", "", `${a.minutes} min read`));
}

// --- The text of an article ---------------------------------------------------------------------

// An article is written in a small part of Markdown: paragraphs, "## " headings, "> " quotes,
// "- " lists, **bold**, *emphasis* and [links](address). Everything is built as elements, never
// as markup, so nothing in an article can become code on the page.
function inline(text: string): (Node | string)[] {
  const out: (Node | string)[] = [];
  const mark = /\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\(([^)\s]+)\)/g;
  let from = 0;
  for (let m = mark.exec(text); m; m = mark.exec(text)) {
    if (m.index > from) out.push(text.slice(from, m.index));
    if (m[1] !== undefined) out.push(h("strong", "font-semibold text-ink-strong", m[1]));
    else if (m[2] !== undefined) out.push(h("em", "", m[2]));
    else if (m[4].startsWith("/")) out.push(linkTo(link(m[4]), "link", m[3]));
    else if (/^https?:\/\//.test(m[4])) {
      const a = linkTo(m[4], "link", m[3]);
      a.target = "_blank";
      a.rel = "noopener";
      out.push(a);
    } else out.push(m[3]);
    from = m.index + m[0].length;
  }
  if (from < text.length) out.push(text.slice(from));
  return out;
}

export function prose(body: string): HTMLElement[] {
  return body.replace(/\r\n/g, "\n").split(/\n\s*\n/).map((block) => block.trim()).filter(Boolean).map((block) => {
    const lines = block.split("\n");
    if (block.startsWith("## ")) return add(h("h2", "pt-4 text-[1.375rem] font-medium leading-snug tracking-tight text-ink-strong"), ...inline(block.slice(3)));
    if (lines.every((l) => l.startsWith("> ")))
      return add(h("blockquote", "border-l-2 border-line-strong pl-5 text-ink-strong"), ...inline(lines.map((l) => l.slice(2)).join(" ")));
    if (lines.every((l) => l.startsWith("- ")))
      return add(h("ul", "list-disc space-y-2 pl-6"), ...lines.map((l) => add(h("li"), ...inline(l.slice(2)))));
    return add(h("p"), ...inline(lines.join(" ")));
  });
}
