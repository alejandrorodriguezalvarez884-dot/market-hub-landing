# The bot format (`markethub-bot/1`)

A bot is one JSON file, `bot.json`. It is a set of rules, not code: Market Hub runs it on paper.
At the close of each session it rebalances on, it looks at the companies of its universe, keeps
those that pass its filters, scores them, holds the best ones with the weights it says, and keeps
them to the next close. No money, no broker, no orders: a simulation on daily closes.

```json
{
  "format": "markethub-bot/1",
  "name": "Trend follower",
  "about": "Large caps over their 200-session average, the strongest of the last six months.",
  "universe": {"largest": 300, "exclude": ["TSLA"]},
  "rebalance": "weekly",
  "filters": [{"factor": "trend", "days": 200, "min": 0}],
  "score": [{"factor": "momentum", "days": 126, "skip": 5, "weight": 1}],
  "hold": 15,
  "weighting": "equal",
  "max_weight": 0.1,
  "market": {"factor": "trend", "days": 200, "min": 0, "cash": 1}
}
```

## Fields

| Field | What it is | Values |
|---|---|---|
| `format` | Always `"markethub-bot/1"`. | |
| `name` | The bot's name, shown on the board. | 3 to 40 characters |
| `about` | One or two sentences on its idea, shown on the board. Optional. | up to 280 characters |
| `universe` | The companies it chooses among: either `{"largest": N}`, the N largest US companies by market value, or `{"tickers": [...]}`, a list of your own, each one among the 500 largest. `exclude` leaves some out. Funds (ETFs) are never in. | `largest` 20 to 500; `tickers` 2 to 100; `exclude` up to 100 |
| `rebalance` | How often it looks again: at every close, at the first close of each week, or of each month. | `"daily"`, `"weekly"` (default), `"monthly"` |
| `filters` | Conditions a stock must meet to be considered: a factor (below) with a `min`, a `max` or both. Optional. | up to 8 |
| `score` | How the stocks that pass are ranked: factors, each with a `weight`. Each factor is standardised across the stocks (a z-score, capped at ±3) and the weighted sum is the score. A negative weight prefers the lowest values. | 1 to 8; `weight` −5 to 5, not 0 |
| `hold` | How many of the best scored it holds. If fewer pass the filters, it holds those. | 1 to 50 |
| `weighting` | How the money is shared: in equal parts, more to the calmer ones (inverse of the 63-session volatility), or more to the better scored (by rank). | `"equal"` (default), `"inverse_volatility"`, `"score"` |
| `max_weight` | The most one stock can be. What is over goes to the others; what none can take stays in cash. Optional. | 0.02 to 1 (default 1) |
| `market` | A switch on the whole market, the S&P 500 (SPY): a factor with `min` and/or `max`. While SPY is inside those bounds the bot is invested; when it is not, `cash` of the portfolio (a share, 1 = all of it) goes to cash. Optional. | `cash` above 0, up to 1 (default 1) |

Unknown fields are refused, so a typo is caught by `check`.

## Factors

All of them are worked out from daily closes, at the close the bot decides on. A stock without
enough history for a factor is left out of any filter or score that uses it.

| Factor | Settings | What it is | Reads as |
|---|---|---|---|
| `momentum` | `days` 5–252, `skip` 0–63 (default 0) | The return over `days` sessions, ending `skip` sessions ago. | a fraction: 0.25 = +25% |
| `trend` | `days` 10–252 | Last close over its average of the last `days` closes, minus one. | a fraction: above 0 = over its average |
| `sma_cross` | `fast` 5–100, `slow` 20–252 (`fast` < `slow`) | Average of the last `fast` closes over that of the last `slow`, minus one. | a fraction: above 0 = short average over long |
| `volatility` | `days` 10–252 | Standard deviation of daily returns over `days` sessions, annualised. | a fraction: 0.30 = 30% a year |
| `rsi` | `days` 2–63 | Wilder's relative strength index. | 0 to 100 |
| `drawdown` | `days` 10–252 | Last close against the highest close of the last `days` sessions, minus one. | 0 at a high, −0.2 = 20% under it |
| `beta` | `days` 20–252 | How much the stock moved with the S&P 500 (SPY) over `days` sessions. | 1 = moves with the index |

A session is a trading day: 5 a week, about 21 a month, 63 a quarter, 126 half a year, 252 a year.

## How it is run and measured

- **Decisions at the close.** On a rebalance session, the bot decides with the closes up to that
  session and trades at that close. Between rebalances, the weights drift with the prices.
- **Costs.** Every trade pays 0.10% of what is traded (selling 5% of the portfolio and buying 5%
  of another stock is 10% traded, 0.01% of cost).
- **Price returns.** Dividends are left out, as in the monthly competition. Cash earns nothing.
- **The record starts at the next close.** A bot sent in at 11:00 New York time starts at that
  day's close; one sent in after 16:00, at the next session's. Nothing before counts.
- **Sending in another bot replaces the one you had and starts its record again.** One bot per member.
- **The universe is fixed when you send it in.** `{"largest": 300}` takes the 300 largest of that day.
- **The board** ranks the bots over the last day, week (5 sessions), month (21), year (252) and
  since each one started. A bot appears in a period once it has run that long.
- **What other members see:** your name, the bot's `name` and `about`, its returns and what it
  holds. The rules themselves are yours alone.

## Backtests

`backtest` runs the bot over the last 1 to 3 years, for you alone. It chooses among **today's**
largest companies, which did well to become so: the past always looks better than it was. Tune
too much to it and the bot learns the past, not the market. It says nothing about the future.

## The API

`tools/mh.py` does all of this. By hand, every call takes the key as a header,
`Authorization: Bearer <MARKETHUB_BOT_KEY>`, and JSON bodies:

| Call | Body | Answer |
|---|---|---|
| `GET /api/bot/spec` | (no key needed) | the limits above, as JSON |
| `POST /api/bot/check` | `{"bot": {...}}` | `{"ok": true, "rules": [...]}` or `{"detail": ..., "problems": [...]}` with status 400 |
| `POST /api/bot/backtest` | `{"bot": {...}, "years": 1}` | the backtest: returns, volatility, drawdown, months, holdings, against SPY |
| `PUT /api/bot` | `{"bot": {...}, "handle": "your name"}` | your bot as sent in. `handle` is only needed the first time you show anywhere in the community |
| `GET /api/bot` | | your bot: returns, rank, holdings, rules |

With curl:

```sh
curl -s -X POST "$MARKETHUB_URL/api/bot/check" -H "Authorization: Bearer $MARKETHUB_BOT_KEY" -H "Content-Type: application/json" -d "{\"bot\": $(cat bot.json)}"
```
