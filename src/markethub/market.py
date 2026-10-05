"""Market data for the dashboard: quotes, daily closes and sectors (FMP), and the company list
behind search (SEC). Answers are cached in memory for a short while, so a dashboard refresh does
not spend the provider's quota."""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

import httpx

from .config import (FMP_BASE, HISTORY_DAYS, HISTORY_TTL_SECONDS, PROFILE_TTL_SECONDS,
                     QUOTE_TTL_SECONDS, SEC_TICKERS_URL)


class MarketUnavailable(Exception):
    """No key, a plan that does not include the call, or a provider that did not answer."""


class TTLCache:
    def __init__(self):
        self._items: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl: float) -> Any | None:
        with self._lock:
            hit = self._items.get(key)
            if hit and time.monotonic() - hit[0] < ttl:
                return hit[1]
            return None

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._items[key] = (time.monotonic(), value)


def _num(v: Any) -> float | None:
    try:
        return None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None


class Fmp:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("FMP_API_KEY", "").strip()
        self.client = client or httpx.Client(timeout=20)
        self.cache = TTLCache()

    def _get(self, path: str, **params: Any) -> Any:
        if not self.api_key:
            raise MarketUnavailable("FMP_API_KEY is not set.")
        try:
            resp = self.client.get(f"{FMP_BASE}/{path}", params={**params, "apikey": self.api_key})
        except httpx.HTTPError:
            raise MarketUnavailable("The market data provider did not answer.") from None
        if resp.status_code >= 400:
            # Never pass the provider's body on: it could echo request details.
            raise MarketUnavailable(f"The market data provider answered {resp.status_code}.")
        return resp.json()

    def cached(self, path: str, ttl: float, **params: Any) -> Any:
        """Any provider path, answered from memory for ``ttl`` seconds."""
        key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        hit = self.cache.get(key, ttl)
        if hit is not None:
            return hit
        data = self._get(path, **params)
        self.cache.put(key, data)
        return data

    def quotes(self, tickers: list[str]) -> dict[str, dict]:
        """Last price, day change and 52-week range per ticker. Unknown tickers are left out."""
        out, missing = {}, []
        for t in tickers:
            hit = self.cache.get(f"q:{t}", QUOTE_TTL_SECONDS)
            if hit is not None:
                out[t] = hit
            else:
                missing.append(t)
        if missing:
            rows: list[dict] = []
            try:
                rows = self._get("batch-quote", symbols=",".join(missing)) or []
            except MarketUnavailable:
                # Batch quotes are not in every plan: one call per ticker instead.
                for t in missing:
                    rows.extend(self._get("quote", symbol=t) or [])
            for row in rows:
                t = str(row.get("symbol", "")).upper()
                if not t:
                    continue
                q = {
                    "ticker": t,
                    "name": row.get("name") or t,
                    "price": _num(row.get("price")),
                    "change": _num(row.get("change")),
                    "change_pct": _num(row.get("changePercentage", row.get("changesPercentage"))),
                    "previous_close": _num(row.get("previousClose")),
                    "year_high": _num(row.get("yearHigh")),
                    "year_low": _num(row.get("yearLow")),
                    "market_cap": _num(row.get("marketCap")),
                    "volume": _num(row.get("volume")),
                    "open": _num(row.get("open")),
                    "day_low": _num(row.get("dayLow")),
                    "day_high": _num(row.get("dayHigh")),
                    "exchange": row.get("exchange") or "",
                    "timestamp": row.get("timestamp"),
                }
                self.cache.put(f"q:{t}", q)
                out[t] = q
        return out

    def history(self, ticker: str) -> list[dict]:
        """Daily closes for the last ``HISTORY_DAYS`` days, oldest first."""
        hit = self.cache.get(f"h:{ticker}", HISTORY_TTL_SECONDS)
        if hit is not None:
            return hit
        start = (date.today() - timedelta(days=HISTORY_DAYS)).isoformat()
        data = self._get("historical-price-eod/light", symbol=ticker, **{"from": start}) or []
        rows = data.get("historical", []) if isinstance(data, dict) else data
        bars = sorted(({"date": r["date"][:10], "close": _num(r.get("price", r.get("close")))}
                       for r in rows if r.get("date")), key=lambda b: b["date"])
        bars = [b for b in bars if b["close"] is not None]
        self.cache.put(f"h:{ticker}", bars)
        return bars

    def profile(self, ticker: str) -> dict:
        hit = self.cache.get(f"p:{ticker}", PROFILE_TTL_SECONDS)
        if hit is not None:
            return hit
        rows = self._get("profile", symbol=ticker) or []
        row = rows[0] if rows else {}
        p = {"sector": row.get("sector") or "", "industry": row.get("industry") or "",
             "name": row.get("companyName") or ticker, "is_etf": bool(row.get("isEtf")),
             "exchange": row.get("exchange") or row.get("exchangeShortName") or "",
             "beta": _num(row.get("beta")), "last_dividend": _num(row.get("lastDividend")),
             "average_volume": _num(row.get("averageVolume", row.get("volAvg")))}
        self.cache.put(f"p:{ticker}", p)
        return p


# --- Company search (SEC list of US-listed companies) ---------------------------------------


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str


def _norm(text: str) -> str:
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\b(inc|corp|corporation|co|company|ltd|plc|holdings?|group|the)\b", " ", text)
    return " ".join(text.split())


def sec_loader(client: httpx.Client | None = None) -> list[Company]:
    agent = os.environ.get("SEC_USER_AGENT", "").strip() or "market-hub contact@example.com"
    c = client or httpx.Client(timeout=30)
    try:
        resp = c.get(SEC_TICKERS_URL, headers={"User-Agent": agent})
        resp.raise_for_status()
    except httpx.HTTPError:
        raise MarketUnavailable("The SEC company list is not available right now.") from None
    out, seen = [], set()
    for row in resp.json().values():
        t = str(row["ticker"]).upper()
        if t not in seen:
            seen.add(t)
            out.append(Company(t, str(row["title"])))
    return out


# Funds the SEC list leaves out but people often hold.
EXTRA = [Company(t, n) for t, n in (
    ("SPY", "SPDR S&P 500 ETF Trust"), ("QQQ", "Invesco QQQ Trust"), ("VOO", "Vanguard S&P 500 ETF"),
    ("VTI", "Vanguard Total Stock Market ETF"), ("IWM", "iShares Russell 2000 ETF"),
    ("DIA", "SPDR Dow Jones Industrial Average ETF"), ("VEA", "Vanguard FTSE Developed Markets ETF"),
    ("VWO", "Vanguard FTSE Emerging Markets ETF"), ("BND", "Vanguard Total Bond Market ETF"),
    ("GLD", "SPDR Gold Shares"), ("TLT", "iShares 20+ Year Treasury Bond ETF"),
)]


class Directory:
    def __init__(self, loader: Callable[[], list[Company]] = sec_loader, ttl: float = 86400):
        self._loader, self._ttl = loader, ttl
        self._companies: list[Company] | None = None
        self._by_ticker: dict[str, Company] = {}
        self._at = 0.0
        self._lock = threading.Lock()

    def _all(self) -> list[Company]:
        with self._lock:
            if self._companies is None or time.monotonic() - self._at > self._ttl:
                companies = self._loader()
                known = {c.ticker for c in companies}
                companies += [c for c in EXTRA if c.ticker not in known]
                self._companies, self._at = companies, time.monotonic()
                self._by_ticker = {c.ticker: c for c in companies}
            return self._companies

    def get(self, ticker: str) -> Company | None:
        self._all()
        return self._by_ticker.get(ticker.strip().upper().replace(".", "-"))

    def known(self, ticker: str) -> bool:
        return self.get(ticker) is not None

    def search(self, query: str, limit: int = 8) -> list[Company]:
        q = query.strip()
        if not q:
            return []
        qt, qn = q.upper().replace(".", "-"), _norm(q)
        exact, prefix, start, word = [], [], [], []
        for c in self._all():
            name = _norm(c.name)
            if c.ticker == qt:
                exact.append(c)
            elif qt.isalnum() and c.ticker.startswith(qt):
                prefix.append(c)
            elif qn and name.startswith(qn):
                start.append(c)
            elif qn and len(qn) >= 3 and f" {qn}" in f" {name}":
                word.append(c)
        groups = [exact, start, prefix, word] if len(q) > 4 else [exact, prefix, start, word]
        out: list[Company] = []
        for g in groups:
            for c in g:
                if c not in out:
                    out.append(c)
                if len(out) >= limit:
                    return out
        return out
