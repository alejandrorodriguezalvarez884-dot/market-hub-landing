// A thread of comments: a box to write in, and the comments nested under the ones they answer.
// It is the same under an opinion article and under a month of the community's competition; what
// differs (where the comments are read from and sent to, and what stands under the box) is given.
import { ApiError } from "./api";
import { add, h } from "./dom";
import { timeAgo } from "./format";
import type { Comment, Thread } from "./opinion";

export type ThreadSource = {
  load: () => Promise<Thread>;
  post: (text: string, parent: string | null) => Promise<unknown>;
  remove: (id: string) => Promise<unknown>;
  note: string; // under the box: how a comment is shown
  ask?: string; // inside the empty box
  none?: string; // where there are no comments yet
  visitor?: () => HTMLElement; // what someone not signed in gets in place of the box
};

const DEPTH_MAX = 6; // as the server's: below this a thread is answered further up

// Fills `els` with the thread and keeps it current. Returns the function that reads it again.
export function mountThread(els: { composer: HTMLElement; list: HTMLElement; count?: HTMLElement }, src: ThreadSource): () => Promise<void> {
  // Where a comment or an answer is written. `parent` is the comment it answers, if any.
  function composer(parent: string | null, cancel?: () => void): HTMLElement {
    const box = h("textarea", "field min-h-[5.5rem] w-full resize-y");
    box.maxLength = 2000;
    box.placeholder = parent ? "Write your answer" : src.ask ?? "What do you think?";
    box.setAttribute("aria-label", box.placeholder);
    const send = h("button", "btn btn-primary", parent ? "Answer" : "Comment");
    send.type = "submit";
    const note = h("p", "text-[13px] text-down");
    note.setAttribute("role", "alert");
    const form = add(h("form", "space-y-2"), box, add(h("div", "flex flex-wrap items-center gap-3"), send,
      cancel ? Object.assign(h("button", "btn btn-ghost", "Cancel"), { type: "button", onclick: cancel }) : null,
      h("span", "text-[12.5px] text-muted", src.note), note));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!box.value.trim()) return;
      send.disabled = true;
      note.textContent = "";
      try {
        await src.post(box.value, parent);
        load();
      } catch (err) {
        send.disabled = false;
        note.textContent = err instanceof ApiError ? err.message : "The comment could not be sent.";
      }
    });
    return form;
  }

  function one(c: Comment, t: Thread, children: Map<string | null, Comment[]>): HTMLElement {
    const el = h("div", "pt-5");
    el.id = `c-${c.id}`;
    const head = add(h("p", "flex flex-wrap items-center gap-x-2.5 text-[12.5px] text-muted"),
      c.deleted ? h("span", "", "Deleted") : add(h("span", "flex items-center gap-2 font-medium text-ink-strong"),
        h("span", "flex h-6 w-6 items-center justify-center rounded-full bg-raised text-[11px]", c.name.charAt(0).toUpperCase()), c.name),
      h("time", "num", timeAgo(c.created_utc)));
    const actions = h("p", "mt-1.5 flex gap-4 text-[12.5px] text-muted");
    const slot = h("div", "mt-3");
    if (!c.deleted) {
      if (t.signed_in && c.depth < DEPTH_MAX) {
        const reply = Object.assign(h("button", "hover:text-ink-strong", "Answer"), { type: "button" });
        reply.addEventListener("click", () => {
          slot.replaceChildren(composer(c.id, () => slot.replaceChildren()));
          slot.querySelector("textarea")!.focus();
        });
        actions.append(reply);
      }
      if (c.mine || t.moderator) {
        const del = Object.assign(h("button", "hover:text-down", "Delete"), { type: "button" });
        del.addEventListener("click", async () => {
          if (!confirm("Delete this comment?")) return;
          await src.remove(c.id).catch(() => {});
          load();
        });
        actions.append(del);
      }
    }
    add(el, head, c.deleted ? null : h("p", "mt-1.5 whitespace-pre-wrap break-words text-[15px] leading-relaxed text-ink", c.text), actions, slot);
    const under = children.get(c.id) ?? [];
    // Answers hang from a rule at the left of what they answer, as deep as the thread goes.
    if (under.length) el.append(add(h("div", "ml-1.5 border-l border-line pl-4 sm:ml-3 sm:pl-5"), ...under.map((x) => one(x, t, children))));
    return el;
  }

  function show(t: Thread) {
    const live = t.comments.filter((c) => !c.deleted).length;
    if (els.count) els.count.textContent = live ? `${live}` : "";
    els.composer.replaceChildren(t.signed_in ? composer(null) : src.visitor?.() ?? "");
    const children = new Map<string | null, Comment[]>();
    for (const c of t.comments) children.set(c.parent_id, [...(children.get(c.parent_id) ?? []), c]);
    // A deleted comment with nothing under it leaves no trace.
    const kept = (c: Comment): boolean => !c.deleted || (children.get(c.id) ?? []).some(kept);
    for (const [k, list] of children) children.set(k, list.filter(kept));
    const top = [...(children.get(null) ?? [])].reverse(); // the newest conversation first; its answers in order
    els.list.replaceChildren(...(top.length ? top.map((c) => one(c, t, children)) : [h("p", "text-sm text-muted", src.none ?? "No comments yet. Be the first.")]));
  }

  const load = () => src.load().then(show).catch(() => {});
  return load;
}
