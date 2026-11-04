// Calls to the portal's API. Same origin in production; in development the API runs on another
// port and PUBLIC_API_URL points at it (with credentials, so the session cookie goes along).
import { lang } from "../i18n";
import { link } from "./site";

export const API = (import.meta.env.PUBLIC_API_URL ?? "").replace(/\/$/, "");

// `provider` says how the account signs in: with Google, with Apple (from the phone app) or with
// a password kept by us (and then it has no picture). Sessions from before there were two ways in do not say, and are Google's.
export type User = { id: string; email: string; name: string; picture: string; provider?: "google" | "password" | "apple" };
export type Position = { ticker: string; shares: number; avg_cost: number | null };
export type Portfolio = { positions: Position[]; watchlist: string[]; updated_utc?: string };
export type Config = { google_client_id: string; domain: string | null; password_login?: boolean;
  // Whether an account can be made here: with a captcha (and then the key of its widget), without one, or not at all.
  registration?: "captcha" | "open" | "closed"; turnstile_site_key?: string | null;
  submissions?: boolean; // whether readers can send articles in for review here
  tools: { earnings_radar: string | null; fundamentals_lab: string | null } };

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Every call says the page's language (X-MH-Lang), so what the service writes in words comes back
// in it. A header of our own, not Accept-Language: browsers and the phone app send that one by
// themselves, and only a page in Spanish asks for Spanish (docs/i18n.md).
export const langHeader = (): Record<string, string> => ({ "x-mh-lang": lang() });

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    ...init,
    headers: { ...langHeader(), ...(init.body ? { "content-type": "application/json" } : {}), ...((init.headers as Record<string, string>) ?? {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, body.detail ?? (lang() === "es" ? `La petición ha fallado (${res.status}).` : `Request failed (${res.status}).`));
  return body as T;
}

export const me = () => api<{ user: User; has_data: boolean; moderator?: boolean }>("/api/me");
export const config = () => api<Config>("/api/config");

// Who is signed in, or null. Pages that need a user send the visitor to the sign-in page.
export async function signedIn(): Promise<{ user: User; has_data: boolean; moderator?: boolean } | null> {
  try {
    return await me();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}

export async function requireUser(): Promise<{ user: User; has_data: boolean; moderator?: boolean }> {
  const who = await signedIn();
  if (!who) {
    location.replace(`${link("/signin/")}?next=${encodeURIComponent(location.pathname + location.search)}`);
    throw new Error("not signed in");
  }
  return who;
}

export const toolLinks = (tools: Config["tools"], ticker: string) => ({
  fundamentals: tools.fundamentals_lab ? `${tools.fundamentals_lab}/stock/?t=${encodeURIComponent(ticker)}` : null,
  earnings: tools.earnings_radar ? `${tools.earnings_radar}/analyze/?ticker=${encodeURIComponent(ticker)}` : null,
});
