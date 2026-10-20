// The community's bot competition: what /api/bots returns (see src/markethub/bots.py) and the
// calls of its page. The competition has its own site, Bot League: the kit, the keys and the agent's
// routes are there. Here the board is read, and a bot can be withdrawn or its key taken back.
import { api } from "./api";

export type BotPeriod = "1d" | "1w" | "1m" | "1y" | "all";
export type BotReturns = Record<BotPeriod, number | null>;
export type BotHolding = { ticker: string; weight: number }; // weight as a fraction
export type BotLine = {
  handle: string; stand_in: boolean; you: boolean; name: string; about: string; since: string | null; as_of: string | null;
  sessions: number; returns: BotReturns; ranks: Partial<Record<BotPeriod, number>>; holdings: BotHolding[]; holding: number; cash: number | null;
};
export type MyBot = {
  handle: string; name: string; about: string; submitted_utc: string; since: string | null; as_of: string | null; sessions: number;
  returns: BotReturns | null; ranks: Partial<Record<BotPeriod, number>>; entrants: number; holdings: BotHolding[]; cash: number | null;
  rules: string[]; universe: number; curve: { date: string; value: number }[];
};
export type BotKey = { created_utc: string; used_utc: string | null };
export type BotBoard = {
  sample: boolean; as_of: string | null; stale: boolean; periods: { key: BotPeriod; label: string }[]; rows: BotLine[]; entrants: number;
  benchmark: { ticker: string; returns: BotReturns | null }; you: MyBot | null; key: BotKey | null; name: string;
  rules: { cost: number; universe: number; hold: number }; league: string;
};

export const botBoard = () => api<BotBoard>("/api/bots");
export const refreshBots = () => api<{ moved: number; asked?: boolean }>("/api/bots/refresh", { method: "POST" });
export const dropBotKey = () => api<{ revoked: boolean }>("/api/bots/key", { method: "DELETE" });
export const withdrawBot = () => api<{ withdrawn: boolean }>("/api/bots/mine", { method: "DELETE" });
