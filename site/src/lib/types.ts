// What /api/dashboard returns (see src/markethub/dashboard.py).
export type N = number | null;
type Facts = { return_1m: N; return_3m: N; return_ytd: N; return_1y: N; spark: number[] };
export type Row = Facts & {
  ticker: string; name: string; sector: string; country: string; shares: number; avg_cost: N; price: N; value: N; cost: N;
  pnl: N; pnl_pct: N; day_change: N; day_change_pct: N; weight: N; day_contribution: N; beta: N; volatility: N; volatility_group: string;
  market_cap: N; size: string; dividend_yield: N; from_high_52w: N;
};
export type Watch = Facts & { ticker: string; name: string; price: N; day_change_pct: N; from_high_52w: N; year_low: N; year_high: N };
// The positions gathered by something they share: a sector, a country, how much they move, their size.
export type Group = { label: string; value: number; weight: number; count: number; tickers: string[]; day_change_pct: N; volatility: N;
  return_1m: N; return_3m: N; return_ytd: N; return_1y: N };
export type Grouping = { key: string; label: string; note?: string; items: Group[] };
export type PeriodKey = "1d" | "1m" | "3m" | "ytd" | "1y";
export type Period = { key: PeriodKey; label: string; portfolio: N; indices: Record<string, N> };
export type Index = Facts & { ticker: string; name: string; price: N; day_change_pct: N };
export type Day = { date: string; return: number };
export type Risk = { volatility: N; beta: N; benchmark_volatility: N; max_drawdown: N; best_day: Day | null; worst_day: Day | null; up_days: N;
  top1: N; top3: N; top3_tickers: string[]; effective_positions: N; dividend_yield: N };
// The portfolio read back in sentences: by the code at once, by the model when it answers.
export type Insights = { headline: string; items: { kind: string; text: string }[]; written: boolean };
export type Dashboard = {
  sample: boolean;
  totals: { value: N; cost: N; pnl: N; pnl_pct: N; day_change: N; day_change_pct: N; positions: number; cost_covers: number };
  positions: Row[];
  sectors: { sector: string; value: number; weight: number }[];
  groups: Grouping[];
  history: { dates: string[]; value: number[]; portfolio_rebased: number[]; benchmark_rebased: number[]; benchmark?: string; indices: Record<string, number[]> };
  performance: { periods: Period[]; indices: { ticker: string; name: string }[] };
  risk: Risk;
  watchlist: Watch[];
  movers: { up: string[]; down: string[] };
  benchmark: Index;
  indices: Index[];
  insights: Insights;
  notes: string[];
};

// What /api/community returns (see src/markethub/community.py).
export type Returns = Record<PeriodKey, N>;
export type Member = { handle: string; since_utc: string | null; you: boolean; stand_in: boolean; sample: boolean; count: number; top_sector: string | null;
  positions: { ticker: string; name: string; sector: string; weight: number }[]; performance: Returns; volatility: N; updated_utc: string };
export type Standing = { rank: number; of: number; return: number; average: number; above_average: boolean; ahead_of: number };
export type Board = {
  members: Member[]; average: Returns; sample: boolean; shared: number;
  you: { sharing: boolean; handle: string; since_utc: string | null; performance: Returns | null; standing: Record<PeriodKey, Standing | null> };
  periods: { key: PeriodKey; label: string }[];
  indices: { ticker: string; name: string; performance: Returns }[];
};
export type Sharing = { enabled: boolean; handle: string; since_utc: string | null };
