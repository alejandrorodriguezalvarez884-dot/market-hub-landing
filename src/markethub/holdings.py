"""The market data behind My Hub, and its stand-in for when the provider does not answer.

For every instrument a user holds or follows, the private area needs its quote, its daily closes
and a few facts about it (sector, country, size, beta, dividend). They come from the provider
(``market.Fmp``). When it does not answer (no key, the quota used up), a whole answer is built
from the sample data instead and is marked as such, so the pages can say so. It is never a mix:
a real price over an invented history would be worse than either.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from . import sample
from .config import HISTORY_DAYS
from .market import MarketUnavailable

# What a portfolio is set against: the funds that follow the four indices everybody quotes.
INDICES = [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("DIA", "Dow Jones"), ("IWM", "Russell 2000")]
BENCHMARK = INDICES[0][0]

# In the sample data, a fund with no series of its own follows its index.
ALIASES = {"DIA": "DJI", "IWM": "RUT"}
# Where the sample data places the foreign companies most often held through a US listing.
# Everything else it takes to be American, which most US-listed companies are.
SAMPLE_COUNTRIES = {
    "TSM": "TW", "ASML": "NL", "NVO": "DK", "SAP": "DE", "TM": "JP", "SONY": "JP", "HMC": "JP", "MUFG": "JP",
    "SHEL": "GB", "AZN": "GB", "HSBC": "GB", "UL": "GB", "BP": "GB", "GSK": "GB", "DEO": "GB", "BTI": "GB", "RIO": "GB", "ARM": "GB",
    "NVS": "CH", "UBS": "CH", "TTE": "FR", "SNY": "FR", "SAN": "ES", "BBVA": "ES", "ING": "NL", "STLA": "NL", "RACE": "IT",
    "BABA": "CN", "PDD": "CN", "JD": "CN", "BIDU": "CN", "NIO": "CN", "INFY": "IN", "HDB": "IN", "SE": "SG",
    "SHOP": "CA", "RY": "CA", "TD": "CA", "CNQ": "CA", "ENB": "CA", "MELI": "UY", "VALE": "BR", "PBR": "BR", "ITUB": "BR", "NU": "BR",
    "BHP": "AU", "SPOT": "LU", "NOK": "FI", "ERIC": "SE", "LIN": "IE", "ACN": "IE", "MDT": "IE",
}
# And the sector of companies the sample has no entry for: without it each would get one at random.
SAMPLE_SECTORS = {sector: tickers.split() for sector, tickers in {
    "Technology": "TSM ASML SAP ARM INFY ORCL CRM ADBE AVGO INTC QCOM CSCO IBM PLTR SHOP SONY NOK ERIC ACN TXN MU NOW",
    "Healthcare": "NVO AZN NVS SNY GSK PFE MRK ABBV TMO MDT ABT AMGN",
    "Financial Services": "HSBC UBS SAN BBVA ING RY TD MUFG ITUB NU HDB BAC WFC GS MS MA PYPL AXP C BLK",
    "Energy": "SHEL BP TTE CNQ ENB PBR COP SLB",
    "Consumer Cyclical": "TM HMC BABA PDD JD NIO MELI STLA RACE NKE MCD SBUX F GM BKNG",
    "Consumer Defensive": "UL DEO BTI PEP PM MDLZ",
    "Basic Materials": "RIO BHP VALE FCX NEM",
    "Communication Services": "BIDU SPOT SE DIS T VZ CMCSA TMUS",
    "Industrials": "GE UNP UPS HON RTX DE LMT",
    "Utilities": "DUK SO",
    "Real Estate": "AMT O",
}.items()}
SAMPLE_SECTOR_OF = {ticker: sector for sector, tickers in SAMPLE_SECTORS.items() for ticker in tickers}
COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada", "CN": "China", "JP": "Japan", "DE": "Germany", "FR": "France",
    "NL": "Netherlands", "CH": "Switzerland", "IE": "Ireland", "TW": "Taiwan", "DK": "Denmark", "ES": "Spain", "IT": "Italy",
    "IN": "India", "BR": "Brazil", "AU": "Australia", "SG": "Singapore", "KR": "South Korea", "IL": "Israel", "SE": "Sweden",
    "FI": "Finland", "LU": "Luxembourg", "UY": "Uruguay", "MX": "Mexico", "AR": "Argentina", "HK": "Hong Kong", "BM": "Bermuda",
    "KY": "Cayman Islands", "ZA": "South Africa", "NO": "Norway", "BE": "Belgium", "CL": "Chile", "CO": "Colombia", "GR": "Greece",
}


def country_name(code: str | None) -> str:
    code = (code or "").strip().upper()
    return COUNTRY_NAMES.get(code, code) if code else "Unknown"


class SampleData:
    """The provider's three calls, answered from the sample data (sample.py): generated, not
    observed, and the same from one visit to the next."""

    def __init__(self, name_of: Callable[[str], str | None] | None = None):
        self.name_of = name_of or (lambda ticker: None)

    def _rows(self, ticker: str):
        s = sample.spec(ALIASES.get(ticker, ticker))
        return s, sample.daily(s.symbol, s.name)

    def _name(self, ticker: str, s: sample.Spec) -> str:
        if ticker in ALIASES:
            return dict(INDICES)[ticker]
        # The sample's own name where it has one: the SEC's list writes them in capitals.
        return s.name if s.name != s.symbol else self.name_of(ticker) or ticker

    def quotes(self, tickers: list[str]) -> dict[str, dict]:
        out = {}
        for t in tickers:
            s, rows = self._rows(t)
            last, prev = rows[-1][4], rows[-2][4]
            year = [r[4] for r in rows[-252:]]
            out[t] = {"ticker": t, "name": self._name(t, s), "price": last, "change": round(last - prev, 4),
                      "change_pct": (last / prev - 1) * 100, "previous_close": prev, "year_high": max(year), "year_low": min(year),
                      "market_cap": last * s.shares if s.shares else None}
        return out

    def history(self, ticker: str) -> list[dict]:
        _, rows = self._rows(ticker)
        since = rows[-1][0] - timedelta(days=HISTORY_DAYS)
        return [{"date": r[0].isoformat(), "close": r[4]} for r in rows if r[0] >= since]

    def profile(self, ticker: str) -> dict:
        s, rows = self._rows(ticker)
        fund = s.kind == "etf" or ticker in ALIASES
        return {"sector": "" if fund else SAMPLE_SECTOR_OF.get(ticker, s.sector), "industry": "", "name": self._name(ticker, s), "is_etf": fund, "exchange": s.exchange,
                "beta": sample.beta_of(s), "last_dividend": round(rows[-1][4] * s.dividend_yield, 4),
                "market_cap": rows[-1][4] * s.shares if s.shares else None, "country": SAMPLE_COUNTRIES.get(ticker, "US")}


@dataclass
class Gathered:
    quotes: dict[str, dict]
    histories: dict[str, list[dict]]
    profiles: dict[str, dict]
    sample: bool


def sample_only() -> bool:
    return os.environ.get("MARKETHUB_SAMPLE_MARKETS") == "1"


def gather(market, tickers: list[str], held: list[str], stand_in: SampleData | None = None, sample: bool = False) -> Gathered:
    """Quotes and closes of ``tickers`` and the facts of the ``held`` ones. From the provider; if
    it does not answer or prices nothing, from ``stand_in`` when there is one."""

    def read(source, is_sample: bool) -> Gathered:
        quotes = source.quotes(tickers) if tickers else {}

        def history(t: str) -> list[dict]:
            try:
                return source.history(t)
            except MarketUnavailable:
                return []

        def profile(t: str) -> dict:
            try:
                return source.profile(t)
            except MarketUnavailable:
                return {}

        with ThreadPoolExecutor(max_workers=8) as pool:
            histories = dict(zip(tickers, pool.map(history, tickers)))
            profiles = dict(zip(held, pool.map(profile, held)))
        return Gathered(quotes, histories, profiles, is_sample)

    if not (sample and stand_in):
        try:
            got = read(market, False)
            if not tickers or not stand_in or any(q.get("price") is not None for q in got.quotes.values()):
                return got
        except MarketUnavailable:
            if not stand_in:
                raise
    return read(stand_in, True)
