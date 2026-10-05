// Calls to the portal's API. Same origin in production; in development the API runs on another
// port and PUBLIC_API_URL points at it (with credentials, so the session cookie goes along).
export const API = (import.meta.env.PUBLIC_API_URL ?? "").replace(/\/$/, "");

export type User = { id: string; email: string; name: string; picture: string };
export type Position = { ticker: string; shares: number; avg_cost: number | null };
export type Portfolio = { positions: Position[]; watchlist: string[]; updated_utc?: string };
export type Config = { google_client_id: string; tools: { earnings_radar: string | null; fundamentals_lab: string | null } };

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    credentials: "include",
    ...init,
    headers: init.body ? { "content-type": "application/json", ...(init.headers ?? {}) } : init.headers,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, body.detail ?? `Request failed (${res.status}).`);
  return body as T;
}

export const me = () => api<{ user: User; has_data: boolean }>("/api/me");
export const config = () => api<Config>("/api/config");

// Who is signed in, or null. Pages that need a user send the visitor to the sign-in page.
export async function signedIn(): Promise<{ user: User; has_data: boolean } | null> {
  try {
    return await me();
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) return null;
    throw e;
  }
}

export async function requireUser(): Promise<{ user: User; has_data: boolean }> {
  const who = await signedIn();
  if (!who) {
    location.replace(`${import.meta.env.BASE_URL.replace(/\/$/, "")}/signin/?next=${encodeURIComponent(location.pathname + location.search)}`);
    throw new Error("not signed in");
  }
  return who;
}

export const toolLinks = (tools: Config["tools"], ticker: string) => ({
  fundamentals: tools.fundamentals_lab ? `${tools.fundamentals_lab}/stock/?t=${encodeURIComponent(ticker)}` : null,
  earnings: tools.earnings_radar ? `${tools.earnings_radar}/analyze/?ticker=${encodeURIComponent(ticker)}` : null,
});
