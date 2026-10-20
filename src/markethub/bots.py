"""The community's bot competition: rules that pick stocks, run on paper by the portal.

A member's bot is a file of rules (FORMAT), not code: which of the largest US companies it looks
at, the figures it filters and scores them on (all of them worked out from daily closes), how many
it holds, how it shares the money between them and how often it looks again. The portal runs it
on paper, with no money and no broker: at the close of each session it rebalances on it takes the
weights its rules give, pays a cost on what it trades, and holds them to the next close. Cash
earns nothing; returns are on price (dividends apart), as in the monthly competition.

A bot is measured from the first close after it was sent in, never before: what it would have done
in the past (its backtest) is for its owner alone. Sending in another one starts the record again.
The record is kept session by session (its curve), so a stock that later leaves the provider's
lists does not change its past.

Nothing runs on a timer: a visit that finds the bots behind the last close asks for them to be
moved on (refresh), as it does with the news.

What is kept of a bot is the member's account id (which never leaves the server), the first name
of their account (shown next to the bot: never the surname, the email or the picture), a random
public id the bot's page is found by, the rules, the companies it could choose from when it was sent in, its
curve and what it holds, a log of its rebalances (what it held before and after each), and the
changes its owner made to it (each version of its rules, from the close it applied, and whether it
is paused). A change keeps the record: it applies from the next close, never backwards, and the
rules can change once a day. A bot's page says when its rules changed, not what they became. Members see the name, the bot's name and note, its returns and what it
holds; its rules are its owner's. Deleting the account deletes the bot and the key.

The key lets an agent on the member's own computer (Claude Code, Codex...) check, backtest and send
in a bot for them. Only its hash is kept; it can be replaced or taken back from the page, and it
opens nothing but the routes of the member's own bot.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import threading
import time
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock
from pathlib import Path
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from .community import SAMPLE_NAMES
from .config import (BOT_BACKTEST_YEARS_MAX, BOT_COST, BOT_HOLD_MAX, BOT_UNIVERSE_MAX, BOTS_CACHE_SECONDS, BOTS_LOCK_SECONDS,
                     BOTS_MAX, BOTS_REFRESH_SECONDS, DATA_DIR, FIRESTORE_DATABASE)
from .holdings import BENCHMARK
from .market import MarketUnavailable
from .opinion import publishable

FORMAT = "markethub-bot/1"
NEW_YORK = ZoneInfo("America/New_York")
BELL = clock(16, 0)
SETTLED = clock(16, 30)  # a session's close is taken as final this long after the bell
YEAR = 252  # sessions
# The periods of the board: a key, its name and how many sessions back it looks.
PERIODS = [("1d", "Day", 1), ("1w", "Week", 5), ("1m", "Month", 21), ("1y", "Year", YEAR)]
SHOWN = 200  # lines of the board sent to the page
SHOWN_HOLDINGS = 12
LOG_KEPT = 260  # rebalances kept in a bot's log, the latest
VERSIONS_KEPT = 100
LOGGED_TURNOVER = 0.0005  # a rebalance that trades less than this is not logged
MOVED = 0.005  # in the log, a weight that moved less than this is drift, not a change
PLAYER = "Member"  # shown for an account with no first name to show


def first_name(name) -> str:
    """The first name of an account, as the board shows a player: no surname, email or picture."""
    first = (str(name or "").split() or [""])[0][:30]
    return first if first and publishable(first) else PLAYER


def public_id() -> str:
    """A bot's id on the board and in its page's address: random, and kept for the bot."""
    return secrets.token_hex(5)
KEY_PREFIX = "mhb_"
# The example bots of Bot League's kit (market-hub-bots), copied here: the stand-ins of the board
# while its figures are sample ones, and a check that the format still takes them.
EXAMPLES = Path(__file__).parent / "bot_examples"

# Each figure a bot can filter or score on, worked out from daily closes: its settings, each with
# its lowest and highest value and its default (None: it must be given).
FACTORS: dict[str, dict[str, tuple[int, int, int | None]]] = {
    "momentum": {"days": (5, YEAR, None), "skip": (0, 63, 0)},
    "trend": {"days": (10, YEAR, None)},
    "sma_cross": {"fast": (5, 100, None), "slow": (20, YEAR, None)},
    "volatility": {"days": (10, YEAR, None)},
    "rsi": {"days": (2, 63, None)},
    "drawdown": {"days": (10, YEAR, None)},
    "beta": {"days": (20, YEAR, None)},
}
FACTOR_NOTES = {
    "momentum": "Return over `days` sessions, ending `skip` sessions ago. 0.25 is +25%.",
    "trend": "Last close over its average of the last `days` closes, minus one. Above 0: over the average.",
    "sma_cross": "Average of the last `fast` closes over that of the last `slow`, minus one. Above 0: the short average is over the long one.",
    "volatility": "Standard deviation of daily returns over `days` sessions, a year's worth. 0.30 is 30%.",
    "rsi": "Wilder's relative strength index over `days` sessions, from 0 to 100.",
    "drawdown": "Last close against the highest close of the last `days` sessions, minus one. 0 at a high, -0.2 for 20% below it.",
    "beta": "How much the stock has moved with the S&P 500 (SPY) over `days` sessions. 1 moves with it.",
}
PERCENT = {"momentum", "trend", "sma_cross", "volatility", "drawdown"}  # figures that read as a percentage
REBALANCE = ("daily", "weekly", "monthly")
WEIGHTING = ("equal", "inverse_volatility", "score")
FIELDS = {"format", "name", "about", "universe", "rebalance", "filters", "score", "hold", "weighting", "max_weight", "market"}
TICKER = re.compile(r"[A-Z][A-Z0-9\-]{0,9}")
USER_ID = re.compile(r"[A-Za-z0-9_\-]{1,128}")


class Refused(ValueError):
    """A bot, or a request about one, that cannot be taken: every reason, to tell its author."""

    def __init__(self, problems: list[str] | str):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__(" ".join(self.problems))


def _iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat(timespec="seconds")


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text)


def digest(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# --- The rules -----------------------------------------------------------------------------------


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _ticker(v) -> str | None:
    t = str(v).strip().upper().replace(".", "-") if isinstance(v, str) else ""
    return t if TICKER.fullmatch(t) else None


def _factor(raw, where: str, extra: set[str], problems: list[str]) -> dict | None:
    """A factor with its settings; ``extra`` are the other fields the place it is used in takes."""
    if not isinstance(raw, dict):
        problems.append(f'{where}: each one is an object with a "factor".')
        return None
    name = raw.get("factor")
    if name not in FACTORS:
        problems.append(f'{where}: "factor" is one of {", ".join(FACTORS)}.')
        return None
    allowed = {"factor", *FACTORS[name], *extra}
    for k in raw:
        if k not in allowed:
            problems.append(f'{where}: {name} has no field "{k}" (it takes {", ".join(sorted(allowed - {"factor"}))}).')
    out = {"factor": name}
    for k, (low, high, default) in FACTORS[name].items():
        v = raw.get(k, default)
        if v is None:
            problems.append(f'{where}: {name} needs "{k}", a whole number from {low} to {high}.')
        elif not _number(v) or v != int(v) or not low <= v <= high:
            problems.append(f'{where}: {name}\'s "{k}" is a whole number from {low} to {high}.')
        else:
            out[k] = int(v)
    if name == "sma_cross" and out.get("fast", 0) >= out.get("slow", 10**6):
        problems.append(f'{where}: sma_cross\'s "fast" is shorter than its "slow".')
    return out


def _bounds(raw: dict, out: dict, where: str, problems: list[str]) -> None:
    for k in ("min", "max"):
        if k in raw:
            if _number(raw[k]):
                out[k] = float(raw[k])
            else:
                problems.append(f'{where}: "{k}" is a number.')
    if "min" not in raw and "max" not in raw:
        problems.append(f'{where}: give a "min", a "max" or both.')
    elif out.get("min", -math.inf) > out.get("max", math.inf):
        problems.append(f'{where}: "min" is above "max".')


def _tickers(raw, where: str, low: int, high: int, problems: list[str]) -> list[str]:
    if not isinstance(raw, list) or not low <= len(raw) <= high:
        problems.append(f"{where} is a list of {low} to {high} tickers.")
        return []
    out = []
    for v in raw:
        t = _ticker(v)
        if not t:
            problems.append(f"{where}: {json.dumps(v)} is not a ticker.")
        elif t in out:
            problems.append(f"{where}: {t} is there twice.")
        else:
            out.append(t)
    return out


def check(raw) -> dict:
    """The bot a member's file describes, with every default filled in. Refused, with every
    problem found, when it is not one."""
    if not isinstance(raw, dict):
        raise Refused("A bot is a JSON object: see SPEC.md in the kit.")
    problems: list[str] = []
    for k in raw:
        if k not in FIELDS:
            problems.append(f'There is no field "{k}" (a bot takes {", ".join(sorted(FIELDS))}).')
    if raw.get("format") != FORMAT:
        problems.append(f'"format" is "{FORMAT}".')
    out: dict = {"format": FORMAT}

    name = " ".join(str(raw.get("name") or "").split())
    if not 3 <= len(name) <= 40:
        problems.append('"name" is the bot\'s name, 3 to 40 characters.')
    elif not publishable(name):
        problems.append('That "name" cannot be shown.')
    about = " ".join(str(raw.get("about") or "").split())
    if len(about) > 280:
        problems.append('"about" is at most 280 characters.')
    elif about and not publishable(about):
        problems.append('That "about" cannot be shown.')
    out.update(name=name, about=about)

    u = raw.get("universe")
    if not isinstance(u, dict):
        problems.append('"universe" is an object: {"largest": 500} or {"tickers": [...]}.')
    else:
        universe: dict = {}
        for k in u:
            if k not in ("largest", "tickers", "exclude"):
                problems.append(f'"universe" has no field "{k}" (it takes largest, tickers and exclude).')
        if ("largest" in u) == ("tickers" in u):
            problems.append('"universe" takes "largest" or "tickers", one of the two.')
        elif "largest" in u:
            v = u["largest"]
            if not _number(v) or v != int(v) or not 20 <= v <= BOT_UNIVERSE_MAX:
                problems.append(f'"universe.largest" is a whole number from 20 to {BOT_UNIVERSE_MAX}.')
            else:
                universe["largest"] = int(v)
        else:
            universe["tickers"] = _tickers(u["tickers"], '"universe.tickers"', 2, 100, problems)
        universe["exclude"] = _tickers(u["exclude"], '"universe.exclude"', 0, 100, problems) if "exclude" in u else []
        out["universe"] = universe

    rebalance = raw.get("rebalance", "weekly")
    if rebalance not in REBALANCE:
        problems.append(f'"rebalance" is one of {", ".join(REBALANCE)}.')
    out["rebalance"] = rebalance

    filters = raw.get("filters", [])
    if not isinstance(filters, list) or len(filters) > 8:
        problems.append('"filters" is a list of at most 8.')
        filters = []
    out["filters"] = []
    for n, f in enumerate(filters, 1):
        got = _factor(f, f"filters[{n}]", {"min", "max"}, problems)
        if got is not None:
            _bounds(f, got, f"filters[{n}]", problems)
            out["filters"].append(got)

    score = raw.get("score")
    if not isinstance(score, list) or not 1 <= len(score) <= 8:
        problems.append('"score" is a list of 1 to 8 factors, each with a "weight".')
        score = []
    out["score"] = []
    for n, s in enumerate(score, 1):
        got = _factor(s, f"score[{n}]", {"weight"}, problems)
        if got is None:
            continue
        w = s.get("weight")
        if not _number(w) or w == 0 or not -5 <= w <= 5:
            problems.append(f'score[{n}]: "weight" is a number from -5 to 5, not 0 (below 0 prefers the lowest).')
        else:
            got["weight"] = float(w)
        out["score"].append(got)

    hold = raw.get("hold")
    if not _number(hold) or hold != int(hold) or not 1 <= hold <= BOT_HOLD_MAX:
        problems.append(f'"hold" is how many stocks it holds, a whole number from 1 to {BOT_HOLD_MAX}.')
    else:
        out["hold"] = int(hold)
    weighting = raw.get("weighting", "equal")
    if weighting not in WEIGHTING:
        problems.append(f'"weighting" is one of {", ".join(WEIGHTING)}.')
    out["weighting"] = weighting
    cap = raw.get("max_weight", 1)
    if not _number(cap) or not 0.02 <= cap <= 1:
        problems.append('"max_weight" is the most one stock can be, from 0.02 to 1.')
    else:
        out["max_weight"] = float(cap)

    if raw.get("market") is not None:
        m = raw["market"]
        got = _factor(m, '"market"', {"min", "max", "cash"}, problems)
        if got is not None:
            _bounds(m, got, '"market"', problems)
            cash = m.get("cash", 1)
            if not _number(cash) or not 0 < cash <= 1:
                problems.append('"market.cash": the share held in cash when the market is out of its bounds, above 0 and up to 1.')
            else:
                got["cash"] = float(cash)
            out["market"] = got
    if problems:
        raise Refused(problems)
    return out


def resolve(bot: dict, largest: Callable[[int], list[str]]) -> list[str]:
    """The companies a bot chooses among, as of today. Refused when one is not among the largest."""
    pool = largest(BOT_UNIVERSE_MAX)
    u = bot["universe"]
    if "largest" in u:
        chosen = pool[:u["largest"]]
    else:
        known = set(pool)
        outside = [t for t in u["tickers"] if t not in known]
        if outside:
            raise Refused(f"Not among the {BOT_UNIVERSE_MAX} largest US companies (funds are left out): {', '.join(outside)}.")
        chosen = list(u["tickers"])
    chosen = [t for t in chosen if t not in set(u["exclude"])]
    if len(chosen) < 2:
        raise Refused("The universe leaves fewer than two companies to choose from.")
    if bot["hold"] > len(chosen):
        raise Refused(f'"hold" is {bot["hold"]}, and the universe has {len(chosen)} companies.')
    return chosen


def needs(bot: dict) -> int:
    """How many sessions of closes the bot's figures look back over, at most."""
    out = 64 if bot["weighting"] == "inverse_volatility" else 2
    for f in bot["filters"] + bot["score"] + ([bot["market"]] if bot.get("market") else []):
        out = max(out, f.get("days", 0) + f.get("skip", 0) + 1, f.get("slow", 0) + 1)
    return out


def _figure(name: str, v: float) -> str:
    if name in PERCENT:
        return f"{v * 100:+.0f}%".replace("+0%", "0%").replace("-", "−")
    return f"{v:g}".replace("-", "−")


def _what(f: dict) -> str:
    name = f["factor"]
    if name == "momentum":
        return f"its return over {f['days']} sessions" + (f", leaving out the last {f['skip']}" if f["skip"] else "")
    if name == "sma_cross":
        return f"its {f['fast']}-session average against its {f['slow']}-session one"
    return {"trend": "its close against its {days}-session average", "volatility": "its volatility over {days} sessions",
            "rsi": "its RSI over {days} sessions", "drawdown": "how far it is under its high of {days} sessions",
            "beta": "its beta to the S&P 500 over {days} sessions"}[name].format(**f)


def _range(f: dict) -> str:
    low, high = f.get("min"), f.get("max")
    if low is not None and high is not None:
        return f"between {_figure(f['factor'], low)} and {_figure(f['factor'], high)}"
    return f"at least {_figure(f['factor'], low)}" if low is not None else f"at most {_figure(f['factor'], high)}"


def describe(bot: dict, universe: list[str] | None = None) -> list[str]:
    """The rules of a bot in a few sentences, written by the code."""
    u = bot["universe"]
    if "largest" in u:
        out = [f"Looks at the {u['largest']} largest US companies" + (f", leaving out {', '.join(u['exclude'])}." if u["exclude"] else ".")]
    else:
        names = universe if universe is not None else [t for t in u["tickers"] if t not in u["exclude"]]
        out = [f"Looks at {len(names)} companies: {', '.join(names[:12])}{'…' if len(names) > 12 else ''}."]
    for f in bot["filters"]:
        out.append(f"Keeps those where {_what(f)} is {_range(f)}.")
    terms = [f"{_what(s)} ({'higher' if s['weight'] > 0 else 'lower'} is better, weight {abs(s['weight']):g})" for s in bot["score"]]
    out.append("Scores them on " + "; ".join(terms) + ".")
    parts = {"equal": "in equal parts", "inverse_volatility": "the calmer ones with more", "score": "the best scored with more"}
    cap = f", none above {bot['max_weight'] * 100:.0f}%" if bot["max_weight"] < 1 else ""
    out.append(f"Holds the best {bot['hold']}, {parts[bot['weighting']]}{cap}.")
    out.append({"daily": "Looks again at every close.", "weekly": "Looks again at the first close of each week.",
                "monthly": "Looks again at the first close of each month."}[bot["rebalance"]])
    if bot.get("market"):
        m = bot["market"]
        out.append(f"When, for the S&P 500, {_what(m)} is not {_range(m)}, holds {m['cash'] * 100:.0f}% in cash.")
    return out


def spec() -> dict:
    """What a bot can be, for the agent that writes one."""
    return {
        "format": FORMAT,
        "factors": {k: {"settings": {s: {"min": lo, "max": hi, **({"default": d} if d is not None else {})} for s, (lo, hi, d) in v.items()},
                        "means": FACTOR_NOTES[k]} for k, v in FACTORS.items()},
        "universe": {"largest": {"min": 20, "max": BOT_UNIVERSE_MAX}, "tickers": {"min": 2, "max": 100}, "exclude": {"max": 100}},
        "rebalance": list(REBALANCE), "weighting": list(WEIGHTING), "hold": {"min": 1, "max": BOT_HOLD_MAX},
        "max_weight": {"min": 0.02, "max": 1}, "filters": {"max": 8}, "score": {"min": 1, "max": 8, "weight": {"min": -5, "max": 5}},
        "cost": BOT_COST, "backtest_years": {"min": 1, "max": BOT_BACKTEST_YEARS_MAX},
    }


# --- Running a bot on paper ----------------------------------------------------------------------


class Prices:
    """Daily closes of many stocks on the benchmark's calendar of sessions, and the figures worked
    out from them, each once."""

    def __init__(self, closes: dict[str, list[tuple[str, float]]]):
        import pandas as pd

        bench = closes.get(BENCHMARK) or []
        if not bench:
            raise MarketUnavailable("The market data provider has no closes for the benchmark.")
        self.days = [d for d, _ in bench]
        columns = {t: pd.Series(dict((d, c) for d, c in rows if c and c > 0), dtype=float) for t, rows in closes.items() if rows}
        # A session a stock has no close for keeps its last one, for a few sessions.
        self.frame = pd.DataFrame(columns).reindex(self.days).ffill(limit=5)
        self.rets = self.frame.pct_change(fill_method=None)
        self.close = self.frame.to_numpy(dtype=float)
        self.col = {t: j for j, t in enumerate(self.frame.columns)}
        self._memo: dict[tuple, object] = {}

    def factor(self, f: dict):
        import numpy as np

        key = tuple((k, f[k]) for k in sorted(FACTORS[f["factor"]])) + (("factor", f["factor"]),)
        hit = self._memo.get(key)
        if hit is not None:
            return hit
        c, r, name = self.frame, self.rets, f["factor"]
        if name == "momentum":
            v = c.shift(f["skip"]) / c.shift(f["skip"] + f["days"]) - 1
        elif name == "trend":
            v = c / c.rolling(f["days"]).mean() - 1
        elif name == "sma_cross":
            v = c.rolling(f["fast"]).mean() / c.rolling(f["slow"]).mean() - 1
        elif name == "volatility":
            v = r.rolling(f["days"]).std() * math.sqrt(YEAR)
        elif name == "rsi":
            move = c.diff()
            up = move.clip(lower=0).ewm(alpha=1 / f["days"], min_periods=f["days"], adjust=False).mean()
            down = (-move.clip(upper=0)).ewm(alpha=1 / f["days"], min_periods=f["days"], adjust=False).mean()
            v = 100 - 100 / (1 + up / down)
        elif name == "drawdown":
            v = c / c.rolling(f["days"]).max() - 1
        else:  # beta
            m, n = r[BENCHMARK], f["days"]
            cov = r.mul(m, axis=0).rolling(n).mean() - r.rolling(n).mean().mul(m.rolling(n).mean(), axis=0)
            v = cov.div(m.rolling(n).var(ddof=0), axis=0)
        out = np.array(v.to_numpy(dtype=float), copy=True)
        out[~np.isfinite(out)] = np.nan
        self._memo[key] = out
        return out


def _cap(weights: list[float], cap: float) -> list[float]:
    """No weight above ``cap``: what is over goes to the others, in proportion, and what none of
    them can take stays in cash."""
    w = list(weights)
    for _ in range(len(w)):
        over = [k for k, x in enumerate(w) if x > cap + 1e-12]
        if not over:
            break
        excess = sum(w[k] - cap for k in over)
        for k in over:
            w[k] = cap
        free = [k for k, x in enumerate(w) if x < cap - 1e-12]
        room = sum(w[k] for k in free)
        if not free or room <= 0:
            break
        for k in free:
            w[k] += excess * w[k] / room
    return w


def _inside(v: float, f: dict) -> bool:
    return f.get("min", -math.inf) <= v <= f.get("max", math.inf)


def decide(bot: dict, universe: list[str], prices: Prices, i: int) -> dict[str, float]:
    """What a bot holds after the close of session ``i``: each stock's share of the portfolio."""
    import numpy as np

    names = [t for t in universe if t in prices.col]
    if not names:
        return {}
    idx = np.array([prices.col[t] for t in names])
    ok = np.isfinite(prices.close[i, idx])
    with np.errstate(invalid="ignore"):
        for f in bot["filters"]:
            v = prices.factor(f)[i, idx]
            ok &= np.isfinite(v) & (v >= f.get("min", -np.inf)) & (v <= f.get("max", np.inf))
        for s in bot["score"]:
            ok &= np.isfinite(prices.factor(s)[i, idx])
    keep = np.flatnonzero(ok)
    if keep.size == 0:
        return {}
    total = np.zeros(keep.size)
    for s in bot["score"]:
        v = prices.factor(s)[i, idx[keep]]
        sd = v.std()
        z = (v - v.mean()) / sd if sd > 0 else np.zeros(keep.size)
        total += s["weight"] * np.clip(z, -3, 3)
    order = sorted(range(keep.size), key=lambda k: (-total[k], names[keep[k]]))[:bot["hold"]]
    chosen = [names[keep[k]] for k in order]
    n = len(chosen)
    if bot["weighting"] == "score":
        raw = [float(n - k) for k in range(n)]
    elif bot["weighting"] == "inverse_volatility":
        vol = prices.factor({"factor": "volatility", "days": 63})[i, [prices.col[t] for t in chosen]]
        inv = [1 / v if np.isfinite(v) and v > 0 else None for v in vol]
        known = sorted(x for x in inv if x is not None)
        raw = [x if x is not None else (known[len(known) // 2] if known else 1.0) for x in inv]
    else:
        raw = [1.0] * n
    weights = _cap([x / sum(raw) for x in raw], bot["max_weight"])
    m = bot.get("market")
    if m:
        v = prices.factor(m)[i, prices.col[BENCHMARK]]
        if np.isfinite(v) and not _inside(float(v), m):
            weights = [w * (1 - m["cash"]) for w in weights]
    return {t: float(w) for t, w in zip(chosen, weights) if w > 1e-9}


def _due(rule: str, days: list[str], i: int) -> bool:
    if rule == "daily" or i == 0:
        return True
    a, b = date.fromisoformat(days[i - 1]), date.fromisoformat(days[i])
    if rule == "weekly":
        return a.isocalendar()[:2] != b.isocalendar()[:2]
    return (a.year, a.month) != (b.year, b.month)


def _rounded(w: dict[str, float]) -> dict[str, float]:
    return {t: round(x, 4) for t, x in sorted(w.items()) if x >= 0.00005}


def run(bot: dict, universe: list[str], prices: Prices, start: int, end: int, held: dict[str, float] | None = None,
        value: float = 1.0, log: list | None = None, force: bool = False,
        paused: bool = False) -> tuple[list[tuple[str, float]], dict[str, float], float]:
    """A bot from the close of session ``start`` to that of ``end``. Without ``held`` it starts in
    cash and buys at the close of ``start``; with it, it goes on from what it held the session
    before. Gives the value at each close, what it holds at the end and how much it traded.
    ``force`` rebalances at the close of ``start`` whatever the calendar says (rules that have just
    changed); ``paused`` holds cash at every rebalance; ``log`` gets each rebalance that traded."""
    curve: list[tuple[str, float]] = []
    traded = 0.0
    w = dict(held) if held is not None else None
    for i in range(start, end + 1):
        if w is None:
            w, rebalance = {}, True
        else:
            # The session's move: each holding by its close over the one before. A stock with no
            # close keeps its last one.
            grown = {}
            for t, x in w.items():
                j, r = prices.col.get(t), 0.0
                if j is not None:
                    a, b = prices.close[i - 1, j], prices.close[i, j]
                    if a == a and b == b and a > 0:
                        r = b / a - 1
                grown[t] = x * (1 + r)
            total = (1 - sum(w.values())) + sum(grown.values())
            value *= total
            w = {t: x / total for t, x in grown.items()} if total > 0 else {}
            rebalance = (force and i == start) or _due(bot["rebalance"], prices.days, i)
        if rebalance:
            target = {} if paused else decide(bot, universe, prices, i)
            turnover = sum(abs(target.get(t, 0.0) - w.get(t, 0.0)) for t in set(target) | set(w))
            value *= 1 - BOT_COST * turnover
            traded += turnover
            if log is not None and turnover > LOGGED_TURNOVER:
                log.append({"date": prices.days[i], "turnover": round(turnover, 6), "cost": round(BOT_COST * turnover, 6),
                            "before": _rounded(w), "after": _rounded(target)})
            w = target
        curve.append((prices.days[i], value))
    return curve, w, traded


def activity(log: list[dict], last: int | None = None) -> list[dict]:
    """A bot's rebalances, latest first: what it bought and sold outright, and what it raised or
    cut. Weights that only drifted back into place are left out."""
    out = []
    for e in reversed(log[-last:] if last else log):
        before, after = e.get("before") or {}, e.get("after") or {}
        moves = {t: (before.get(t, 0.0), after.get(t, 0.0)) for t in set(before) | set(after)}
        order = sorted(moves, key=lambda t: (-abs(moves[t][1] - moves[t][0]), t))
        out.append({"date": e["date"], "turnover": e["turnover"], "cost": e["cost"],
                    "bought": [{"ticker": t, "weight": moves[t][1]} for t in order if not moves[t][0] and moves[t][1]],
                    "sold": [{"ticker": t, "weight": moves[t][0]} for t in order if moves[t][0] and not moves[t][1]],
                    "raised": [{"ticker": t, "before": moves[t][0], "after": moves[t][1]} for t in order
                               if moves[t][0] and moves[t][1] - moves[t][0] >= MOVED],
                    "cut": [{"ticker": t, "before": moves[t][0], "after": moves[t][1]} for t in order
                            if moves[t][1] and moves[t][0] - moves[t][1] >= MOVED],
                    "after": after})
    return out


def changes(doc: dict, pending: dict) -> list[str]:
    """What a waiting change does to a bot, in words a page can show: "rules", "excluded NVDA",
    "included NVDA", "paused", "resumed"."""
    out: list[str] = []
    old, new = doc["spec"], pending.get("spec", doc["spec"])
    if new != old:
        a, b = set(old["universe"]["exclude"]), set(new["universe"]["exclude"])
        bare = lambda s: {**s, "universe": {**s["universe"], "exclude": []}}  # noqa: E731
        if bare(old) != bare(new):
            out.append("rules")
        out += [f"excluded {t}" for t in sorted(b - a)] + [f"included {t}" for t in sorted(a - b)]
    was, now = bool(doc.get("paused")), bool(pending.get("paused", doc.get("paused")))
    if was != now:
        out.append("paused" if now else "resumed")
    return out


def _edits(doc: dict) -> str:
    """What an owner's edits have set on a bot: a refresh keeps its work only if this has not moved."""
    return json.dumps([doc.get("pending"), doc.get("paused"), doc.get("rules_changed_utc"), doc.get("spec")], sort_keys=True)


def last_settled(days: list[str], now: datetime) -> int | None:
    """The last session whose close is final at ``now``."""
    local = now.astimezone(NEW_YORK)
    today = local.date().isoformat()
    for i in range(len(days) - 1, -1, -1):
        if days[i] < today or (days[i] == today and local.time() >= SETTLED):
            return i
    return None


def first_session(days: list[str], sent: datetime) -> int | None:
    """The first session that closes after a bot was sent in: its record starts there."""
    for i, d in enumerate(days):
        if datetime.combine(date.fromisoformat(d), BELL, NEW_YORK) > sent:
            return i
    return None


def returns(values: list[float]) -> dict:
    """Over each period of the board, and since the start (from 1, before the first purchase)."""
    out = {k: values[-1] / values[-1 - n] - 1 if len(values) > n and values[-1 - n] else None for k, _, n in PERIODS}
    out["all"] = values[-1] - 1 if values else None
    return out


def measure(values: list[float], days: list[str]) -> dict:
    """A curve that starts from 1 the session before ``days[0]``, read back."""
    series = [1.0] + list(values)
    daily = [b / a - 1 for a, b in zip(series, series[1:]) if a]
    mean = sum(daily) / len(daily) if daily else 0.0
    vol = math.sqrt(sum((x - mean) ** 2 for x in daily) / (len(daily) - 1)) * math.sqrt(YEAR) if len(daily) > 1 else None
    top, worst = 1.0, 0.0
    for v in series:
        top = max(top, v)
        worst = min(worst, v / top - 1)
    months: dict[str, float] = {}
    for d, v in zip(days, values):
        months[d[:7]] = v
    ends, by_month, before = list(months.items()), [], 1.0
    for m, v in ends:
        by_month.append({"month": m, "return": v / before - 1})
        before = v
    sessions = len(values)
    return {"total_return": series[-1] - 1, "annual_return": series[-1] ** (YEAR / sessions) - 1 if sessions >= 20 and series[-1] > 0 else None,
            "volatility": vol, "max_drawdown": worst, "months": by_month}


# --- What is kept ------------------------------------------------------------------------------


class BotStore(Protocol):
    def get(self, user_id: str) -> dict | None: ...
    def put(self, doc: dict) -> None: ...
    def delete(self, user_id: str) -> None: ...
    def all(self) -> list[dict]: ...
    def key(self, hashed: str) -> dict | None: ...
    def put_key(self, doc: dict) -> None: ...
    def delete_key(self, hashed: str) -> None: ...
    def keys_of(self, user_id: str) -> list[dict]: ...
    def meta(self) -> dict: ...
    def put_meta(self, doc: dict) -> None: ...


def _id(user_id: str) -> str:
    if not USER_ID.fullmatch(user_id):
        raise ValueError("bad user id")
    return user_id


class MemoryBots:
    def __init__(self):
        self.bots: dict[str, dict] = {}
        self.keys: dict[str, dict] = {}
        self.state: dict = {}

    def get(self, user_id):
        doc = self.bots.get(user_id)
        return json.loads(json.dumps(doc)) if doc else None

    def put(self, doc):
        self.bots[_id(doc["user_id"])] = json.loads(json.dumps(doc))

    def delete(self, user_id):
        self.bots.pop(user_id, None)

    def all(self):
        return [json.loads(json.dumps(d)) for d in self.bots.values()]

    def key(self, hashed):
        return dict(self.keys[hashed]) if hashed in self.keys else None

    def put_key(self, doc):
        self.keys[doc["hash"]] = dict(doc)

    def delete_key(self, hashed):
        self.keys.pop(hashed, None)

    def keys_of(self, user_id):
        return [dict(k) for k in self.keys.values() if k["user_id"] == user_id]

    def meta(self):
        return dict(self.state)

    def put_meta(self, doc):
        self.state = dict(doc)


class FileBots:
    """For local development only: data/bots/{bots,keys}/ and data/bots/meta.json."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "bots")
        self._lock = threading.Lock()

    def _path(self, folder: str, name: str) -> Path:
        return self.root / folder / f"{name}.json"

    def _write(self, path: Path, doc: dict) -> None:
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc), encoding="utf-8")

    def _read(self, folder: str) -> list[dict]:
        at = self.root / folder
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(at.glob("*.json"))] if at.is_dir() else []

    def get(self, user_id):
        path = self._path("bots", _id(user_id))
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def put(self, doc):
        self._write(self._path("bots", _id(doc["user_id"])), doc)

    def delete(self, user_id):
        self._path("bots", _id(user_id)).unlink(missing_ok=True)

    def all(self):
        return self._read("bots")

    def key(self, hashed):
        path = self._path("keys", hashed)
        return json.loads(path.read_text(encoding="utf-8")) if re.fullmatch(r"[0-9a-f]{64}", hashed) and path.exists() else None

    def put_key(self, doc):
        self._write(self._path("keys", doc["hash"]), doc)

    def delete_key(self, hashed):
        self._path("keys", hashed).unlink(missing_ok=True)

    def keys_of(self, user_id):
        return [k for k in self._read("keys") if k["user_id"] == user_id]

    def meta(self):
        path = self.root / "meta.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def put_meta(self, doc):
        self._write(self.root / "meta.json", doc)


def packed(value):
    """A document as Firestore takes it: an array cannot hold another array, so each row of a list
    of lists (a curve's [date, value], the index's [date, close]) is kept as {"row": [...]}."""
    if isinstance(value, dict):
        return {k: packed(v) for k, v in value.items()}
    if isinstance(value, list):
        return [{"row": packed(x)} if isinstance(x, list) else packed(x) for x in value]
    return value


def unpacked(value):
    """A document read from Firestore, with its rows back as the lists they were."""
    if isinstance(value, dict):
        if set(value) == {"row"} and isinstance(value["row"], list):
            return unpacked(value["row"])
        return {k: unpacked(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unpacked(x) for x in value]
    return value


class FirestoreBots:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        client = firestore.Client(database=database)
        self.where = lambda field, value: FieldFilter(field, "==", value)
        self.bots = client.collection("bots")
        self.keys = client.collection("bot_keys")
        self.state = client.collection("bot_meta").document("board")

    def get(self, user_id):
        snap = self.bots.document(_id(user_id)).get()
        return unpacked(snap.to_dict()) if snap.exists else None

    def put(self, doc):
        self.bots.document(_id(doc["user_id"])).set(packed(doc))

    def delete(self, user_id):
        self.bots.document(_id(user_id)).delete()

    def all(self):
        return [unpacked(s.to_dict()) for s in self.bots.limit(BOTS_MAX).stream()]

    def key(self, hashed):
        snap = self.keys.document(hashed).get()
        return snap.to_dict() if snap.exists else None

    def put_key(self, doc):
        self.keys.document(doc["hash"]).set(doc)

    def delete_key(self, hashed):
        self.keys.document(hashed).delete()

    def keys_of(self, user_id):
        return [s.to_dict() for s in self.keys.where(filter=self.where("user_id", user_id)).stream()]

    def meta(self):
        snap = self.state.get()
        return unpacked(snap.to_dict()) if snap.exists else {}

    def put_meta(self, doc):
        self.state.set(packed(doc))


def default_bots() -> BotStore:
    return FirestoreBots() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileBots()


# --- The competition ---------------------------------------------------------------------------


def examples() -> list[dict]:
    """The example bots of Bot League's kit."""
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(EXAMPLES.glob("*.json"))]


class Bots:
    def __init__(self, store: BotStore, closes: Callable[[set[str]], dict[str, list[tuple[str, float]]]],
                 largest: Callable[[int], list[str]], sample: bool = False, now: Callable[[], datetime] | None = None):
        """``closes`` gives the daily closes of some tickers, oldest first; ``largest(n)`` the n
        largest US companies, funds left out. ``sample``: the figures are sample ones, and
        stand-ins fill the board."""
        self.store, self.closes, self.largest, self.sample = store, closes, largest, sample
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._cached: tuple[float, dict] | None = None
        self._lock = threading.Lock()
        self._refreshing = threading.Lock()

    # --- The key ---

    def issue_key(self, user_id: str, name: str | None = None) -> str:
        """A new key for the member's agent. Their old one stops working. ``name`` is the account's
        name from the session it is made in: the agent's bots are shown under its first name."""
        self.revoke_key(user_id)
        key = KEY_PREFIX + secrets.token_urlsafe(32)
        self.store.put_key({"hash": digest(key), "user_id": user_id, "created_utc": _iso(self.now()), "used_utc": None,
                            "name": first_name(name)})
        return key

    def revoke_key(self, user_id: str) -> None:
        for k in self.store.keys_of(user_id):
            self.store.delete_key(k["hash"])

    def key_status(self, user_id: str) -> dict | None:
        mine = sorted(self.store.keys_of(user_id), key=lambda k: k["created_utc"])
        return {"created_utc": mine[-1]["created_utc"], "used_utc": mine[-1].get("used_utc")} if mine else None

    def who(self, key: str | None) -> str | None:
        """The member a key belongs to, or None."""
        if not key or not key.startswith(KEY_PREFIX) or len(key) > 100:
            return None
        doc = self.store.key(digest(key))
        if not doc:
            return None
        now = self.now()
        if not doc.get("used_utc") or now - _when(doc["used_utc"]) > timedelta(hours=1):
            self.store.put_key({**doc, "used_utc": _iso(now)})
        return doc["user_id"]

    # --- Checking, backtesting and sending in ---

    def check(self, raw) -> dict:
        bot = check(raw)
        universe = resolve(bot, self.largest)
        return {"ok": True, "bot": bot, "universe": len(universe), "rules": describe(bot, universe)}

    def backtest(self, raw, years: int = 1) -> dict:
        """What the bot would have done over the last years, for its owner: a simulation on past
        closes, among today's largest companies."""
        if not isinstance(years, int) or isinstance(years, bool) or not 1 <= years <= BOT_BACKTEST_YEARS_MAX:
            raise Refused(f'"years" is a whole number from 1 to {BOT_BACKTEST_YEARS_MAX}.')
        bot = check(raw)
        universe = resolve(bot, self.largest)
        prices = Prices(self.closes(set(universe) | {BENCHMARK}))
        end = last_settled(prices.days, self.now())
        if end is None or end - needs(bot) < 20:
            raise Refused("There are not enough closes to backtest on yet.")
        start = max(needs(bot), end - YEAR * years + 1)
        curve, held, traded = run(bot, universe, prices, start, end)
        days, values = [d for d, _ in curve], [v for _, v in curve]
        j = prices.col[BENCHMARK]
        base = prices.close[start - 1, j]
        bench = [float(prices.close[i, j] / base) for i in range(start, end + 1)]
        mine, theirs = measure(values, days), measure(bench, days)
        for m, b in zip(mine["months"], theirs["months"]):
            m["benchmark"] = b["return"]
        sessions = len(values)
        step = max(1, sessions // 160)
        return {
            "start": days[0], "end": days[-1], "sessions": sessions, "universe": len(universe), "rules": describe(bot, universe),
            "bot": {k: v for k, v in mine.items() if k != "months"}, "benchmark": {"ticker": BENCHMARK, **{k: v for k, v in theirs.items() if k != "months"}},
            "months": mine["months"], "turnover_per_year": traded / sessions * YEAR, "costs_per_year": traded / sessions * YEAR * BOT_COST,
            "holdings": [{"ticker": t, "weight": w} for t, w in sorted(held.items(), key=lambda x: -x[1])], "cash": max(0.0, 1 - sum(held.values())),
            "curve": [{"date": days[i], "bot": values[i], "benchmark": bench[i]} for i in sorted(set(range(0, sessions, step)) | {sessions - 1})],
            "notes": ["A simulation on past closes: no money, no orders, and nothing it says about the future.",
                      "It chooses among today's largest companies, which did well to become so: the past looks better than it was.",
                      f"It pays {BOT_COST * 100:.2f}% on what it trades. Dividends are left out, as in the competition."],
        }

    def _player(self, user_id: str, name: str | None, mine: dict | None) -> str:
        """The first name a member's bot is shown under: the session's, or the one kept with their key
        or their bot, never one sent with a request."""
        if name:
            return first_name(name)
        keys = sorted(self.store.keys_of(user_id), key=lambda k: k["created_utc"])
        return (keys[-1].get("name") if keys else None) or (mine or {}).get("handle") or PLAYER

    def submit(self, user_id: str, raw, name: str | None = None) -> dict:
        """Send in the member's bot, in place of the one they had: its record starts at the next close."""
        bot = check(raw)
        universe = resolve(bot, self.largest)
        mine = self.store.get(user_id)
        if not mine and len(self.store.all()) >= BOTS_MAX:
            raise Refused("The competition is full for now.")
        self.store.put({"user_id": user_id, "handle": self._player(user_id, name, mine), "public_id": (mine or {}).get("public_id") or public_id(),
                        "spec": bot, "universe": universe,
                        "submitted_utc": _iso(self.now()), "curve": [], "weights": {}, "as_of": None, "log": [],
                        "preview": self._holds(bot, universe)})
        self._cached = None
        return self.mine(user_id)

    # --- Changing it, keeping its record ---

    def _holds(self, bot: dict, universe: list[str]) -> dict | None:
        """What the rules would hold after the last close there is: a preview, never a record."""
        try:
            prices = Prices(self.closes(set(universe) | {BENCHMARK}))
        except MarketUnavailable:
            return None
        end = last_settled(prices.days, self.now())
        if end is None:
            return None
        held = decide(bot, universe, prices, end)
        return {"as_of": prices.days[end], "weights": {t: round(w, 6) for t, w in sorted(held.items(), key=lambda x: -x[1])}}

    def rename(self, user_id: str, name, about=None) -> dict:
        """A new name for the member's bot, and its idea if given: at once, keeping the record, and not
        the day's change of rules. Its page says it was renamed."""
        doc = self.store.get(user_id)
        if not doc:
            raise Refused("There is no bot to rename: send one in first.")
        checked = check({**doc["spec"], "name": name, "about": doc["spec"]["about"] if about is None else about})
        old = doc["spec"]["name"]
        for spec in [doc["spec"], *([doc["pending"]["spec"]] if (doc.get("pending") or {}).get("spec") else [])]:
            spec["name"], spec["about"] = checked["name"], checked["about"]
        if checked["name"] != old and doc.get("curve"):
            now = self.now()
            doc["versions"] = (list(doc.get("versions") or []) + [{"from": now.astimezone(NEW_YORK).date().isoformat(), "changed_utc": _iso(now),
                                                                   "what": [f"renamed from {old}"]}])[-VERSIONS_KEPT:]
        self.store.put(doc)
        self._cached = None
        return self.mine(user_id)

    def sync_player(self, user_id: str, name: str | None) -> None:
        """Show the member's bot, and their key's next bots, under the first name of the session they
        came with: a name changed on their account follows here."""
        first = first_name(name)
        doc = self.store.get(user_id)
        if doc and (doc.get("handle") != first or not doc.get("public_id")):
            self.store.put({**doc, "handle": first, "public_id": doc.get("public_id") or public_id()})
            self._cached = None
        for k in self.store.keys_of(user_id):
            if k.get("name") != first:
                self.store.put_key({**k, "name": first})

    def ensure_ids(self) -> int:
        """Give a public id to every bot sent in before bots had one."""
        done = 0
        for d in self.store.all():
            if not d.get("public_id"):
                there = self.store.get(d["user_id"])
                if there and not there.get("public_id"):
                    self.store.put({**there, "public_id": public_id()})
                    done += 1
        if done:
            self._cached = None
        return done

    def preview(self, raw) -> dict:
        """A bot's rules in words and what they would hold at the last close, before it is changed."""
        bot = check(raw)
        universe = resolve(bot, self.largest)
        return {"ok": True, "bot": bot, "universe": len(universe), "rules": describe(bot, universe), "holds": self._holds(bot, universe)}

    def _change(self, doc: dict, fields: dict) -> None:
        """A bot that has not started yet just becomes the new one; one with a record gets the change
        at its next close."""
        if not doc.get("curve"):
            doc.update(fields)
            if "spec" in fields:
                doc["preview"] = self._holds(doc["spec"], doc["universe"])
            return
        doc["pending"] = {**(doc.get("pending") or {}), **fields, "changed_utc": _iso(self.now())}

    def edit(self, user_id: str, raw) -> dict:
        """New rules for the member's bot, keeping its record: they apply from the next close and its
        page says when they changed. Once a day."""
        doc = self.store.get(user_id)
        if not doc:
            raise Refused("There is no bot to change: send one in first.")
        bot = check(raw)
        # The companies left out with the switch stay out: they come back with "include".
        state = {**doc, **(doc.get("pending") or {})}
        left_out = list(dict.fromkeys([*bot["universe"]["exclude"], *state["spec"]["universe"]["exclude"]]))
        if len(left_out) > 100:
            raise Refused("A bot leaves out at most 100 companies.")
        bot["universe"]["exclude"] = left_out
        universe = resolve(bot, self.largest)
        last = doc.get("rules_changed_utc")
        if last and _when(last).astimezone(NEW_YORK).date() == self.now().astimezone(NEW_YORK).date():
            raise Refused("The rules can change once a day. Try again tomorrow.")
        self._change(doc, {"spec": bot, "universe": universe})
        doc["rules_changed_utc"] = _iso(self.now())
        self.store.put(doc)
        self._cached = None
        return self.mine(user_id)

    def switch(self, user_id: str, action: str, ticker: str | None = None) -> dict:
        """Pause the bot (cash from the next close), resume it, or leave a company out of it or let it
        back in. Not a change of rules: it does not count as the day's change."""
        doc = self.store.get(user_id)
        if not doc:
            raise Refused("There is no bot to change: send one in first.")
        state = {**doc, **(doc.get("pending") or {})}  # the bot as it will be at the next close
        if action in ("pause", "resume"):
            fields: dict = {"paused": action == "pause"}
        elif action in ("exclude", "include"):
            t = _ticker(ticker or "")
            if not t:
                raise Refused("Give the ticker of a company.")
            spec = json.loads(json.dumps(state["spec"]))
            left_out = spec["universe"]["exclude"]
            if action == "exclude":
                if t in left_out:
                    raise Refused(f"{t} is already left out.")
                if t not in state["universe"] and t not in (doc.get("weights") or {}):
                    raise Refused(f"{t} is not among the companies the bot chooses from.")
                if len(left_out) >= 100:
                    raise Refused("A bot leaves out at most 100 companies.")
                left_out.append(t)
                universe = [x for x in state["universe"] if x != t]
                if len(universe) < 2 or spec["hold"] > len(universe):
                    raise Refused(f"Without {t} the bot would have too few companies to choose from.")
            else:
                if t not in left_out:
                    raise Refused(f"{t} is not left out.")
                left_out.remove(t)
                universe = resolve(spec, self.largest)
            fields = {"spec": spec, "universe": universe}
        else:
            raise Refused('The switches are "pause", "resume", "exclude" and "include".')
        self._change(doc, fields)
        self.store.put(doc)
        self._cached = None
        return self.mine(user_id)

    def withdraw(self, user_id: str) -> None:
        self.store.delete(user_id)
        self._cached = None

    # --- Moving the bots on ---

    def _advance(self, doc: dict, prices: Prices, end: int) -> bool:
        """Run a bot on from where it was to the close ``end``. A change waiting for its close applies
        there: the bot rebalances on its new rules at that close, and the version is logged."""
        days, curve = prices.days, doc.get("curve") or []
        if curve:
            start = bisect_right(days, curve[-1][0])
            if start > end or start == 0:
                return False
            held, value = doc.get("weights") or {}, curve[-1][1]
        else:
            start = first_session(days, _when(doc["submitted_utc"]))
            if start is None or start > end:
                return False
            held, value = None, 1.0
        log, new, force = list(doc.get("log") or []), [], False
        pending = doc.get("pending") if curve else None
        switch = first_session(days, _when(pending["changed_utc"])) if pending else None
        if pending and switch is not None and switch <= end:
            switch = max(switch, start)
            if switch > start:
                part, held, _ = run(doc["spec"], doc["universe"], prices, start, switch - 1, held=held, value=value, log=log,
                                    paused=bool(doc.get("paused")))
                new, value = part, part[-1][1]
            what = changes(doc, pending)
            if what:
                version = {"from": days[switch], "changed_utc": pending["changed_utc"], "what": what}
                if "spec" in pending and pending["spec"] != doc["spec"]:
                    version["spec"] = pending["spec"]
                doc["versions"] = (list(doc.get("versions") or []) + [version])[-VERSIONS_KEPT:]
                doc["spec"], doc["universe"] = pending.get("spec", doc["spec"]), pending.get("universe", doc["universe"])
                doc["paused"] = bool(pending.get("paused", doc.get("paused")))
                force = True
            doc.pop("pending", None)
            start = switch
        part, held, _ = run(doc["spec"], doc["universe"], prices, start, end, held=held, value=value, log=log, force=force,
                            paused=bool(doc.get("paused")))
        new += part
        doc["curve"] = curve + [[d, round(v, 6)] for d, v in new]
        doc["weights"] = {t: round(w, 6) for t, w in held.items() if w >= 5e-7}
        doc["log"] = log[-LOG_KEPT:]
        doc["as_of"] = days[end]
        doc.pop("preview", None)
        return True

    def behind(self) -> bool:
        """Whether a refresh is worth asking for: a bot is behind the last close there should
        be, and none was asked for lately."""
        meta, now = self.store.meta(), self.now()
        if meta.get("checked_utc") and now - _when(meta["checked_utc"]) < timedelta(seconds=BOTS_REFRESH_SECONDS):
            return False
        local = now.astimezone(NEW_YORK)
        day = local.date() if local.time() >= SETTLED else local.date() - timedelta(days=1)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        expected = day.isoformat()
        for b in self._state()["rows"]:  # kept in memory: a visit does not read every bot again
            if b["stand_in"]:
                continue
            if b.get("as_of") and b["as_of"] < expected:
                return True
            if not b.get("as_of") and _when(b["submitted_utc"]) < datetime.combine(day, BELL, NEW_YORK):
                return True
        return False

    def refresh(self, force: bool = False) -> dict:
        """Move every bot on to the last close. Once at a time, and not again for a while."""
        if not self._refreshing.acquire(blocking=False):
            return {"moved": 0, "busy": True}
        try:
            meta, now = self.store.meta(), self.now()
            if meta.get("running_utc") and now - _when(meta["running_utc"]) < timedelta(seconds=BOTS_LOCK_SECONDS):
                return {"moved": 0, "busy": True}
            if not force and meta.get("checked_utc") and now - _when(meta["checked_utc"]) < timedelta(seconds=BOTS_REFRESH_SECONDS):
                return {"moved": 0}
            self.store.put_meta({**meta, "running_utc": _iso(now)})
            moved, done = 0, {**meta, "checked_utc": _iso(now)}
            try:
                docs = self.store.all()
                if docs:
                    tickers = {t for d in docs for t in d["universe"]} | {t for d in docs for t in d.get("weights") or {}}
                    prices = Prices(self.closes(tickers | {BENCHMARK}))
                    end = last_settled(prices.days, now)
                    if end is not None:
                        for doc in docs:
                            seen = _edits(doc)
                            if self._advance(doc, prices, end):
                                # Kept only if it is still the bot that was read: not withdrawn, replaced or changed meanwhile.
                                there = self.store.get(doc["user_id"])
                                if there and there["submitted_utc"] == doc["submitted_utc"] and _edits(there) == seen:
                                    self.store.put(doc)
                                    moved += 1
                        j = prices.col[BENCHMARK]
                        done["as_of"] = prices.days[end]
                        done["benchmark"] = [[prices.days[i], float(prices.close[i, j])] for i in range(max(0, end - YEAR), end + 1)]
            except MarketUnavailable:
                pass
            done.pop("running_utc", None)
            self.store.put_meta(done)
            self._cached = None
            return {"moved": moved}
        finally:
            self._refreshing.release()

    # --- Reading ---

    def _stand_ins(self) -> tuple[list[dict], list[float]]:
        """Bots of the kit run on sample figures, started on different days, so the board has its shape."""
        universe = self.largest(BOT_UNIVERSE_MAX)
        prices = Prices(self.closes(set(universe) | {BENCHMARK}))
        end = last_settled(prices.days, self.now()) or len(prices.days) - 1
        out = []
        for n, (raw, back) in enumerate(zip(examples(), [300, 140, 60, 15, 3, 200])):
            try:
                bot = check(raw)
                mine = resolve(bot, lambda k: universe[:k])
            except Refused:
                continue
            curve, held, _ = run(bot, mine, prices, end - back, end)
            out.append({"user_id": "", "stand_in": True, "handle": SAMPLE_NAMES[n % len(SAMPLE_NAMES)], "spec": bot, "universe": mine,
                        "curve": [[d, v] for d, v in curve], "weights": held, "as_of": prices.days[end]})
        j = prices.col[BENCHMARK]
        return out, [float(x) for x in prices.close[max(0, end - YEAR): end + 1, j]]

    def _state(self) -> dict:
        hit = self._cached
        if hit and time.monotonic() - hit[0] < BOTS_CACHE_SECONDS:
            return hit[1]
        with self._lock:
            docs, meta = self.store.all(), self.store.meta()
            bench = [c for _, c in meta.get("benchmark") or []]
            if self.sample:
                try:
                    extra, bench = self._stand_ins()
                    docs = docs + extra
                except MarketUnavailable:
                    pass
            rows = []
            for d in docs:
                values = [v for _, v in d.get("curve") or []]
                held = sorted((d.get("weights") or {}).items(), key=lambda x: -x[1])
                rows.append({"user_id": d["user_id"], "id": d.get("public_id"), "handle": d["handle"], "stand_in": bool(d.get("stand_in")), "name": d["spec"]["name"],
                             "about": d["spec"]["about"], "since": d["curve"][0][0] if d.get("curve") else None, "as_of": d.get("as_of"),
                             "sessions": len(values), "returns": returns(values) if values else {k: None for k in [*(p[0] for p in PERIODS), "all"]},
                             "holdings": [{"ticker": t, "weight": w} for t, w in held[:SHOWN_HOLDINGS]], "holding": len(held),
                             "cash": max(0.0, 1 - sum(w for _, w in held)) if values else None, "submitted_utc": d.get("submitted_utc"),
                             "paused": bool(d.get("paused")), "changed": ((d.get("versions") or [{}])[-1]).get("from")})
            for key in [p[0] for p in PERIODS] + ["all"]:
                ranked = sorted((r for r in rows if r["returns"][key] is not None), key=lambda r: (-r["returns"][key], r["handle"].lower(), r["id"] or ""))
                for n, r in enumerate(ranked, 1):
                    r.setdefault("ranks", {})[key] = n
            for r in rows:
                r.setdefault("ranks", {})
            rows.sort(key=lambda r: (r["returns"]["all"] is None, -(r["returns"]["all"] or 0), r["handle"].lower(), r["id"] or ""))
            as_of = max((r["as_of"] for r in rows if r["as_of"]), default=meta.get("as_of"))
            # The index over the same periods. It has no "since the start": each bot has its own.
            marks = {**returns([c / bench[0] for c in bench]), "all": None} if bench else None
            state = {"rows": rows, "as_of": as_of, "benchmark": {"ticker": BENCHMARK, "returns": marks}}
            self._cached = (time.monotonic(), state)
            return state

    @staticmethod
    def _line(r: dict, user_id: str) -> dict:
        """A line of the board as members get it: never the account id."""
        return {k: v for k, v in r.items() if k not in ("user_id", "submitted_utc")} | {"you": bool(r["user_id"]) and r["user_id"] == user_id}

    def mine(self, user_id: str) -> dict | None:
        """The member's own bot, with its rules: for its owner alone."""
        doc = self.store.get(user_id)
        if not doc:
            return None
        values = [v for _, v in doc.get("curve") or []]
        row = next((r for r in self._state()["rows"] if r["user_id"] == user_id and r.get("submitted_utc") == doc["submitted_utc"]), None)
        held = sorted((doc.get("weights") or {}).items(), key=lambda x: -x[1])
        return {"handle": doc["handle"], "id": doc.get("public_id"), "name": doc["spec"]["name"], "about": doc["spec"]["about"], "submitted_utc": doc["submitted_utc"],
                "since": doc["curve"][0][0] if doc.get("curve") else None, "as_of": doc.get("as_of"), "sessions": len(values),
                "returns": returns(values) if values else None, "ranks": (row or {}).get("ranks", {}), "entrants": len(self._state()["rows"]),
                "holdings": [{"ticker": t, "weight": w} for t, w in held], "cash": max(0.0, 1 - sum(w for _, w in held)) if values else None,
                "rules": describe(doc["spec"], doc["universe"]), "bot": doc["spec"], "universe": len(doc["universe"]),
                "curve": [{"date": d, "value": v} for d, v in doc.get("curve") or []],
                "paused": bool(doc.get("paused")), "exclude": doc["spec"]["universe"]["exclude"], "preview": doc.get("preview"),
                "rules_changed_utc": doc.get("rules_changed_utc"), "log": activity(doc.get("log") or [], 60),
                "versions": [{k: v.get(k) for k in ("from", "changed_utc", "what")} for v in doc.get("versions") or []],
                "pending": self._pending(doc)}

    def _pending(self, doc: dict) -> dict | None:
        """A change waiting for the next close, for its owner."""
        p = doc.get("pending")
        if not p:
            return None
        state = {**doc, **p}
        return {"changed_utc": p["changed_utc"], "what": changes(doc, p), "paused": bool(state.get("paused")),
                "rules": describe(state["spec"], state["universe"]), "bot": state["spec"], "exclude": state["spec"]["universe"]["exclude"]}

    def overview(self, user_id: str) -> dict:
        state = self._state()
        return {"sample": self.sample, "as_of": state["as_of"], "stale": self.behind(), "periods": [{"key": k, "label": label} for k, label, _ in PERIODS],
                "rows": [self._line(r, user_id) for r in state["rows"][:SHOWN]], "entrants": len(state["rows"]), "benchmark": state["benchmark"],
                "you": self.mine(user_id), "key": self.key_status(user_id), "name": (self.store.get(user_id) or {}).get("handle") or "",
                "rules": {"cost": BOT_COST, "universe": BOT_UNIVERSE_MAX, "hold": BOT_HOLD_MAX}}

    # --- What is kept of a member ---

    def kept(self, user_id: str) -> dict:
        doc = self.store.get(user_id)
        """Everything kept of a member's bot, for their account page and their download."""
        keep = ("handle", "public_id", "submitted_utc", "spec", "universe", "curve", "weights", "as_of", "log", "versions", "pending", "paused",
                "rules_changed_utc", "preview")
        return {"bot": {"name": doc["spec"]["name"], **{k: doc.get(k) for k in keep}} if doc else None, "key": self.key_status(user_id)}

    def forget(self, user_id: str) -> None:
        self.store.delete(user_id)
        self.revoke_key(user_id)
        self._cached = None
