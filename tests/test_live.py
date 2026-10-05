"""Live market data: provider answers turned into the portal's shapes, and each part falling back
on its own when the provider or the data plan does not answer it."""

import logging
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from conftest import CLIENT_ID, fake_verifier
from markethub.api import create_app
from markethub.live import LiveMarkets, SampleMarkets, default_markets
from markethub.market import Company, Directory, MarketUnavailable
from markethub.users import MemoryUsers

TODAY = date(2026, 10, 5)  # a Monday


def daily(n=1300, start=100.0):
    rows, d, p = [], TODAY - timedelta(days=int(n * 1.45)), start
    while d <= TODAY:
        if d.weekday() < 5:
            p *= 1.0004
            rows.append({"symbol": "X", "date": d.isoformat(), "open": p * 0.99, "high": p * 1.01, "low": p * 0.98,
                         "close": p, "volume": 1000})
        d += timedelta(days=1)
    return list(reversed(rows))  # the provider answers newest first


def intraday(days=(date(2026, 10, 2), TODAY)):
    rows = []
    for d in days:
        for i in range(78):
            m = 9 * 60 + 30 + 5 * i
            rows.append({"date": f"{d.isoformat()} {m // 60:02d}:{m % 60:02d}:00", "open": 10 + i, "high": 11 + i,
                         "low": 9 + i, "close": 10.5 + i, "volume": 5})
    return list(reversed(rows))


class FakeFmp:
    """Answers like FMP's stable API; paths in ``fail`` answer as a plan without them would."""

    api_key = "test-key"

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.calls: list[str] = []

    def cached(self, path, ttl, **params):
        self.calls.append(path)
        if any(path.startswith(f) for f in self.fail):
            raise MarketUnavailable("The market data provider answered 402.")
        if path == "treasury-rates":
            return [{"date": "2026-10-05", "year2": 3.90, "year10": 4.20}, {"date": "2026-10-02", "year2": 3.85, "year10": 4.10}]
        if path == "sector-performance-snapshot":
            if params["date"] != "2026-10-02":  # no snapshot yet for today
                return []
            return [{"date": "2026-10-02", "sector": "Technology", "exchange": "NASDAQ", "averageChange": 1.0},
                    {"date": "2026-10-02", "sector": "Technology", "exchange": "NYSE", "averageChange": 2.0},
                    {"date": "2026-10-02", "sector": "Energy", "exchange": "NYSE", "averageChange": -0.5}]
        if path in ("biggest-gainers", "biggest-losers", "most-actives"):
            sign = -1 if path == "biggest-losers" else 1
            return [{"symbol": f"T{i}", "name": f"Company {i}", "price": 10.0 + i, "change": sign * 1.0,
                     "changesPercentage": sign * (9.0 - i), "exchange": "NASDAQ"} for i in range(8)]
        if path == "historical-price-eod/full":
            return daily()
        if path == "historical-price-eod/light":
            return [{"symbol": "X", "date": r["date"], "price": r["close"], "volume": 1} for r in daily(300)]
        if path.startswith("historical-chart/"):
            return intraday()
        raise AssertionError(path)

    def quotes(self, tickers):
        self.calls.append("quote")
        if "quote" in self.fail:
            raise MarketUnavailable("402")
        return {t.upper(): {"ticker": t.upper(), "name": f"{t} name", "price": 100.0, "change": 1.5, "change_pct": 1.5,
                            "previous_close": 98.5, "year_high": 120.0, "year_low": 80.0, "market_cap": 2e12,
                            "volume": 1e6, "open": 99.0, "day_low": 98.0, "day_high": 101.0, "exchange": "NASDAQ"}
                for t in tickers}

    def profile(self, ticker):
        return {"sector": "Technology", "name": "Apple Inc.", "is_etf": ticker == "SPY", "exchange": "NASDAQ",
                "beta": 1.2, "last_dividend": 1.0, "average_volume": 5e7}


def live(fail=(), ttl=900):
    fmp = FakeFmp(fail)
    return LiveMarkets(fmp, ttl=ttl, today=lambda: TODAY), fmp


def test_overview_from_the_provider():
    m, _ = live()
    o = m.overview()
    assert o["sample"] is False and o["sample_sections"] == [] and o["source"] == "FMP"
    spx = next(s for s in o["indices"] if s["symbol"] == "SPX")
    assert spx["name"] == "S&P 500" and spx["price"] == 100.0 and spx["change_pct"] == pytest.approx(0.015)
    assert [s["symbol"] for s in o["tape"]][:3] == ["SPX", "NDX", "DJI"] and len(o["tape"]) == 10
    ten = next(r for r in o["rates"] if r["symbol"] == "US10Y")
    assert ten["price"] == 4.20 and ten["change"] == pytest.approx(0.10)
    tech = next(s for s in o["sectors"] if s["name"] == "Technology")
    assert tech["change_pct"] == pytest.approx(0.015)  # the mean of NASDAQ and NYSE, as a fraction
    assert len(o["movers"]["gainers"]) == 6 and o["movers"]["losers"][0]["change_pct"] < 0


def test_detail_adds_returns_from_daily_closes():
    m, _ = live()
    spx = next(s for s in m.overview(detail=True)["indices"] if s["symbol"] == "SPX")
    assert spx["return_1m"] > 0 and spx["return_ytd"] > 0 and len(spx["spark"]) == 30


def test_the_overview_is_cached_so_visits_do_not_spend_calls():
    m, fmp = live()
    m.overview()
    calls = len(fmp.calls)
    for _ in range(20):
        m.overview()
    assert len(fmp.calls) == calls


def test_a_part_the_plan_lacks_is_sample_and_named():
    m, _ = live(fail=("sector-performance-snapshot", "biggest-"))
    o = m.overview()
    assert o["sample_sections"] == ["movers", "sectors"] and o["sample"] is False
    assert next(s for s in o["indices"] if s["symbol"] == "SPX")["price"] == 100.0  # the rest stays live


def test_a_failed_refresh_keeps_the_last_good_answer():
    m, fmp = live(ttl=0)
    first = m.overview()["sectors"]
    fmp.fail.add("sector-performance-snapshot")
    again = m.overview()
    assert again["sectors"] == first and "sectors" not in again["sample_sections"]


def test_daily_ranges_and_weeks():
    m, _ = live()
    one_month = m.chart("SPX", "1M")
    assert one_month["interval"] == "1D" and len(one_month["bars"]) == 22 and one_month["sample"] is False
    times = [b["time"] for b in one_month["bars"]]
    assert times == sorted(times) and times[-1] == TODAY.isoformat()
    assert all(b["time"].startswith("2026") for b in m.chart("SPX", "YTD")["bars"])
    five = m.chart("SPX", "5Y")
    assert five["interval"] == "1W" and 250 < len(five["bars"]) < 270


def test_intraday_keeps_the_last_session_and_the_close_before_it():
    m, _ = live()
    day = m.chart("AAPL", "1D")
    assert day["interval"] == "5m" and len(day["bars"]) == 78
    daily_closes = {r["date"]: r["close"] for r in daily()}
    assert day["prev_close"] == pytest.approx(daily_closes["2026-10-02"])
    assert len(m.chart("AAPL", "5D")["bars"]) == 2 * 78  # the fake has two sessions


def test_intraday_outside_the_plan_says_so():
    m, _ = live(fail=("historical-chart/",))
    with pytest.raises(MarketUnavailable):
        m.chart("SPX", "1D")
    assert m.chart("SPX", "1M")["bars"]


def test_quote_from_the_provider():
    m, _ = live()
    q = m.quote("AAPL")
    assert q["sample"] is False and q["price"] == 100.0 and q["change_pct"] == pytest.approx(0.015)
    assert q["sector"] == "Technology" and q["beta"] == 1.2 and q["dividend_yield"] == pytest.approx(0.01)
    assert q["return_1y"] > 0 and q["news"]
    assert m.quote("SPY")["kind"] == "etf"
    index = m.quote("SPX")
    assert index["kind"] == "index" and index["market_cap"] is None and index["name"] == "S&P 500"


def test_api_uses_live_data_with_a_key_and_sample_without():
    directory = Directory(loader=lambda: [Company("AAPL", "Apple Inc.")])
    m, _ = live(fail=("historical-chart/",))
    app = create_app(users=MemoryUsers(), market=FakeFmp(), directory=directory, verifier=fake_verifier,
                     client_id=CLIENT_ID, session_secret="s", secure_cookies=False, markets=m)
    c = TestClient(app)
    assert c.get("/api/public/overview").json()["source"] == "FMP"
    assert c.get("/api/public/chart", params={"symbol": "SPX", "range": "1D"}).status_code == 503
    assert c.get("/api/public/chart", params={"symbol": "SPX", "range": "1M"}).json()["sample"] is False
    assert c.get("/api/public/news").json()["sample"] is True  # headlines stay sample for now
    assert isinstance(default_markets(FakeFmp()), LiveMarkets)

    class NoKey:
        api_key = ""
    assert isinstance(default_markets(NoKey()), SampleMarkets)


def test_the_provider_key_never_reaches_the_logs():
    create_app(users=MemoryUsers(), market=FakeFmp(), directory=Directory(loader=lambda: []), verifier=fake_verifier,
               client_id=CLIENT_ID, session_secret="s", markets=SampleMarkets())
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
