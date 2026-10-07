"""Live market data for the public portal, from FMP, in the same shapes as sample.py.

Each part stands on its own. When the provider or the data plan does not answer one (intraday
bars, say), that part falls back: the overview serves the last good answer, or sample data
named in ``sample_sections``; a chart range without data answers MarketUnavailable and the site
switches to a daily range. Nothing here is sent anywhere but the provider, and only symbols.

Answers are kept in memory: the overview for PUBLIC_MARKETS_TTL_SECONDS (an hour by
default), so the number of provider calls does not grow with the number of visitors.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

from . import sample
from .market import Fmp, MarketUnavailable, NotInPlan

log = logging.getLogger("markethub.live")

OVERVIEW_TTL = float(os.environ.get("PUBLIC_MARKETS_TTL_SECONDS", "3600"))
DAILY_TTL = 6 * 3600
INTRADAY_TTL = 300
QUOTE_TTL = 300
# Index and commodity quotes are not in every data plan; their daily closes are. Without a
# quote, the price and the day's move come from the last two closes, refreshed this often.
CLOSE_TTL = float(os.environ.get("PUBLIC_CLOSES_TTL_SECONDS", "21600"))
# Movers below this price are left out: the provider's lists fill up with penny stocks.
MOVERS_MIN_PRICE = 5.0

# Display symbol -> (provider symbol, name, kind).
INSTRUMENTS = [
    ("SPX", "^GSPC", "S&P 500", "index"),
    ("NDX", "^NDX", "Nasdaq 100", "index"),
    ("DJI", "^DJI", "Dow Jones Industrial Average", "index"),
    ("RUT", "^RUT", "Russell 2000", "index"),
    ("VIX", "^VIX", "CBOE Volatility Index", "index"),
    ("SX5E", "^STOXX50E", "Euro Stoxx 50", "index"),
    ("UKX", "^FTSE", "FTSE 100", "index"),
    ("N225", "^N225", "Nikkei 225", "index"),
    ("GOLD", "GCUSD", "Gold", "commodity"),
    ("SILVER", "SIUSD", "Silver", "commodity"),
    ("WTI", "CLUSD", "Crude oil (WTI)", "commodity"),
    ("NATGAS", "NGUSD", "Natural gas", "commodity"),
    ("COPPER", "HGUSD", "Copper", "commodity"),
    ("EURUSD", "EURUSD", "EUR/USD", "fx"),
    ("GBPUSD", "GBPUSD", "GBP/USD", "fx"),
    ("USDJPY", "USDJPY", "USD/JPY", "fx"),
    ("BTCUSD", "BTCUSD", "Bitcoin", "crypto"),
    ("ETHUSD", "ETHUSD", "Ether", "crypto"),
]
BY_SYMBOL = {s: (p, n, k) for s, p, n, k in INSTRUMENTS}
# US Treasury yields, from the provider's daily table: display symbol -> (column, name).
RATES = {"US10Y": ("year10", "US 10-year yield"), "US2Y": ("year2", "US 2-year yield")}
TAPE = ["SPX", "NDX", "DJI", "RUT", "VIX", "US10Y", "GOLD", "WTI", "EURUSD", "BTCUSD"]
SECTIONS = ["tape", "indices", "rates", "commodities", "currencies", "crypto", "sectors", "movers"]


def provider_symbol(symbol: str) -> tuple[str, str, str | None]:
    """(provider symbol, kind, name) for a display symbol; stocks and funds pass through."""
    if symbol in BY_SYMBOL:
        p, n, k = BY_SYMBOL[symbol]
        return p, k, n
    return symbol.replace(".", "-"), "stock", None


def _pct(v) -> float | None:
    return v / 100 if isinstance(v, (int, float)) else None


def _num(v) -> float | None:
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


def _rows(data) -> list[dict]:
    if isinstance(data, dict):
        data = data.get("historical", [])
    return [r for r in (data or []) if isinstance(r, dict)]


def _ret(closes: list[float], back: int) -> float | None:
    return closes[-1] / closes[-1 - back] - 1 if len(closes) > back and closes[-1 - back] else None


class LiveMarkets:
    SOURCE = "FMP"  # the provider's name, as the answers carry it

    def __init__(self, fmp: Fmp, ttl: float = OVERVIEW_TTL, today=None):
        self.fmp, self.ttl = fmp, ttl
        self.today = today or (lambda: datetime.now(timezone.utc).date())
        self._good: dict[str, tuple[float, object]] = {}  # last good answer per section
        self._built: dict[str, datetime] = {}  # when each section was last read from the provider
        self._has_intraday = True  # until the data plan refuses intraday bars
        self._lock = threading.Lock()

    # --- overview -------------------------------------------------------------------------

    def _section(self, name: str, build, detail: bool = False):
        """A section of the overview: fresh within the TTL, else rebuilt; if the rebuild fails,
        the last good one; if there never was one, None (the caller uses sample data)."""
        key = f"{name}:{int(detail)}"
        with self._lock:
            hit = self._good.get(key)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1]
        try:
            value = build()
            if not value:
                raise MarketUnavailable("empty answer")
        except (MarketUnavailable, KeyError, TypeError, ValueError, IndexError) as exc:
            log.warning("live %s unavailable: %s", name, exc)
            return hit[1] if hit else None
        with self._lock:
            self._good[key] = (time.monotonic(), value)
            self._built[name] = datetime.now(timezone.utc)
        return value

    def _snapshot(self, symbol: str, q: dict, dates: list[str], closes: list[float]) -> dict:
        _, kind, name = provider_symbol(symbol)
        return {
            "symbol": symbol, "name": name or q.get("name") or symbol, "kind": kind,
            "price": q.get("price"), "change": q.get("change"), "change_pct": _pct(q.get("change_pct")),
            "return_1m": _ret(closes, 21), "return_ytd": _ytd(dates, closes),
            "return_1y": _ret(closes, 252), "spark": closes[-30:],
        }

    def _closes(self, provider: str) -> tuple[list[str], list[float]]:
        start = (self.today() - timedelta(days=400)).isoformat()
        rows = sorted(_rows(self.fmp.cached("historical-price-eod/light", DAILY_TTL, symbol=provider, **{"from": start})),
                      key=lambda r: r.get("date", ""))
        pairs = [(r["date"][:10], _num(r.get("price", r.get("close")))) for r in rows if r.get("date")]
        pairs = [(d, c) for d, c in pairs if c]
        return [d for d, _ in pairs], [c for _, c in pairs]

    def _instruments(self, kind: str, detail: bool) -> list[dict]:
        symbols = [s for s, _, _, k in INSTRUMENTS if k == kind]
        try:
            quotes = self.fmp.quotes([BY_SYMBOL[s][0] for s in symbols])
        except MarketUnavailable:
            quotes = {}  # quotes for this kind are not in the plan: daily closes below
        out = []
        histories: dict[str, tuple[list[str], list[float]]] = {}
        if detail:
            with ThreadPoolExecutor(max_workers=6) as pool:
                for s, h in zip(symbols, pool.map(lambda s: self._safe_closes(BY_SYMBOL[s][0]), symbols)):
                    histories[s] = h
        for s in symbols:
            q = quotes.get(BY_SYMBOL[s][0].upper())
            if not q or q.get("price") is None:
                q = self._from_closes(BY_SYMBOL[s][0])
            if not q:
                continue
            out.append(self._snapshot(s, q, *histories.get(s, ([], []))))
        if not out:
            raise MarketUnavailable(f"no {kind} prices")
        return out

    def _from_closes(self, provider: str) -> dict | None:
        """Price and day move from the last two daily closes, for symbols without a quote."""
        start = (self.today() - timedelta(days=12)).isoformat()
        try:
            rows = sorted(_rows(self.fmp.cached("historical-price-eod/light", CLOSE_TTL, symbol=provider, **{"from": start})),
                          key=lambda r: r.get("date", ""))
        except MarketUnavailable:
            return None
        closes = [c for c in (_num(r.get("price", r.get("close"))) for r in rows) if c]
        if len(closes) < 2:
            return None
        last, prev = closes[-1], closes[-2]
        return {"price": last, "change": last - prev, "change_pct": (last / prev - 1) * 100}

    def _safe_closes(self, provider: str) -> tuple[list[str], list[float]]:
        try:
            return self._closes(provider)
        except MarketUnavailable:
            return [], []

    def _rate_rows(self) -> list[dict]:
        """The Treasury's daily yields of the last two weeks: a date and a figure per maturity."""
        today = self.today()
        return _rows(self.fmp.cached("treasury-rates", self.ttl, **{"from": (today - timedelta(days=14)).isoformat(),
                                                                  "to": today.isoformat()}))

    def _rates(self) -> list[dict]:
        rows = sorted(self._rate_rows(), key=lambda r: r.get("date", ""), reverse=True)
        out = []
        for symbol, (column, name) in RATES.items():
            vals = [_num(r.get(column)) for r in rows if _num(r.get(column)) is not None]
            if len(vals) < 2:
                continue
            last, prev = vals[0], vals[1]
            out.append({"symbol": symbol, "name": name, "kind": "rate", "price": last, "change": round(last - prev, 3),
                        "change_pct": last / prev - 1 if prev else None, "return_1m": None, "return_ytd": None,
                        "return_1y": None, "spark": list(reversed(vals[:30]))})
        return out

    def _sectors(self) -> list[dict]:
        day = self.today()
        for _ in range(6):  # the last trading day with a snapshot
            rows = _rows(self.fmp.cached("sector-performance-snapshot", self.ttl, date=day.isoformat()))
            if rows:
                break
            day -= timedelta(days=1)
        by: dict[str, list[float]] = {}
        for r in rows:
            v = _num(r.get("averageChange"))
            if r.get("sector") and v is not None:
                by.setdefault(r["sector"], []).append(v)
        return [{"name": k, "change_pct": sum(v) / len(v) / 100, "return_ytd": None, "members": []} for k, v in by.items()]

    def _movers(self) -> dict:
        def listing(path: str) -> list[dict]:
            out = []
            for r in _rows(self.fmp.cached(path, self.ttl)):
                sym = str(r.get("symbol", "")).upper()
                if not sym or (_num(r.get("price")) or 0) < MOVERS_MIN_PRICE:
                    continue
                if len(out) == 6:
                    break
                out.append({"symbol": sym, "name": r.get("name") or sym, "kind": "stock", "price": _num(r.get("price")),
                            "change": _num(r.get("change")),
                            "change_pct": _pct(_num(r.get("changesPercentage", r.get("changePercentage")))),
                            "volume": _num(r.get("volume")), "sector": "", "return_1m": None, "return_ytd": None,
                            "return_1y": None, "spark": []})
            if not out:
                raise MarketUnavailable(f"{path}: nothing")
            return out
        return {"gainers": listing("biggest-gainers"), "losers": listing("biggest-losers"), "active": listing("most-actives")}

    def overview(self, detail: bool = False) -> dict:
        fallback = sample.overview()
        parts: dict[str, object] = {}
        for kind, section in (("index", "indices"), ("commodity", "commodities"), ("fx", "currencies"), ("crypto", "crypto")):
            parts[section] = self._section(section, lambda kind=kind: self._instruments(kind, detail), detail)
        parts["rates"] = self._section("rates", self._rates)
        parts["sectors"] = self._section("sectors", self._sectors)
        parts["movers"] = self._section("movers", self._movers)
        samples = [k for k, v in parts.items() if v is None]
        out = {k: (v if v is not None else fallback[k]) for k, v in parts.items()}
        every = {s["symbol"]: s for k in ("indices", "rates", "commodities", "currencies", "crypto") for s in out[k]}
        out["tape"] = [every[s] for s in TAPE if s in every]
        if any(s in samples for s in ("indices", "rates", "commodities", "currencies", "crypto")):
            samples.append("tape")
        # The oldest live part dates the page: a cached answer keeps the time it was read.
        built = [t for k, t in self._built.items() if k not in samples]
        as_of = min(built) if built else datetime.now(timezone.utc)
        return {"sample": len(samples) == len(SECTIONS), "sample_sections": sorted(samples), "source": self.SOURCE,
                "as_of": as_of.replace(microsecond=0).isoformat(), "intraday": self._has_intraday, **out}

    # --- charts ---------------------------------------------------------------------------

    def _daily(self, provider: str) -> list[dict]:
        start = (self.today() - timedelta(days=5 * 366 + 10)).isoformat()
        rows = _rows(self.fmp.cached("historical-price-eod/full", DAILY_TTL, symbol=provider, **{"from": start}))
        bars = []
        for r in sorted(rows, key=lambda r: r.get("date", "")):
            o, h, lo, c = (_num(r.get(k)) for k in ("open", "high", "low", "close"))
            if None in (o, h, lo, c) or not r.get("date"):
                continue
            bars.append({"time": r["date"][:10], "open": o, "high": h, "low": lo, "close": c,
                         "volume": int(_num(r.get("volume")) or 0)})
        if len(bars) < 2:
            raise MarketUnavailable("no daily prices")
        return bars

    def _intraday(self, provider: str, interval: str, days: int) -> list[dict]:
        today = self.today()
        try:
            rows = _rows(self.fmp.cached(f"historical-chart/{interval}", INTRADAY_TTL, symbol=provider,
                                         **{"from": (today - timedelta(days=days)).isoformat(), "to": today.isoformat()}))
        except NotInPlan:
            self._has_intraday = False  # the overview says so, and the site stops asking for 1D and 5D
            raise
        bars = []
        for r in sorted(rows, key=lambda r: r.get("date", "")):
            o, h, lo, c = (_num(r.get(k)) for k in ("open", "high", "low", "close"))
            if None in (o, h, lo, c) or not r.get("date"):
                continue
            # The exchange's clock, shown as is (the chart's time axis is UTC).
            t = datetime.strptime(r["date"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            bars.append({"time": int(t.timestamp()), "day": r["date"][:10], "open": o, "high": h, "low": lo, "close": c,
                         "volume": int(_num(r.get("volume")) or 0)})
        if not bars:
            raise MarketUnavailable("no intraday prices")
        return bars

    def chart(self, symbol: str, rng: str = "1Y", name: str | None = None) -> dict:
        provider, kind, known = provider_symbol(symbol)
        rng = rng.upper() if rng.upper() in sample.RANGES else "1Y"
        daily = self._daily(provider)
        if rng in ("1D", "5D"):
            intraday = self._intraday(provider, "5min" if rng == "1D" else "30min", 4 if rng == "1D" else 10)
            days = sorted({b["day"] for b in intraday})
            keep = days[-1:] if rng == "1D" else days[-5:]
            bars = [{k: v for k, v in b.items() if k != "day"} for b in intraday if b["day"] in keep]
            before = [b for b in daily if b["time"] < keep[0]]
            prev_close = before[-1]["close"] if before else bars[0]["open"]
            interval = "5m" if rng == "1D" else "30m"
        else:
            if rng == "5Y":
                weeks: dict[tuple, list[dict]] = {}
                for b in daily[-1260:]:
                    weeks.setdefault(date.fromisoformat(b["time"]).isocalendar()[:2], []).append(b)
                bars = [{"time": w[0]["time"], "open": w[0]["open"], "high": max(x["high"] for x in w),
                         "low": min(x["low"] for x in w), "close": w[-1]["close"], "volume": sum(x["volume"] for x in w)}
                        for w in weeks.values()]
                interval = "1W"
            else:
                if rng == "YTD":
                    year = daily[-1]["time"][:4]
                    bars = [b for b in daily if b["time"][:4] == year]
                else:
                    bars = daily[-{"1M": 22, "6M": 126, "1Y": 252}[rng]:]
                interval = "1D"
            prev_close = daily[-2]["close"]
        return {"sample": False, "source": self.SOURCE, "symbol": symbol, "name": known or name or symbol, "kind": kind,
                "range": rng, "interval": interval, "prev_close": prev_close, "bars": bars}

    # --- quote ----------------------------------------------------------------------------

    def quote(self, ticker: str, name: str | None = None) -> dict:
        provider, kind, known = provider_symbol(ticker)
        try:
            q = self.fmp.quotes([provider]).get(provider.upper())
        except MarketUnavailable:
            q = None
        try:
            daily = self._daily(provider)
        except MarketUnavailable:
            daily = []
        closes = [b["close"] for b in daily]
        if not q or q.get("price") is None:
            # No quote in the data plan (indices, commodities): the last daily bar stands in.
            if len(daily) < 2:
                raise MarketUnavailable("no quote")
            last, prev, year = daily[-1], daily[-2]["close"], daily[-252:]
            q = {"price": last["close"], "change": last["close"] - prev, "change_pct": (last["close"] / prev - 1) * 100,
                 "previous_close": prev, "open": last["open"], "day_low": last["low"], "day_high": last["high"],
                 "year_low": min(b["low"] for b in year), "year_high": max(b["high"] for b in year),
                 "volume": last["volume"] or None}
            # The same closes as the overview, so a figure reads the same on both pages.
            q |= self._from_closes(provider) or {}
        profile: dict = {}
        if kind == "stock":
            try:
                profile = self.fmp.profile(provider)
            except MarketUnavailable:
                profile = {}
            if profile.get("is_etf"):
                kind = "etf"
        price = q["price"]
        # A market value kept with the company's facts ages with them: its share count does not.
        cap = q.get("market_cap") or (price * profile["shares"] if profile.get("shares") and price else profile.get("market_cap"))
        last_dividend = profile.get("last_dividend")
        volumes = [b["volume"] for b in daily[-63:] if b["volume"]]
        return {
            "sample": False, "source": self.SOURCE,
            "symbol": ticker, "name": known or q.get("name") or profile.get("name") or name or ticker, "kind": kind,
            "price": price, "change": q.get("change"), "change_pct": _pct(q.get("change_pct")),
            "exchange": profile.get("exchange") or q.get("exchange") or "", "sector": profile.get("sector") or "—",
            "prev_close": q.get("previous_close"), "open": q.get("open"),
            "day_low": q.get("day_low"), "day_high": q.get("day_high"),
            "year_low": q.get("year_low"), "year_high": q.get("year_high"),
            "volume": q.get("volume"),
            "avg_volume": profile.get("average_volume") or (sum(volumes) / len(volumes) if volumes else None),
            "market_cap": cap if kind in ("stock", "etf") else None,
            "pe": profile.get("pe"), "eps": profile.get("eps"),
            "dividend_yield": last_dividend / price if last_dividend and price else None,
            "beta": profile.get("beta"),
            "return_1m": _ret(closes, 21), "return_6m": _ret(closes, 126),
            "return_ytd": _ytd([b["time"] for b in daily], closes), "return_1y": _ret(closes, 252),
            "return_5y": _ret(closes, 1250), "spark": closes[-30:],
            "news": [],  # the API fills it from the news desk
        }


def _ytd(dates: list[str], closes: list[float]) -> float | None:
    if not dates:
        return None
    year = dates[-1][:4]
    before = [c for d, c in zip(dates, closes) if d[:4] < year]
    return closes[-1] / before[-1] - 1 if before and before[-1] else None


class SampleMarkets:
    """The sample data behind the same interface (no provider key, local development, tests)."""

    def overview(self, detail: bool = False) -> dict:
        return sample.overview() | {"sample_sections": SECTIONS, "source": "sample"}

    def chart(self, symbol: str, rng: str = "1Y", name: str | None = None) -> dict:
        return sample.chart(symbol, rng, name=name)

    def quote(self, ticker: str, name: str | None = None) -> dict:
        return sample.quote(ticker, name=name)


def default_markets(market) -> LiveMarkets | SampleMarkets:
    """The public pages' figures, from the same provider as My Hub's: Yahoo when it is there,
    else FMP when it has a key, else the sample data."""
    from .yahoo import Yahoo, YahooMarkets  # here, not at the top: yahoo.py builds on this module

    if os.environ.get("MARKETHUB_SAMPLE_MARKETS") == "1":
        return SampleMarkets()
    yahoo = next((s for s in [market, *getattr(market, "sources", [])] if isinstance(s, Yahoo)), None)
    if yahoo:
        return YahooMarkets(yahoo)
    if not getattr(market, "api_key", ""):
        return SampleMarkets()
    return LiveMarkets(market)
