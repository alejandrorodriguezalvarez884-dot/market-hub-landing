"""Market data from Yahoo Finance, read with the yfinance library: the portal's provider by default.

It takes no key and has no daily quota, but it is not an official API: yfinance asks the addresses
Yahoo's own pages ask, and Yahoo can refuse an address that asks too much (or a data centre's).
So a symbol is read in one request (its daily bars, which carry the quote as well), the answer is
kept in memory, and after a refusal nothing is asked for a while. Treasury yields come from the
Treasury itself.

``Yahoo`` answers what My Hub asks of a provider (quotes, closes, facts about a company) in the
shapes of ``market.Fmp``. ``YahooMarkets`` is ``live.LiveMarkets`` reading from it. ``Fallback``
puts a second provider behind the first. Nothing is sent to Yahoo but symbols.
"""

from __future__ import annotations

import calendar
import csv
import io
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import httpx

from .config import HISTORY_DAYS, HISTORY_TTL_SECONDS, PROFILE_TTL_SECONDS, QUOTE_TTL_SECONDS
from .live import DAILY_TTL, INSTRUMENTS, INTRADAY_TTL, MOVERS_MIN_PRICE, LiveMarkets, _num, _pct, _ytd, provider_symbol
from .market import Fmp, MarketUnavailable, TTLCache

log = logging.getLogger("markethub.yahoo")

# With no quota to save, the public figures are read again this often.
OVERVIEW_TTL = float(os.environ.get("PUBLIC_MARKETS_TTL_SECONDS", "300"))
# After Yahoo refuses a request nothing is asked for this long; after any other failure, for a
# shorter while, so a provider that is down does not slow every page.
REFUSED_SECONDS = 300
FAILED_SECONDS = 60
WORKERS = 8

# The portal's symbols for what is not a stock (live.INSTRUMENTS) -> Yahoo's. Indices are the same.
SYMBOLS = {
    "GCUSD": "GC=F", "SIUSD": "SI=F", "CLUSD": "CL=F", "NGUSD": "NG=F", "HGUSD": "HG=F",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X", "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
}
# A sector's move of the day is its SPDR fund's.
SECTOR_FUNDS = [
    ("Technology", "XLK"), ("Communication Services", "XLC"), ("Consumer Cyclical", "XLY"), ("Consumer Defensive", "XLP"),
    ("Financial Services", "XLF"), ("Healthcare", "XLV"), ("Industrials", "XLI"), ("Energy", "XLE"), ("Utilities", "XLU"),
    ("Real Estate", "XLRE"), ("Basic Materials", "XLB"),
]
EXCHANGES = {"NasdaqGS": "NASDAQ", "NasdaqGM": "NASDAQ", "NasdaqCM": "NASDAQ", "NYSEArca": "NYSE Arca", "BATS": "Cboe BZX",
             "NYSEAmerican": "NYSE American"}
# The Treasury's own table of daily par yields, a year at a time.
TREASURY_URL = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{year}/all"
                "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv")
TREASURY_COLUMNS = {"2 Yr": "year2", "10 Yr": "year10"}


def _rows(frame):
    """(timestamp, open, high, low, close, volume) for each bar of a yfinance table that has a close."""
    if frame is None or getattr(frame, "empty", True):
        return
    columns = [frame[c].tolist() for c in ("Open", "High", "Low", "Close", "Volume")]
    for ts, o, h, lo, c, v in zip(frame.index, *columns):
        c = _num(c)
        if c is None or c != c:  # no close: a day without a trade
            continue
        o, h, lo = (x if isinstance(x, (int, float)) and x == x else c for x in (o, h, lo))
        yield ts, float(o), float(h), float(lo), c, int(v) if isinstance(v, (int, float)) and v == v else 0


def _late(frame, meta: dict) -> dict | None:
    """The last trade of a day's minutes when it fell outside the regular session: before the
    open ("pre") or after the close ("post"), set against the session's last price."""
    rows = list(_rows(frame))
    regular = (meta.get("currentTradingPeriod") or {}).get("regular") or {}
    base = _num(meta.get("regularMarketPrice"))
    opens, closes = regular.get("start"), regular.get("end")
    if not rows or not base or not hasattr(opens, "time") or not hasattr(closes, "time"):
        return None
    at, price = rows[-1][0], rows[-1][4]
    session = "pre" if at.time() < opens.time() else "post" if at.time() >= closes.time() else None
    if not session:
        return None  # the market is open: the quote is the price
    return {"session": session, "price": price, "change": price - base, "change_pct": price / base - 1, "at": at.isoformat()}


class Yahoo:
    def __init__(self, yf=None):
        self._yf = yf  # the yfinance module; tests pass a stand-in
        self._reads = TTLCache()  # symbol -> {"bars": daily bars, oldest first, "meta": the quote}
        self._facts = TTLCache()
        self._minutes = TTLCache()
        self._lates = TTLCache()
        self._quiet_until = 0.0
        self._lock = threading.Lock()

    @property
    def yf(self):
        with self._lock:
            if self._yf is None:
                import yfinance  # slow to import (pandas): only when the first price is asked for

                try:
                    yfinance.config.debug.hide_exceptions = False  # a missing ticker raises instead of printing
                except AttributeError:
                    pass
                self._yf = yfinance
            return self._yf

    def _call(self, what: str, ask):
        """One question to Yahoo. None when Yahoo has no such symbol."""
        if time.monotonic() < self._quiet_until:
            raise MarketUnavailable("The market data provider is not answering for now.")
        yf = self.yf
        try:
            got = ask(yf)
        except Exception as exc:  # yfinance raises its own errors and those of the HTTP library under it
            kind = type(exc).__name__
            if "Missing" in kind:
                log.info("yahoo %s -> no such symbol", what)
                return None
            self._quiet_until = time.monotonic() + (REFUSED_SECONDS if "RateLimit" in kind else FAILED_SECONDS)
            # The error's name only: its text can carry the address that was asked.
            log.warning("yahoo %s -> %s", what, kind)
            raise MarketUnavailable("The market data provider did not answer.") from None
        log.info("yahoo %s -> ok", what)
        return got

    def _read(self, symbol: str, ttl: float) -> dict:
        key = symbol.upper()
        hit = self._reads.get(key, ttl)
        if hit is not None:
            return hit

        def ask(yf):
            ticker = yf.Ticker(SYMBOLS.get(key, key))
            frame = ticker.history(period="5y", interval="1d", auto_adjust=False, actions=False)
            return frame, dict(getattr(ticker, "history_metadata", None) or {})

        got = self._call(f"bars {key}", ask)
        bars = [{"time": ts.strftime("%Y-%m-%d"), "open": o, "high": h, "low": lo, "close": c, "volume": v}
                for ts, o, h, lo, c, v in _rows(got[0])] if got else []
        read = {"bars": bars, "meta": got[1] if got else {}}
        self._reads.put(key, read)
        return read

    def _quote(self, ticker: str, read: dict) -> dict | None:
        bars, meta = read["bars"], read["meta"]
        if not bars:
            return None
        last, year = bars[-1], bars[-252:]
        price = _num(meta.get("regularMarketPrice")) or last["close"]
        # The day's bar is the last one, so the close before it is the previous close.
        prev = bars[-2]["close"] if len(bars) > 1 else None
        shares = (self._facts.get(ticker, PROFILE_TTL_SECONDS) or {}).get("shares")
        exchange = str(meta.get("fullExchangeName") or meta.get("exchangeName") or "")
        return {
            "ticker": ticker, "name": meta.get("longName") or meta.get("shortName") or ticker, "price": price,
            "change": price - prev if prev else None, "change_pct": (price / prev - 1) * 100 if prev else None,
            "previous_close": prev,
            "year_high": _num(meta.get("fiftyTwoWeekHigh")) or max(b["high"] for b in year),
            "year_low": _num(meta.get("fiftyTwoWeekLow")) or min(b["low"] for b in year),
            "market_cap": price * shares if shares else None,
            "volume": _num(meta.get("regularMarketVolume")) or last["volume"] or None,
            "open": last["open"], "day_low": _num(meta.get("regularMarketDayLow")) or last["low"],
            "day_high": _num(meta.get("regularMarketDayHigh")) or last["high"],
            "exchange": EXCHANGES.get(exchange, exchange), "timestamp": None,
        }

    def quotes(self, tickers: list[str]) -> dict[str, dict]:
        """Last price, day change and 52-week range per ticker. Unknown tickers are left out."""
        asked = [t.upper() for t in tickers]

        def read(t: str) -> dict | None:
            try:
                return self._read(t, QUOTE_TTL_SECONDS)
            except MarketUnavailable:
                return None

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            reads = list(pool.map(read, asked))
        if asked and all(r is None for r in reads):
            raise MarketUnavailable("The market data provider did not answer.")
        out = {}
        for t, r in zip(asked, reads):
            q = self._quote(t, r) if r else None
            if q:
                out[t] = q
        return out

    def daily(self, symbol: str) -> list[dict]:
        """Five years of daily bars, oldest first: time, open, high, low, close and volume."""
        return self._read(symbol, DAILY_TTL)["bars"]

    def history(self, ticker: str) -> list[dict]:
        """Daily closes for the last ``HISTORY_DAYS`` days, oldest first."""
        since = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
        return [{"date": b["time"], "close": b["close"]} for b in self._read(ticker, HISTORY_TTL_SECONDS)["bars"] if b["time"] >= since]

    def profile(self, ticker: str) -> dict:
        key = ticker.upper()
        hit = self._facts.get(key, PROFILE_TTL_SECONDS)
        if hit is not None:
            return hit
        info = self._call(f"facts {key}", lambda yf: dict(yf.Ticker(SYMBOLS.get(key, key)).info or {})) or {}
        fund = str(info.get("quoteType") or "").upper() in ("ETF", "MUTUALFUND")
        exchange = str(info.get("fullExchangeName") or info.get("exchange") or "")
        p = {"sector": info.get("sector") or "", "industry": info.get("industry") or "",
             "name": info.get("longName") or info.get("shortName") or ticker, "is_etf": fund,
             "exchange": EXCHANGES.get(exchange, exchange), "beta": _num(info.get("beta")) or _num(info.get("beta3Year")),
             # What a share pays in a year: the declared rate, or for a fund what it paid in the last one.
             "last_dividend": _num(info.get("dividendRate")) or _num(info.get("trailingAnnualDividendRate")),
             "average_volume": _num(info.get("averageVolume")), "market_cap": _num(info.get("marketCap")),
             "shares": _num(info.get("sharesOutstanding")), "country": info.get("country") or "",
             "pe": _num(info.get("trailingPE")), "eps": _num(info.get("trailingEps"))}
        self._facts.put(key, p)
        return p

    def intraday(self, symbol: str, interval: str, period: str) -> list[dict]:
        """Bars within the day, oldest first, on the exchange's own clock."""
        key = f"{symbol.upper()} {interval} {period}"
        hit = self._minutes.get(key, INTRADAY_TTL)
        if hit is not None:
            return hit
        frame = self._call(f"intraday {key}", lambda yf: yf.Ticker(SYMBOLS.get(symbol.upper(), symbol.upper())).history(
            period=period, interval=interval, auto_adjust=False, actions=False))
        # The exchange's clock, shown as is (the chart's time axis is UTC).
        bars = [{"time": calendar.timegm(ts.timetuple()), "day": ts.strftime("%Y-%m-%d"), "open": o, "high": h, "low": lo,
                 "close": c, "volume": v} for ts, o, h, lo, c, v in _rows(frame)]
        self._minutes.put(key, bars)
        return bars

    def extended(self, symbol: str) -> dict | None:
        """What a share last traded at before the open or after the close, while that is the
        latest there is: its session, price, move from the regular session's last price, and when."""
        key = symbol.upper()
        hit = self._lates.get(key, QUOTE_TTL_SECONDS)
        if hit is not None:
            return hit or None

        def ask(yf):
            ticker = yf.Ticker(SYMBOLS.get(key, key))
            frame = ticker.history(period="1d", interval="1m", prepost=True, auto_adjust=False, actions=False)
            return frame, dict(getattr(ticker, "history_metadata", None) or {})

        got = self._call(f"extended {key}", ask)
        late = _late(*got) if got else None
        self._lates.put(key, late or {})  # an empty answer is kept too: no trade out of hours
        return late

    def listed(self, which: str) -> list[dict]:
        """One of Yahoo's lists of the day: "day_gainers", "day_losers" or "most_actives"."""
        got = self._call(f"list {which}", lambda yf: yf.screen(which, count=25)) or {}
        return [r for r in got.get("quotes") or [] if isinstance(r, dict)]


class Fallback:
    """Several providers behind one: a question goes to the first that has an answer to it."""

    def __init__(self, *sources):
        self.sources = list(sources)

    def _first(self, ask, good):
        got = None
        for source in self.sources:
            try:
                got = ask(source)
            except MarketUnavailable:
                continue
            if good(got):
                return got
        if got is None:
            raise MarketUnavailable("The market data provider did not answer.")
        return got

    def quotes(self, tickers: list[str]) -> dict[str, dict]:
        return self._first(lambda s: s.quotes(tickers), lambda q: not tickers or any(v.get("price") is not None for v in q.values()))

    def history(self, ticker: str) -> list[dict]:
        return self._first(lambda s: s.history(ticker), bool)

    def profile(self, ticker: str) -> dict:
        return self._first(lambda s: s.profile(ticker), bool)


def default_market():
    """The provider behind the portal. MARKET_DATA names it: "yahoo" (the default), with FMP behind
    it when there is a key for it, or "fmp" alone."""
    fmp = Fmp()
    if os.environ.get("MARKET_DATA", "yahoo").strip().lower() == "fmp":
        return fmp
    return Fallback(Yahoo(), fmp) if fmp.api_key else Yahoo()


def treasury_yields(client: httpx.Client, year: int) -> list[dict]:
    """The Treasury's daily par yields of a year: a date and a figure per maturity, in percent."""
    try:
        resp = client.get(TREASURY_URL.format(year=year), headers={"User-Agent": "market-hub"})
        resp.raise_for_status()
    except httpx.HTTPError:
        raise MarketUnavailable("The Treasury's yields are not available right now.") from None
    out = []
    for row in csv.DictReader(io.StringIO(resp.text)):
        try:
            day = datetime.strptime((row.get("Date") or "").strip(), "%m/%d/%Y").date()
        except ValueError:
            continue
        out.append({"date": day.isoformat()} | {name: _num(row.get(column)) for column, name in TREASURY_COLUMNS.items()})
    return out


class YahooMarkets(LiveMarkets):
    """The public pages' figures, from Yahoo; the Treasury's yields from the Treasury."""

    SOURCE = "Yahoo Finance"

    def __init__(self, yahoo: Yahoo, ttl: float = OVERVIEW_TTL, today=None, client: httpx.Client | None = None):
        super().__init__(yahoo, ttl, today)
        self.yahoo = yahoo
        self.client = client or httpx.Client(timeout=20, follow_redirects=True)
        self._yields = TTLCache()

    def _closes(self, provider: str) -> tuple[list[str], list[float]]:
        since = (self.today() - timedelta(days=400)).isoformat()
        bars = [b for b in self.yahoo.daily(provider) if b["time"] >= since]
        return [b["time"] for b in bars], [b["close"] for b in bars]

    def _from_closes(self, provider: str) -> dict | None:
        try:
            bars = self.yahoo.daily(provider)
        except MarketUnavailable:
            return None
        if len(bars) < 2:
            return None
        last, prev = bars[-1]["close"], bars[-2]["close"]
        return {"price": last, "change": last - prev, "change_pct": (last / prev - 1) * 100}

    def _rate_rows(self) -> list[dict]:
        today = self.today()
        rows = self._yields.get("rows", self.ttl)
        if rows is None:
            rows = treasury_yields(self.client, today.year)
            if len(rows) < 2:  # the first days of a year
                rows += treasury_yields(self.client, today.year - 1)
            self._yields.put("rows", rows)
        since = (today - timedelta(days=45)).isoformat()
        return [r for r in rows if r["date"] >= since]

    def _sectors(self) -> list[dict]:
        quotes = self.yahoo.quotes([fund for _, fund in SECTOR_FUNDS])
        out = []
        for name, fund in SECTOR_FUNDS:
            q = quotes.get(fund)
            if q and q.get("change_pct") is not None:
                out.append({"name": name, "change_pct": q["change_pct"] / 100, "return_ytd": _ytd(*self._safe_closes(fund)), "members": []})
        return out

    def _movers(self) -> dict:
        def listing(which: str) -> list[dict]:
            out = []
            for r in self.yahoo.listed(which):
                sym, price = str(r.get("symbol", "")).upper(), _num(r.get("regularMarketPrice"))
                if not sym or (price or 0) < MOVERS_MIN_PRICE:
                    continue
                if len(out) == 6:
                    break
                out.append({"symbol": sym, "name": r.get("longName") or r.get("shortName") or sym, "kind": "stock", "price": price,
                            "change": _num(r.get("regularMarketChange")), "change_pct": _pct(_num(r.get("regularMarketChangePercent"))),
                            "volume": _num(r.get("regularMarketVolume")), "sector": "", "return_1m": None, "return_ytd": None,
                            "return_1y": None, "spark": []})
            if not out:
                raise MarketUnavailable(f"{which}: nothing")
            return out
        return {"gainers": listing("day_gainers"), "losers": listing("day_losers"), "active": listing("most_actives")}

    def overview(self, detail: bool = False) -> dict:
        with self._lock:
            hit = self._good.get(f"indices:{int(detail)}")
        if not hit or time.monotonic() - hit[0] >= self.ttl:
            # Every symbol of the page is read at once, side by side, before the parts are put together.
            try:
                self.yahoo.quotes([provider for _, provider, _, _ in INSTRUMENTS] + [fund for _, fund in SECTOR_FUNDS])
            except MarketUnavailable:
                pass
        return super().overview(detail)

    def quote(self, ticker: str, name: str | None = None) -> dict:
        q = super().quote(ticker, name)
        late = None
        if q["kind"] in ("stock", "etf"):  # the rest trade round the clock, or have no such hours
            try:
                late = self.yahoo.extended(provider_symbol(ticker)[0])
            except MarketUnavailable:
                late = None  # the page stands without it
        return q | {"extended": late}

    def _daily(self, provider: str) -> list[dict]:
        bars = self.yahoo.daily(provider)
        if len(bars) < 2:
            raise MarketUnavailable("no daily prices")
        return bars

    def _intraday(self, provider: str, interval: str, days: int) -> list[dict]:
        bars = self.yahoo.intraday(provider, "5m" if interval == "5min" else "30m", "5d" if interval == "5min" else "1mo")
        since = (self.today() - timedelta(days=days)).isoformat()
        bars = [b for b in bars if b["day"] >= since]
        if not bars:
            raise MarketUnavailable("no intraday prices")
        return bars
