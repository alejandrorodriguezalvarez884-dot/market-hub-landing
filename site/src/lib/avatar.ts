import type { User } from "./api";
import { h } from "./dom";

// The user's Google picture, or their initial when there is none (an account with a password of
// ours has none) or it fails to load.
export function avatar(user: User, size = "h-8 w-8"): HTMLElement {
  const el = h("span", `flex ${size} flex-none items-center justify-center overflow-hidden rounded-full bg-accent text-sm font-semibold text-white`);
  if (user.picture) {
    const img = h("img", "h-full w-full object-cover");
    img.src = user.picture;
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    img.onerror = () => el.replaceChildren(user.name.charAt(0).toUpperCase());
    el.append(img);
  } else el.textContent = user.name.charAt(0).toUpperCase();
  return el;
}

export async function signOut(home: string) {
  const { api } = await import("./api");
  await api("/api/auth/logout", { method: "POST" });
  (window as any).google?.accounts?.id?.disableAutoSelect?.();
  location.href = home;
}
