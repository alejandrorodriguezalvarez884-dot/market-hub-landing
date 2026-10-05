"""Sample data for the public portal: market overview, charts, quotes and news.

A placeholder until a real provider is wired in. Every answer carries ``"sample": True`` and the
site labels it as sample data. The numbers are generated, not observed: a random walk per
symbol from a fixed seed, so a symbol's history stays the same from one day to the next and
grows by one bar each trading day, scaled so the last close sits at a plausible level.

Descriptive only, like the rest of the portal: prices, moves and headlines. No ratings, no fair
values, nothing that says what to buy or sell.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

START = date(2019, 1, 2)
RANGES = ("1D", "5D", "1M", "6M", "YTD", "1Y", "5Y")


@dataclass(frozen=True)
class Spec:
    symbol: str
    name: str
    kind: str  # index, stock, etf, rate, commodity, fx, crypto
    level: float  # where the last close sits
    vol: float  # daily volatility
    volume: int = 0  # average daily volume, shares
    sector: str = ""
    shares: float = 0.0  # shares outstanding, for the market cap
    eps: float = 0.0
    dividend_yield: float = 0.0
    exchange: str = ""


INSTRUMENTS = [
    Spec("SPX", "S&P 500", "index", 5850, 0.010),
    Spec("NDX", "Nasdaq 100", "index", 20750, 0.013),
    Spec("DJI", "Dow Jones Industrial Average", "index", 42600, 0.009),
    Spec("RUT", "Russell 2000", "index", 2240, 0.014),
    Spec("VIX", "CBOE Volatility Index", "index", 17.2, 0.055),
    Spec("SX5E", "Euro Stoxx 50", "index", 4960, 0.011),
    Spec("UKX", "FTSE 100", "index", 8280, 0.009),
    Spec("N225", "Nikkei 225", "index", 38900, 0.013),
    Spec("US10Y", "US 10-year yield", "rate", 4.12, 0.018),
    Spec("US2Y", "US 2-year yield", "rate", 3.86, 0.02),
    Spec("DE10Y", "Germany 10-year yield", "rate", 2.27, 0.02),
    Spec("GOLD", "Gold", "commodity", 2655, 0.009),
    Spec("SILVER", "Silver", "commodity", 31.4, 0.018),
    Spec("WTI", "Crude oil (WTI)", "commodity", 71.6, 0.021),
    Spec("NATGAS", "Natural gas", "commodity", 2.84, 0.035),
    Spec("COPPER", "Copper", "commodity", 4.31, 0.014),
    Spec("EURUSD", "EUR/USD", "fx", 1.0915, 0.004),
    Spec("GBPUSD", "GBP/USD", "fx", 1.3080, 0.0045),
    Spec("USDJPY", "USD/JPY", "fx", 148.6, 0.005),
    Spec("DXY", "US Dollar Index", "fx", 102.4, 0.004),
    Spec("BTCUSD", "Bitcoin", "crypto", 64200, 0.03),
    Spec("ETHUSD", "Ether", "crypto", 2510, 0.035),
]

# Large US companies and funds: movers, quotes and the news tickers. Fundamentals are rough
# placeholders, only there so the quote page has its shape.
STOCKS = [
    Spec("AAPL", "Apple Inc.", "stock", 226.8, 0.015, 52_000_000, "Technology", 15.2e9, 6.6, 0.0044, "NASDAQ"),
    Spec("MSFT", "Microsoft Corp.", "stock", 417.5, 0.014, 20_000_000, "Technology", 7.43e9, 12.1, 0.0075, "NASDAQ"),
    Spec("NVDA", "NVIDIA Corp.", "stock", 124.9, 0.03, 250_000_000, "Technology", 24.5e9, 2.5, 0.0003, "NASDAQ"),
    Spec("AMZN", "Amazon.com Inc.", "stock", 186.4, 0.019, 40_000_000, "Consumer Cyclical", 10.5e9, 4.2, 0.0, "NASDAQ"),
    Spec("GOOGL", "Alphabet Inc.", "stock", 164.2, 0.017, 25_000_000, "Communication Services", 12.3e9, 7.5, 0.0049, "NASDAQ"),
    Spec("META", "Meta Platforms Inc.", "stock", 573.1, 0.021, 12_000_000, "Communication Services", 2.53e9, 21.2, 0.0035, "NASDAQ"),
    Spec("TSLA", "Tesla Inc.", "stock", 249.3, 0.033, 85_000_000, "Consumer Cyclical", 3.2e9, 3.6, 0.0, "NASDAQ"),
    Spec("BRK-B", "Berkshire Hathaway Inc.", "stock", 456.0, 0.009, 3_500_000, "Financial Services", 2.15e9, 30.5, 0.0, "NYSE"),
    Spec("JPM", "JPMorgan Chase & Co.", "stock", 211.2, 0.013, 9_000_000, "Financial Services", 2.85e9, 17.4, 0.0237, "NYSE"),
    Spec("V", "Visa Inc.", "stock", 278.6, 0.011, 6_500_000, "Financial Services", 1.95e9, 9.7, 0.0075, "NYSE"),
    Spec("UNH", "UnitedHealth Group Inc.", "stock", 584.3, 0.014, 3_200_000, "Healthcare", 0.92e9, 16.3, 0.0144, "NYSE"),
    Spec("LLY", "Eli Lilly and Co.", "stock", 905.4, 0.019, 3_000_000, "Healthcare", 0.95e9, 11.0, 0.0057, "NYSE"),
    Spec("JNJ", "Johnson & Johnson", "stock", 162.1, 0.009, 7_000_000, "Healthcare", 2.41e9, 6.1, 0.0306, "NYSE"),
    Spec("XOM", "Exxon Mobil Corp.", "stock", 118.4, 0.014, 15_000_000, "Energy", 4.4e9, 8.6, 0.0321, "NYSE"),
    Spec("CVX", "Chevron Corp.", "stock", 148.9, 0.014, 7_500_000, "Energy", 1.8e9, 10.1, 0.0438, "NYSE"),
    Spec("PG", "Procter & Gamble Co.", "stock", 173.2, 0.008, 6_000_000, "Consumer Defensive", 2.36e9, 6.5, 0.0232, "NYSE"),
    Spec("KO", "Coca-Cola Co.", "stock", 71.3, 0.008, 12_000_000, "Consumer Defensive", 4.31e9, 2.5, 0.0272, "NYSE"),
    Spec("WMT", "Walmart Inc.", "stock", 80.8, 0.01, 14_000_000, "Consumer Defensive", 8.04e9, 2.3, 0.0103, "NYSE"),
    Spec("HD", "Home Depot Inc.", "stock", 405.2, 0.012, 3_300_000, "Consumer Cyclical", 0.99e9, 15.0, 0.0222, "NYSE"),
    Spec("CAT", "Caterpillar Inc.", "stock", 391.5, 0.016, 2_400_000, "Industrials", 0.48e9, 21.9, 0.0144, "NYSE"),
    Spec("BA", "Boeing Co.", "stock", 152.6, 0.022, 7_000_000, "Industrials", 0.62e9, -12.2, 0.0, "NYSE"),
    Spec("AMD", "Advanced Micro Devices Inc.", "stock", 164.1, 0.029, 45_000_000, "Technology", 1.62e9, 1.3, 0.0, "NASDAQ"),
    Spec("NFLX", "Netflix Inc.", "stock", 709.3, 0.021, 3_200_000, "Communication Services", 0.43e9, 17.7, 0.0, "NASDAQ"),
    Spec("COST", "Costco Wholesale Corp.", "stock", 888.6, 0.011, 1_900_000, "Consumer Defensive", 0.44e9, 16.6, 0.0052, "NASDAQ"),
    Spec("NEE", "NextEra Energy Inc.", "stock", 84.1, 0.013, 9_000_000, "Utilities", 2.05e9, 3.4, 0.0245, "NYSE"),
    Spec("PLD", "Prologis Inc.", "stock", 125.7, 0.015, 3_500_000, "Real Estate", 0.93e9, 3.4, 0.0305, "NYSE"),
    Spec("LIN", "Linde plc", "stock", 474.0, 0.01, 1_900_000, "Basic Materials", 0.48e9, 13.6, 0.0118, "NASDAQ"),
    Spec("SPY", "SPDR S&P 500 ETF Trust", "etf", 584.6, 0.01, 45_000_000, "ETF / fund", 0.91e9, 0.0, 0.0121, "NYSE Arca"),
    Spec("QQQ", "Invesco QQQ Trust", "etf", 504.1, 0.013, 35_000_000, "ETF / fund", 0.59e9, 0.0, 0.0057, "NASDAQ"),
]

SECTORS = ["Technology", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Financial Services",
           "Healthcare", "Industrials", "Energy", "Utilities", "Real Estate", "Basic Materials"]

_BY_SYMBOL = {s.symbol: s for s in INSTRUMENTS + STOCKS}


def _seed(*parts: object) -> int:
    return int.from_bytes(hashlib.sha256(":".join(map(str, parts)).encode()).digest()[:8], "big")


def spec(symbol: str, name: str | None = None) -> Spec:
    """The known instrument, or a made-up stock for any other ticker (stable per ticker)."""
    symbol = symbol.upper()
    if symbol in _BY_SYMBOL:
        return _BY_SYMBOL[symbol]
    r = random.Random(_seed("spec", symbol))
    level = round(r.uniform(12, 380), 2)
    shares = r.uniform(0.05e9, 2.5e9)
    return Spec(symbol, name or symbol, "stock", level, r.uniform(0.012, 0.03), int(r.uniform(0.5e6, 20e6)),
                r.choice(SECTORS), shares, round(level / r.uniform(12, 40), 2), round(r.choice([0, 0, 0.008, 0.015, 0.024]), 4))


def trading_day(today: date | None = None) -> date:
    d = today or datetime.now(timezone.utc).date()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _digits(s: Spec) -> int:
    return 4 if s.kind == "fx" and s.level < 10 else 3 if s.kind == "rate" else 2


@lru_cache(maxsize=512)
def _daily(symbol: str, name: str, last_day: date) -> tuple[tuple, ...]:
    """(date, open, high, low, close, volume) per trading day from START to ``last_day``."""
    s = spec(symbol, name)
    r = random.Random(_seed("daily", s.symbol))
    rows, level, d = [], 100.0, START
    while d <= last_day:
        if d.weekday() < 5:
            ret = r.gauss(0.0004, s.vol)
            o = level * (1 + r.gauss(0, s.vol / 4))
            c = level * (1 + ret)
            hi = max(o, c) * (1 + abs(r.gauss(0, s.vol / 2)))
            lo = min(o, c) * (1 - abs(r.gauss(0, s.vol / 2)))
            vol = int(s.volume * (0.55 + r.random() * 0.9)) if s.volume else 0
            rows.append((d, o, hi, lo, c, vol))
            level = c
        d += timedelta(days=1)
    k = s.level / rows[-1][4]
    nd = _digits(s)
    return tuple((d, round(o * k, nd), round(h * k, nd), round(lo * k, nd), round(c * k, nd), v) for d, o, h, lo, c, v in rows)


def daily(symbol: str, name: str | None = None, today: date | None = None) -> tuple[tuple, ...]:
    s = spec(symbol, name)
    return _daily(s.symbol, s.name, trading_day(today))


def _ret(rows: tuple[tuple, ...], back: int) -> float | None:
    return rows[-1][4] / rows[-1 - back][4] - 1 if len(rows) > back and rows[-1 - back][4] else None


def _ytd(rows: tuple[tuple, ...]) -> float | None:
    year = rows[-1][0].year
    before = [r for r in rows if r[0].year < year]
    return rows[-1][4] / before[-1][4] - 1 if before else None


def snapshot(symbol: str, name: str | None = None, today: date | None = None, spark: int = 30) -> dict:
    s = spec(symbol, name)
    rows = daily(s.symbol, s.name, today)
    last, prev = rows[-1], rows[-2]
    nd = _digits(s)
    return {
        "symbol": s.symbol, "name": s.name, "kind": s.kind,
        "price": last[4], "change": round(last[4] - prev[4], nd), "change_pct": last[4] / prev[4] - 1,
        "return_1m": _ret(rows, 21), "return_ytd": _ytd(rows), "return_1y": _ret(rows, 252),
        "spark": [r[4] for r in rows[-spark:]],
    }


def _bridge(r: random.Random, start: float, end: float, n: int, vol: float) -> list[float]:
    """A random path of ``n`` points from ``start`` to ``end``."""
    walk = [0.0]
    for _ in range(n - 1):
        walk.append(walk[-1] + r.gauss(0, vol))
    return [start + (end - start) * i / (n - 1) + (walk[i] - walk[-1] * i / (n - 1)) * start for i in range(n)]


def _intraday(s: Spec, row: tuple, prev_close: float, minutes: int) -> list[dict]:
    d, _o, _h, _l, c, vol = row
    n = 390 // minutes
    r = random.Random(_seed("intraday", s.symbol, d, minutes))
    path = _bridge(r, prev_close, c, n + 1, s.vol / (n ** 0.5) * 1.2)
    nd = _digits(s)
    out = []
    t0 = datetime(d.year, d.month, d.day, 9, 30, tzinfo=timezone.utc)
    for i in range(n):
        o, cl = path[i], path[i + 1]
        wig = abs(r.gauss(0, s.vol / (n ** 0.5) / 2))
        out.append({"time": int((t0 + timedelta(minutes=minutes * i)).timestamp()),
                    "open": round(o, nd), "high": round(max(o, cl) * (1 + wig), nd), "low": round(min(o, cl) * (1 - wig), nd),
                    "close": round(cl, nd), "volume": int(vol / n * (0.5 + r.random()))})
    return out


def _bar(row: tuple) -> dict:
    d, o, h, lo, c, v = row
    return {"time": d.isoformat(), "open": o, "high": h, "low": lo, "close": c, "volume": v}


def chart(symbol: str, rng: str = "1Y", name: str | None = None, today: date | None = None) -> dict:
    s = spec(symbol, name)
    rows = daily(s.symbol, s.name, today)
    rng = rng.upper() if rng.upper() in RANGES else "1Y"
    if rng == "1D":
        bars, interval = _intraday(s, rows[-1], rows[-2][4], 5), "5m"
    elif rng == "5D":
        bars = [b for i in range(-5, 0) for b in _intraday(s, rows[i], rows[i - 1][4], 30)]
        interval = "30m"
    elif rng == "5Y":
        weeks: dict[tuple, list] = {}
        for row in rows[-1260:]:
            weeks.setdefault(row[0].isocalendar()[:2], []).append(row)
        bars = [{"time": w[0][0].isoformat(), "open": w[0][1], "high": max(x[2] for x in w), "low": min(x[3] for x in w),
                 "close": w[-1][4], "volume": sum(x[5] for x in w)} for w in weeks.values()]
        interval = "1W"
    else:
        if rng == "YTD":
            part = [r for r in rows if r[0].year == rows[-1][0].year]
        else:
            part = rows[-{"1M": 22, "6M": 126, "1Y": 252}[rng]:]
        bars, interval = [_bar(r) for r in part], "1D"
    return {"sample": True, "symbol": s.symbol, "name": s.name, "kind": s.kind, "range": rng, "interval": interval,
            "prev_close": rows[-2][4], "bars": bars}


def overview(today: date | None = None) -> dict:
    snap = {i.symbol: snapshot(i.symbol, today=today) for i in INSTRUMENTS}
    group = lambda kind: [snap[i.symbol] for i in INSTRUMENTS if i.kind == kind]  # noqa: E731
    stocks = [snapshot(s.symbol, today=today) | {"volume": daily(s.symbol, today=today)[-1][5], "sector": s.sector}
              for s in STOCKS if s.kind == "stock"]
    by_change = sorted(stocks, key=lambda x: x["change_pct"])
    sectors = []
    for sector in SECTORS:
        members = [x for x in stocks if x["sector"] == sector]
        r = random.Random(_seed("sector", sector, trading_day(today)))
        base = sum(x["change_pct"] for x in members) / len(members) if members else r.gauss(0, 0.008)
        sectors.append({"name": sector, "change_pct": base * 0.6 + r.gauss(0, 0.004),
                        "return_ytd": r.gauss(0.09, 0.08), "members": [x["symbol"] for x in members]})
    tape = ["SPX", "NDX", "DJI", "RUT", "VIX", "US10Y", "GOLD", "WTI", "EURUSD", "BTCUSD"]
    return {
        "sample": True,
        "as_of": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "intraday": True,
        "tape": [snap[t] for t in tape],
        "indices": group("index"),
        "rates": group("rate"),
        "commodities": group("commodity"),
        "currencies": group("fx"),
        "crypto": group("crypto"),
        "sectors": sectors,
        "movers": {
            "gainers": list(reversed(by_change[-6:])),
            "losers": by_change[:6],
            "active": sorted(stocks, key=lambda x: x["volume"], reverse=True)[:6],
        },
    }


def quote(ticker: str, name: str | None = None, today: date | None = None) -> dict:
    s = spec(ticker, name)
    rows = daily(s.symbol, s.name, today)
    last, prev = rows[-1], rows[-2]
    year = rows[-252:]
    r = random.Random(_seed("quote", s.symbol))
    snap = snapshot(s.symbol, s.name, today)
    return snap | {
        "sample": True,
        "exchange": s.exchange or "NYSE",
        "sector": s.sector or "—",
        "prev_close": prev[4], "open": last[1], "day_low": last[3], "day_high": last[2],
        "year_low": min(x[3] for x in year), "year_high": max(x[2] for x in year),
        "volume": last[5], "avg_volume": int(sum(x[5] for x in rows[-63:]) / 63),
        "market_cap": last[4] * s.shares if s.shares else None,
        "pe": round(last[4] / s.eps, 1) if s.eps > 0 else None,
        "eps": s.eps or None,
        "dividend_yield": s.dividend_yield or None,
        "beta": round(r.uniform(0.6, 1.6), 2) if s.kind == "stock" else None,
        "return_6m": _ret(rows, 126), "return_5y": _ret(rows, 1260),
        "news": news(ticker=s.symbol, limit=4, name=s.name)["items"],
    }


# --- News -------------------------------------------------------------------------------------

CATEGORIES = ["Markets", "Economy", "Companies", "Earnings", "Technology", "Commodities"]

# Generic headlines in the voice of a markets desk. Placeholder content, not reporting: the
# sources are made up and the site says so. (category, title, summary, tickers, minutes ago)
HEADLINES = [
    ("Markets", "Stocks drift as investors look ahead to central bank minutes",
     "Major US indexes moved in a narrow range through the session, with trading volumes below their monthly average.",
     ["SPX", "NDX"], 14),
    ("Economy", "Treasury yields edge higher before the monthly jobs report",
     "The 10-year yield rose a few basis points as bond traders adjusted positions ahead of the labour market data.",
     ["US10Y", "US2Y"], 38),
    ("Technology", "Chipmakers swing between gains and losses in a choppy session",
     "Semiconductor shares were the most traded group of the day, with moves in both directions across the sector.",
     ["NVDA", "AMD"], 55),
    ("Commodities", "Oil prices move with inventory data and supply headlines",
     "Crude futures reacted to the weekly stock figures, while natural gas traded in a wide intraday range.",
     ["WTI", "NATGAS", "XOM", "CVX"], 72),
    ("Earnings", "Earnings season calendar: the large companies reporting this week",
     "A look at which of the largest US companies publish quarterly results over the coming days, and when.",
     ["JPM", "UNH", "NFLX"], 96),
    ("Companies", "What the latest annual filings say about Big Tech capital spending",
     "Data centres and chips dominate the investment lines of the largest technology groups' latest reports.",
     ["MSFT", "GOOGL", "META", "AMZN"], 130),
    ("Markets", "European shares close mixed as the euro holds steady",
     "Regional benchmarks ended the day without a clear direction; currency markets were quiet.",
     ["SX5E", "UKX", "EURUSD"], 165),
    ("Economy", "Inflation data in focus: what the components show",
     "Shelter and services prices remain the largest contributors to the annual rate, according to the latest release.",
     ["US10Y"], 210),
    ("Commodities", "Gold trades near its recent range as the dollar firms",
     "Precious metals moved with the dollar index, with silver more volatile than gold through the session.",
     ["GOLD", "SILVER", "DXY"], 260),
    ("Technology", "Software companies' cloud revenue growth, compared",
     "A side-by-side of the latest reported growth rates for the cloud businesses of the largest software groups.",
     ["MSFT", "AMZN", "GOOGL"], 320),
    ("Companies", "Retailers' latest results: inventories, margins and traffic",
     "Large retailers described consumer demand in their latest reports; here are the figures they published.",
     ["WMT", "COST", "HD"], 390),
    ("Markets", "Small caps and large caps: how the gap has moved this year",
     "The Russell 2000 and the S&P 500 have followed different paths since January; a look at the numbers.",
     ["RUT", "SPX"], 470),
    ("Earnings", "How to read a results release: guidance, margins and one-offs",
     "A short guide to the parts of a quarterly release that move the most, and the vocabulary companies use.",
     [], 560),
    ("Economy", "Asian markets: Tokyo moves with the yen",
     "The Nikkei 225 traded in step with the dollar-yen exchange rate during the Asian session.",
     ["N225", "USDJPY"], 640),
    ("Markets", "Volatility index stays near its long-run average",
     "The VIX moved little during the day, as options activity was concentrated in short-dated contracts.",
     ["VIX", "SPX"], 720),
    ("Technology", "Electric vehicle makers: deliveries and price changes",
     "Recent delivery figures and list price changes across the electric vehicle makers listed in the US.",
     ["TSLA"], 830),
    ("Companies", "Pharmaceutical groups and the weight-loss drug market",
     "Production capacity and prescriptions figures from the companies' latest communications.",
     ["LLY", "JNJ"], 960),
    ("Commodities", "Copper and industrial metals track the global manufacturing surveys",
     "Base metals moved with the latest purchasing managers' indexes from the largest economies.",
     ["COPPER", "CAT"], 1090),
    ("Markets", "Crypto assets trade in a wide range over the weekend",
     "Bitcoin and ether moved several percent in both directions in thin weekend trading.",
     ["BTCUSD", "ETHUSD"], 1250),
    ("Earnings", "Banks' net interest income: what the last quarter showed",
     "Large US banks reported their lending margins; a comparison of the figures from their releases.",
     ["JPM", "BRK-B", "V"], 1420),
]


def _company_headlines(ticker: str, name: str) -> list[tuple]:
    return [
        ("Companies", f"{name}: what its latest annual report shows",
         f"Revenue, margins and cash flow from {name}'s most recent annual filing, in brief.", [ticker], 180),
        ("Earnings", f"{name}'s last quarter in numbers",
         f"The main figures from {name}'s latest quarterly results release, against the same quarter a year earlier.",
         [ticker], 1500),
        ("Markets", f"How {ticker} has moved against the S&P 500 this year",
         f"{name}'s shares compared with the broad market since January.", [ticker, "SPX"], 2900),
    ]


def news(category: str | None = None, ticker: str | None = None, limit: int = 20, name: str | None = None,
         now: datetime | None = None) -> dict:
    now = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    items = list(HEADLINES)
    if ticker:
        ticker = ticker.upper()
        own = [h for h in items if ticker in h[3]]
        items = own + (_company_headlines(ticker, name or spec(ticker).name) if len(own) < 3 else [])
    if category and category in CATEGORIES:
        items = [h for h in items if h[0] == category]
    sources = ["Sample Markets Desk", "Sample Wire", "Sample Economics Desk"]
    out = []
    for i, (cat, title, summary, tickers, ago) in enumerate(sorted(items, key=lambda h: h[4])[:limit]):
        out.append({
            "id": hashlib.sha1(title.encode()).hexdigest()[:10],
            "category": cat, "title": title, "summary": summary, "tickers": tickers,
            "source": sources[i % len(sources)],
            "published_utc": (now - timedelta(minutes=ago)).isoformat(),
        })
    return {"sample": True, "categories": CATEGORIES, "items": out}
