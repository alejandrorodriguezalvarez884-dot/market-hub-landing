"""My Hub: the user's positions valued at today's prices, taken apart and set against the indices.

Descriptive only: values, gains and losses against the user's own average cost, day moves, past
returns, what the portfolio is made of (by sector, country, volatility and size) and how much it
has moved. Nothing here suggests what to buy or sell.

Every return of the portfolio is that of today's holdings held through the period: trades are
not recorded, so it is not the user's real past performance, and the pages say so.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from . import insights
from .holdings import BENCHMARK, INDICES, SampleData, country_name, gather

SPARK_SESSIONS = 63  # three months
HISTORY_SPAN_DAYS = 372  # a year and a week: the return over one year needs a close a year back
PERIODS = [("1d", "Today"), ("1m", "1 month"), ("3m", "3 months"), ("ytd", "This year"), ("1y", "1 year")]
# How much a holding moved over the last year, annualised: below the first figure it is "Low".
VOLATILITY = [("Low", 0.20), ("Medium", 0.35), ("High", math.inf)]
SIZES = [("Mega cap", 200e9), ("Large cap", 10e9), ("Mid cap", 2e9), ("Small cap", 0.0)]
FUND = "ETF / fund"


def _ret(closes: list[float], sessions: int) -> float | None:
    if len(closes) <= sessions or not closes[-1 - sessions]:
        return None
    return closes[-1] / closes[-1 - sessions] - 1


def _since(bars: list[dict], days: int) -> float | None:
    """Return from the last close on or before ``days`` ago."""
    if not bars:
        return None
    cutoff = (date.fromisoformat(bars[-1]["date"]) - timedelta(days=days)).isoformat()
    before = [b for b in bars if b["date"] <= cutoff]
    if not before or not before[-1]["close"]:
        return None
    return bars[-1]["close"] / before[-1]["close"] - 1


def _ytd(bars: list[dict]) -> float | None:
    if not bars:
        return None
    year = bars[-1]["date"][:4]
    before = [b for b in bars if b["date"][:4] < year]
    return bars[-1]["close"] / before[-1]["close"] - 1 if before and before[-1]["close"] else None


def _returns(bars: list[dict]) -> dict:
    return {"return_1m": _since(bars, 30), "return_3m": _since(bars, 91), "return_ytd": _ytd(bars), "return_1y": _since(bars, 365)}


def _facts(bars: list[dict]) -> dict:
    return {**_returns(bars), "spark": [round(b["close"], 4) for b in bars[-SPARK_SESSIONS:]]}


def _moves(values: list[float]) -> list[float]:
    return [b / a - 1 for a, b in zip(values, values[1:]) if a]


def _annual(moves: list[float]) -> float | None:
    """The spread of daily moves, as a yearly figure."""
    if len(moves) < 20:
        return None
    mean = sum(moves) / len(moves)
    return math.sqrt(sum((m - mean) ** 2 for m in moves) / (len(moves) - 1)) * math.sqrt(252)


def volatility(bars: list[dict]) -> float | None:
    return _annual(_moves([b["close"] for b in bars[-253:]]))


def _deepest_fall(values: list[float]) -> float | None:
    """The largest fall from a peak, as a negative fraction."""
    peak, worst = 0.0, 0.0
    for v in values:
        peak = max(peak, v)
        if peak:
            worst = min(worst, v / peak - 1)
    return worst if values else None


def volatility_group(v: float | None) -> str:
    return next(name for name, below in VOLATILITY if v < below) if v is not None else "Unknown"


def size_group(cap: float | None, fund: bool) -> str:
    if fund:
        return FUND
    return next(name for name, floor in SIZES if cap >= floor) if cap else "Unknown"


def grouped(rows: list[dict], key: str, total: float, order: list[str] | None = None) -> list[dict]:
    """The positions gathered by ``key``: each group's share of the portfolio and its returns,
    which are those of its members weighted by their value."""
    members: dict[str, list[dict]] = {}
    for r in rows:
        if r["value"] is not None:
            members.setdefault(r[key], []).append(r)
    out = []
    for label, group in members.items():
        value = sum(r["value"] for r in group)
        day = sum(r["day_change"] or 0.0 for r in group)

        def mean(field: str, group=group) -> float | None:
            have = [r for r in group if r[field] is not None]
            weight = sum(r["value"] for r in have)
            return sum(r[field] * r["value"] for r in have) / weight if weight else None

        out.append({"label": label, "value": value, "weight": value / total if total else None, "count": len(group),
                    "tickers": [r["ticker"] for r in sorted(group, key=lambda r: -r["value"])],
                    "day_change_pct": day / (value - day) if value - day else None, "volatility": mean("volatility"),
                    **{f: mean(f) for f in ("return_1m", "return_3m", "return_ytd", "return_1y")}})
    rank = {name: i for i, name in enumerate(order or [])}
    return sorted(out, key=lambda g: (rank.get(g["label"], len(rank)), -g["value"]))


def holdings_history(positions: list[dict], histories: dict[str, list[dict]], bench: list[dict],
                     days: int = HISTORY_SPAN_DAYS, others: dict[str, list[dict]] | None = None) -> dict:
    """Daily value of the current holdings over the last year, on the dates every holding and
    the benchmark have a close, and all of it rebased to 100: the holdings, the benchmark and
    the ``others`` (more indices, where they have a close that day or the one before)."""
    empty = {"dates": [], "value": [], "portfolio_rebased": [], "benchmark_rebased": [], "indices": {}}
    tickers = [p["ticker"] for p in positions if histories.get(p["ticker"])]
    if not tickers or not bench:
        return empty
    cutoff = (date.fromisoformat(bench[-1]["date"]) - timedelta(days=days)).isoformat()
    by = {t: {b["date"]: b["close"] for b in histories[t]} for t in tickers}
    bench_by = {b["date"]: b["close"] for b in bench}
    dates = sorted(d for d in bench_by if d >= cutoff and all(d in by[t] for t in tickers))
    if not dates:
        return empty
    shares = {p["ticker"]: p["shares"] for p in positions}
    value = [sum(shares[t] * by[t][d] for t in tickers) for d in dates]
    indices = {BENCHMARK: [round(bench_by[d] / bench_by[dates[0]] * 100, 2) for d in dates]}
    for ticker, bars in (others or {}).items():
        closes, last, series = {b["date"]: b["close"] for b in bars}, None, []
        for d in dates:
            last = closes.get(d, last)
            series.append(last)
        if series[0]:
            indices[ticker] = [round(c / series[0] * 100, 2) for c in series]
    return {"dates": dates, "value": [round(v, 2) for v in value], "portfolio_rebased": [round(v / value[0] * 100, 2) for v in value],
            "benchmark_rebased": indices[BENCHMARK], "benchmark": BENCHMARK, "indices": indices}


def _risk(rows: list[dict], history: dict, bench: list[dict]) -> dict:
    """How much the portfolio moves and how concentrated it is."""
    valued = sorted((r for r in rows if r["weight"]), key=lambda r: -r["weight"])
    weights = [r["weight"] for r in valued]
    out = {"volatility": None, "beta": None, "benchmark_volatility": None, "max_drawdown": None, "best_day": None, "worst_day": None,
           "up_days": None, "top1": weights[0] if weights else None, "top3": sum(weights[:3]) if weights else None,
           "top3_tickers": [r["ticker"] for r in valued[:3]],
           # A portfolio of N equal positions scores N: one that is mostly a single stock scores near 1.
           "effective_positions": 1 / sum(w * w for w in weights) if weights else None,
           "dividend_yield": sum(r["weight"] * (r["dividend_yield"] or 0.0) for r in valued) if valued else None}
    values, dates = history["value"], history["dates"]
    if len(values) < 21:
        return out
    moves = _moves(values)
    bench_by = {b["date"]: b["close"] for b in bench}
    index = _moves([bench_by[d] for d in dates])
    if len(index) == len(moves):
        mean_p, mean_i = sum(moves) / len(moves), sum(index) / len(index)
        spread = sum((i - mean_i) ** 2 for i in index)
        out["beta"] = sum((p - mean_p) * (i - mean_i) for p, i in zip(moves, index)) / spread if spread else None
        out["benchmark_volatility"] = _annual(index)
    best, worst = max(range(len(moves)), key=moves.__getitem__), min(range(len(moves)), key=moves.__getitem__)
    out.update(volatility=_annual(moves), max_drawdown=_deepest_fall(values), up_days=sum(m > 0 for m in moves) / len(moves),
               best_day={"date": dates[best + 1], "return": moves[best]}, worst_day={"date": dates[worst + 1], "return": moves[worst]})
    return out


def build(doc: dict, market, stand_in: SampleData | None = None, sample: bool = False) -> dict:
    """The whole of My Hub for one user's document. ``stand_in`` answers when the provider does
    not, and the answer then says ``"sample": True``."""
    positions = doc.get("positions", [])
    watchlist = doc.get("watchlist", [])
    held = [p["ticker"] for p in positions]
    index_tickers = [t for t, _ in INDICES]
    tickers = list(dict.fromkeys(held + watchlist + index_tickers))
    notes: list[str] = []

    got = gather(market, tickers, held, stand_in, sample)
    quotes, histories, profiles = got.quotes, got.histories, got.profiles

    rows = []
    for p in positions:
        q = quotes.get(p["ticker"], {})
        price = q.get("price")
        value = price * p["shares"] if price is not None else None
        cost = p["avg_cost"] * p["shares"] if p.get("avg_cost") is not None else None
        prof = profiles.get(p["ticker"], {})
        bars = histories.get(p["ticker"], [])
        fund = bool(prof.get("is_etf"))
        cap = prof.get("market_cap") or q.get("market_cap")
        moved = volatility(bars)
        high = q.get("year_high")
        rows.append({
            "ticker": p["ticker"],
            "name": q.get("name") or prof.get("name") or p["ticker"],
            "sector": (FUND if fund else prof.get("sector")) or "Other",
            "country": "Funds" if fund else country_name(prof.get("country")),
            "shares": p["shares"],
            "avg_cost": p.get("avg_cost"),
            "price": price,
            "value": value,
            "cost": cost,
            "pnl": value - cost if value is not None and cost is not None else None,
            "pnl_pct": value / cost - 1 if value is not None and cost else None,
            "day_change": q["change"] * p["shares"] if q.get("change") is not None else None,
            "day_change_pct": q.get("change_pct") / 100 if q.get("change_pct") is not None else None,
            "beta": prof.get("beta"),
            "volatility": moved,
            "volatility_group": volatility_group(moved),
            "market_cap": cap,
            "size": size_group(cap, fund),
            "dividend_yield": prof["last_dividend"] / price if prof.get("last_dividend") and price else None,
            "from_high_52w": price / high - 1 if price is not None and high else None,
            **_facts(bars),
        })
        if price is None:
            notes.append(f"No price for {p['ticker']} right now.")

    total_value = sum(r["value"] for r in rows if r["value"] is not None)
    with_cost = [r for r in rows if r["cost"] is not None and r["value"] is not None]
    total_cost = sum(r["cost"] for r in with_cost)
    day = sum(r["day_change"] for r in rows if r["day_change"] is not None)
    before = total_value - day
    for r in rows:
        r["weight"] = r["value"] / total_value if r["value"] is not None and total_value else None
        # How many points of the portfolio's move today are this position's.
        r["day_contribution"] = r["day_change"] / before if r["day_change"] is not None and before else None

    watch = []
    for t in watchlist:
        q = quotes.get(t, {})
        high, price = q.get("year_high"), q.get("price")
        watch.append({
            "ticker": t,
            "name": q.get("name") or t,
            "price": price,
            "day_change_pct": q.get("change_pct") / 100 if q.get("change_pct") is not None else None,
            "from_high_52w": price / high - 1 if price is not None and high else None,
            "year_low": q.get("year_low"), "year_high": high,
            **_facts(histories.get(t, [])),
        })
        if price is None:
            notes.append(f"No price for {t} right now.")

    bench = histories.get(BENCHMARK, [])
    history = holdings_history(positions, histories, bench, others={t: histories.get(t, []) for t in index_tickers[1:]})
    series = [{"date": d, "close": v} for d, v in zip(history["dates"], history["value"])]
    day_pct = day / before if rows and before else None
    own = {"1d": day_pct, **{k[7:]: v for k, v in _returns(series).items()}}
    indices = []
    for ticker, name in INDICES:
        q, bars = quotes.get(ticker, {}), histories.get(ticker, [])
        indices.append({"ticker": ticker, "name": name, "price": q.get("price"),
                        "day_change_pct": q.get("change_pct") / 100 if q.get("change_pct") is not None else None, **_facts(bars)})
    periods = [{"key": key, "label": label, "portfolio": own.get(key) if rows else None,
                "indices": {i["ticker"]: i["day_change_pct"] if key == "1d" else i[f"return_{key}"] for i in indices}}
               for key, label in PERIODS]

    movers = sorted((x for x in rows + watch if x.get("day_change_pct") is not None), key=lambda x: x["day_change_pct"])
    sectors = grouped(rows, "sector", total_value)
    out = {
        "sample": got.sample,
        "totals": {
            "value": total_value if rows else None,
            "cost": total_cost if with_cost else None,
            "pnl": total_value_with_cost(with_cost) - total_cost if with_cost else None,
            "pnl_pct": (total_value_with_cost(with_cost) / total_cost - 1) if with_cost and total_cost else None,
            "day_change": day if rows else None,
            "day_change_pct": day_pct,
            "positions": len(rows),
            "cost_covers": len(with_cost),
        },
        "positions": sorted(rows, key=lambda r: -(r["value"] or 0)),
        "sectors": [{"sector": g["label"], "value": g["value"], "weight": g["weight"]} for g in sectors],
        "groups": [
            {"key": "sector", "label": "Sector", "items": sectors},
            {"key": "country", "label": "Country", "note": "Where each company has its head office.",
             "items": grouped(rows, "country", total_value)},
            {"key": "volatility", "label": "Volatility",
             "note": "How much each holding's price moved over the last year, as a yearly figure: under 20% is low, 35% or more is high.",
             "items": grouped(rows, "volatility_group", total_value, [name for name, _ in VOLATILITY])},
            {"key": "size", "label": "Size", "note": "By market value: mega from $200B, large from $10B, mid from $2B.",
             "items": grouped(rows, "size", total_value, [name for name, _ in SIZES] + [FUND])},
        ] if total_value else [],
        "history": history,
        "performance": {"periods": periods, "indices": [{"ticker": t, "name": n} for t, n in INDICES]},
        "risk": _risk(rows, history, bench),
        "watchlist": watch,
        "movers": {"up": [m["ticker"] for m in reversed(movers[-3:]) if m["day_change_pct"] > 0],
                   "down": [m["ticker"] for m in movers[:3] if m["day_change_pct"] < 0]},
        "benchmark": indices[0],
        "indices": indices,
        "notes": notes,
    }
    out["insights"] = insights.sentences(out)
    return out


def total_value_with_cost(rows: list[dict]) -> float:
    """Value of the positions that have an average cost, so gains compare like with like."""
    return sum(r["value"] for r in rows)
