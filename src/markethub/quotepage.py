"""What the quote page shows beyond the price: a symbol's past set against the S&P 500, and the
facts Yahoo keeps about a company or a fund, in the shapes the page reads.

Everything here is arithmetic on prices and a reshaping of what the provider says. Nothing
estimates, ranks or recommends.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

BENCHMARK = "SPY"  # the S&P 500, as a fund that trades: its closes sit on the same days as a stock's
SESSIONS_A_YEAR = 252
# A holding's symbol the quote page can open: a US ticker, with its share class if it has one.
US_TICKER = re.compile(r"^[A-Z]{1,5}([.-][A-Z])?$")

SECTOR_NAMES = {
    "technology": "Technology", "healthcare": "Healthcare", "financial_services": "Financial Services",
    "consumer_cyclical": "Consumer Cyclical", "consumer_defensive": "Consumer Defensive", "industrials": "Industrials",
    "communication_services": "Communication Services", "energy": "Energy", "utilities": "Utilities",
    "realestate": "Real Estate", "basic_materials": "Basic Materials",
}
ASSET_NAMES = {"stockPosition": "Stocks", "bondPosition": "Bonds", "cashPosition": "Cash", "preferredPosition": "Preferred",
               "convertiblePosition": "Convertible", "otherPosition": "Other"}
# Rows of an income statement, by the names yfinance gives them.
STATEMENT_ROWS = {"revenue": "Total Revenue", "gross_profit": "Gross Profit", "operating_income": "Operating Income",
                  "net_income": "Net Income", "eps": "Diluted EPS"}


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _day(stamp: Any) -> str | None:
    """A moment Yahoo gives in seconds, as a date."""
    s = _num(stamp)
    return datetime.fromtimestamp(s, timezone.utc).date().isoformat() if s else None


# --- the past -----------------------------------------------------------------------------------


def _aligned(dates: list[str], bench: list[dict]) -> list[float | None]:
    """The benchmark's close on each of ``dates``: the last one at or before it."""
    out, i, last = [], 0, None
    for d in dates:
        while i < len(bench) and bench[i]["time"] <= d:
            last = bench[i]["close"]
            i += 1
        out.append(last)
    return out


def _years(dates: list[str], closes: list[float]) -> list[dict]:
    """Each calendar year's price return: from the last close of the year before (or the first
    close there is, for the first year) to the year's last close, with the positions of those two
    closes. A year the data does not cover whole says so."""
    out, start = [], 0
    for i, d in enumerate(dates):
        if i + 1 < len(dates) and dates[i + 1][:4] == d[:4]:
            continue
        out.append({"year": int(d[:4]), "return": closes[i] / closes[start] - 1 if closes[start] else None, "at": (start, i)})
        start = i
    for k, y in enumerate(out):
        y["partial"] = (k == 0 and dates[0][5:] > "01-07") or (k == len(out) - 1 and dates[-1][5:] < "12-24")
    return out


def _daily_returns(closes: list[float | None]) -> list[float | None]:
    return [b / a - 1 if a and b else None for a, b in zip(closes, closes[1:])]


def _vol(rets: list[float]) -> float | None:
    if len(rets) < 20:
        return None
    mean = sum(rets) / len(rets)
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) * math.sqrt(SESSIONS_A_YEAR)


def _drawdown(dates: list[str], closes: list[float]) -> dict | None:
    """The deepest fall from a high to a later low, with its two days."""
    peak, peak_day, worst = closes[0], dates[0], None
    for d, c in zip(dates, closes):
        if c > peak:
            peak, peak_day = c, d
        fall = c / peak - 1
        if worst is None or fall < worst["depth"]:
            worst = {"depth": fall, "peak": peak_day, "trough": d}
    return worst


def history(bars: list[dict], bench: list[dict] | None) -> dict | None:
    """A symbol's daily closes (up to five years) with the benchmark's on the same days, each
    calendar year's return for both, and how much the price moved: volatility, deepest fall,
    best and worst day of the last year, and beta to the benchmark over that year."""
    bars = [b for b in bars if _num(b.get("close"))]
    if len(bars) < 2:
        return None
    dates, closes = [b["time"][:10] for b in bars], [float(b["close"]) for b in bars]
    marks = _aligned(dates, bench) if bench else [None] * len(dates)
    rets = _daily_returns(closes)
    year_rets = [r for r in rets[-SESSIONS_A_YEAR:] if r is not None]
    year_days = dates[1:][-SESSIONS_A_YEAR:]
    best = max(range(len(year_rets)), key=lambda i: year_rets[i]) if year_rets else None
    worst = min(range(len(year_rets)), key=lambda i: year_rets[i]) if year_rets else None

    # Beta and the benchmark's own figures, on the days both have a close.
    b_rets = _daily_returns(marks)[-SESSIONS_A_YEAR:]
    pairs = [(r, b) for r, b in zip(rets[-SESSIONS_A_YEAR:], b_rets) if r is not None and b is not None]
    beta = None
    if len(pairs) >= 60:
        mr, mb = (sum(p[i] for p in pairs) / len(pairs) for i in (0, 1))
        var = sum((b - mb) ** 2 for _, b in pairs)
        beta = sum((r - mr) * (b - mb) for r, b in pairs) / var if var else None
    years = _years(dates, closes)
    for y in years:
        i, j = y.pop("at")
        y["benchmark"] = marks[j] / marks[i] - 1 if marks[i] and marks[j] else None
    first_mark = next((i for i, m in enumerate(marks) if m), None)
    risk = {
        "volatility_1y": _vol(year_rets),
        "benchmark_volatility_1y": _vol([b for _, b in pairs]) if pairs else None,
        "max_drawdown": _drawdown(dates, closes),
        "benchmark_max_drawdown": _drawdown(dates[first_mark:], [m or 0.0 for m in marks[first_mark:]]) if first_mark is not None else None,
        "best_day": {"date": year_days[best], "return": year_rets[best]} if best is not None else None,
        "worst_day": {"date": year_days[worst], "return": year_rets[worst]} if worst is not None else None,
        "beta_1y": beta,
        "up_days_1y": sum(r > 0 for r in year_rets) / len(year_rets) if year_rets else None,
    }
    return {"benchmark": BENCHMARK if bench else None, "dates": dates, "closes": [round(c, 4) for c in closes],
            "benchmark_closes": [round(m, 4) if m else None for m in marks] if bench else None, "years": years, "risk": risk}


# --- the facts ----------------------------------------------------------------------------------


def statements(frame) -> list[dict]:
    """An income statement from yfinance (a row per item, a column per period, newest first) as
    periods oldest first, each with its end and the few figures the page charts."""
    if frame is None or getattr(frame, "empty", True):
        return []
    rows = set(frame.index)
    out = []
    for column in frame.columns:
        period = {"end": column.date().isoformat() if hasattr(column, "date") else str(column)[:10]}
        for name, row in STATEMENT_ROWS.items():
            period[name] = _num(frame.at[row, column]) if row in rows else None
        if period["revenue"] is not None or period["net_income"] is not None:
            out.append(period)
    return sorted(out, key=lambda p: p["end"])


def company(info: dict) -> dict:
    """What Yahoo says of a company: its business, how it is valued, how much of its sales it keeps,
    its balance sheet, who holds it and what it pays."""
    g = lambda k: _num(info.get(k))  # noqa: E731
    return {
        "summary": info.get("longBusinessSummary") or "",
        "sector": info.get("sector") or "", "industry": info.get("industry") or "",
        "employees": g("fullTimeEmployees"), "website": info.get("website") or "",
        "city": info.get("city") or "", "state": info.get("state") or "", "country": info.get("country") or "",
        "valuation": {"pe": g("trailingPE"), "forward_pe": g("forwardPE"), "ps": g("priceToSalesTrailing12Months"),
                      "pb": g("priceToBook"), "ev_ebitda": g("enterpriseToEbitda"), "ev_revenue": g("enterpriseToRevenue"),
                      "enterprise_value": g("enterpriseValue")},
        "profitability": {"gross_margin": g("grossMargins"), "operating_margin": g("operatingMargins"),
                          "net_margin": g("profitMargins"), "roe": g("returnOnEquity"), "roa": g("returnOnAssets")},
        "growth": {"revenue": g("revenueGrowth"), "earnings": g("earningsQuarterlyGrowth") or g("earningsGrowth")},
        "health": {"revenue": g("totalRevenue"), "ebitda": g("ebitda"), "free_cash_flow": g("freeCashflow"),
                   "cash": g("totalCash"), "debt": g("totalDebt"),
                   # Yahoo gives debt to equity in percent.
                   "debt_to_equity": g("debtToEquity") / 100 if g("debtToEquity") is not None else None,
                   "current_ratio": g("currentRatio")},
        "ownership": {"insiders": g("heldPercentInsiders"), "institutions": g("heldPercentInstitutions"),
                      "short_of_float": g("shortPercentOfFloat"), "shares": g("sharesOutstanding"), "float": g("floatShares")},
        "dividends": {"rate": g("dividendRate"), "payout_ratio": g("payoutRatio"), "ex_date": _day(info.get("exDividendDate")),
                      # Yahoo gives the five-year average in percent.
                      "five_year_avg_yield": g("fiveYearAvgDividendYield") / 100 if g("fiveYearAvgDividendYield") is not None else None},
        "next_results": _day(info.get("earningsTimestampStart")),
    }


def fund(info: dict, data=None) -> dict:
    """What Yahoo says of a fund: what it is, what it costs, how big it is, and what it holds."""
    g = lambda k: _num(info.get(k))  # noqa: E731
    # The net expense ratio comes in percent; the one from the annual report as a fraction.
    expense = g("netExpenseRatio")
    expense = expense / 100 if expense is not None else g("annualReportExpenseRatio")
    overview = dict(getattr(data, "fund_overview", None) or {}) if data is not None else {}
    holdings = []
    top = getattr(data, "top_holdings", None) if data is not None else None
    if top is not None and not getattr(top, "empty", True):
        for sym, row in top.to_dict("index").items():
            weight = _num(row.get("Holding Percent"))
            if weight is None:
                continue
            sym = str(sym).upper()
            holdings.append({"symbol": sym.replace(".", "-") if US_TICKER.match(sym) else None, "label": sym,
                             "name": row.get("Name") or sym, "weight": weight})
    sectors = {}
    if data is not None:
        sectors = dict(getattr(data, "sector_weightings", None) or {})
    mix = dict(getattr(data, "asset_classes", None) or {}) if data is not None else {}
    ytd = g("ytdReturn")
    return {
        "summary": info.get("longBusinessSummary") or "",
        "legal_type": overview.get("legalType") or "", "family": info.get("fundFamily") or overview.get("family") or "",
        "category": info.get("category") or overview.get("categoryName") or "",
        "expense_ratio": expense, "assets": g("totalAssets") or g("netAssets"), "yield": g("yield"),
        "nav": g("navPrice"), "inception": _day(info.get("fundInceptionDate")), "beta_3y": g("beta3Year"),
        # Total returns as the fund reports them, with what it paid out: a year on average.
        "return_3y": g("threeYearAverageReturn"), "return_5y": g("fiveYearAverageReturn"),
        "return_ytd": ytd / 100 if ytd is not None else None,
        "holdings": holdings,
        "holdings_weight": sum(h["weight"] for h in holdings) if holdings else None,
        "sectors": sorted(({"name": SECTOR_NAMES.get(k, k.replace("_", " ").title()), "weight": w}
                           for k, v in sectors.items() if (w := _num(v))), key=lambda s: -s["weight"]),
        "asset_mix": sorted(({"name": ASSET_NAMES.get(k, k), "weight": w} for k, v in mix.items() if (w := _num(v)) and w > 0.0005),
                            key=lambda s: -s["weight"]),
    }

