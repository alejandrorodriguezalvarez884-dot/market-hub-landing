"""Yahoo as the provider: the shapes My Hub and the public pages expect, no network."""

from datetime import date

import httpx
import pandas as pd
import pytest

from markethub.holdings import country_name
from markethub.live import LiveMarkets, default_markets
from markethub.market import MarketUnavailable
from markethub.yahoo import Fallback, Yahoo, YahooMarkets, default_market

TODAY = date(2026, 10, 6)


class YFPricesMissingError(Exception):
    pass


class YFRateLimitError(Exception):
    pass


def frame(index, start=100.0):
    closes = [start + i for i in range(len(index))]
    return pd.DataFrame({"Open": [c - 1 for c in closes], "High": [c + 2 for c in closes], "Low": [c - 3 for c in closes],
                         "Close": closes, "Adj Close": closes, "Volume": [1000] * len(index)}, index=index)


class FakeTicker:
    def __init__(self, yf, symbol):
        self.yf, self.symbol = yf, symbol

    def history(self, period, interval, auto_adjust, actions, prepost=False):
        self.yf.calls.append(f"{self.symbol} {interval}")
        if self.yf.refusing:
            raise YFRateLimitError("Too Many Requests")
        if self.symbol in self.yf.missing:
            raise YFPricesMissingError(self.symbol)
        if interval == "1d":
            return frame(pd.bdate_range(end="2026-10-06", periods=300, tz="America/New_York"))
        if prepost:  # a day's minutes with the hours around the session, up to the fake clock
            return frame(pd.date_range("2026-10-07 04:00", self.yf.clock, freq="1min", tz="America/New_York"), start=402.0)
        minutes = pd.date_range("2026-10-05 09:30", periods=78, freq="5min", tz="America/New_York").append(
            pd.date_range("2026-10-06 09:30", periods=78, freq="5min", tz="America/New_York"))
        return frame(minutes, start=10.0)

    @property
    def history_metadata(self):
        day = lambda clock: pd.Timestamp(f"2026-10-07 {clock}", tz="America/New_York")  # noqa: E731
        return {"regularMarketPrice": 400.5, "fiftyTwoWeekHigh": 410.0, "fiftyTwoWeekLow": 150.0, "longName": f"{self.symbol} Inc.",
                "fullExchangeName": "NasdaqGS", "regularMarketVolume": 5000,
                "currentTradingPeriod": {"regular": {"start": day("09:30"), "end": day("16:00")}}}

    @property
    def info(self):
        self.yf.calls.append(f"{self.symbol} info")
        if self.symbol == "SPY":
            return {"quoteType": "ETF", "longName": "SPDR S&P 500 ETF Trust", "dividendRate": None, "trailingAnnualDividendRate": 5.6,
                    "beta3Year": 1.0, "country": None}
        return {"quoteType": "EQUITY", "longName": "Taiwan Semiconductor", "sector": "Technology", "country": "Taiwan", "beta": 1.2,
                "dividendRate": 3.77, "sharesOutstanding": 1e9, "trailingPE": 30.0, "trailingEps": 13.3, "averageVolume": 2e6}


class FakeYf:
    def __init__(self, missing=()):
        self.calls: list[str] = []
        self.missing, self.refusing = set(missing), False
        self.clock = "2026-10-07 04:09"  # New York's time: ten minutes into the pre-market

    def Ticker(self, symbol):  # noqa: N802 (yfinance's name)
        return FakeTicker(self, symbol)

    def screen(self, which, count):
        self.calls.append(which)
        sign = -1 if which == "day_losers" else 1
        return {"quotes": [{"symbol": f"T{i}", "shortName": f"Company {i}", "regularMarketPrice": 3.0 + i, "regularMarketChange": sign * 1.0,
                            "regularMarketChangePercent": sign * (9.0 - i), "regularMarketVolume": 1e6} for i in range(10)]}


def test_a_quote_comes_from_the_daily_bars_and_what_yahoo_says_of_the_day():
    yf = FakeYf(missing={"NOPE"})
    q = Yahoo(yf).quotes(["AAPL", "NOPE"])
    assert list(q) == ["AAPL"]  # an unknown ticker is left out
    a = q["AAPL"]
    assert a["price"] == 400.5 and a["previous_close"] == 398.0  # the close before the day's bar
    assert a["change"] == pytest.approx(2.5) and a["change_pct"] == pytest.approx(2.5 / 398 * 100)
    assert a["year_high"] == 410.0 and a["year_low"] == 150.0 and a["exchange"] == "NASDAQ" and a["name"] == "AAPL Inc."


def test_what_is_not_a_stock_is_asked_by_yahoos_symbol_and_answered_by_ours():
    yf = FakeYf()
    q = Yahoo(yf).quotes(["GCUSD", "^GSPC", "BTCUSD"])
    assert sorted(q) == ["BTCUSD", "GCUSD", "^GSPC"]
    assert sorted(c.split()[0] for c in yf.calls) == ["BTC-USD", "GC=F", "^GSPC"]


def test_one_request_per_symbol_serves_the_quote_and_the_closes():
    yf = FakeYf()
    y = Yahoo(yf)
    y.quotes(["AAPL"])
    closes = y.history("AAPL")
    y.quotes(["AAPL"])
    assert yf.calls == ["AAPL 1d"]
    assert closes[-1] == {"date": "2026-10-06", "close": 399.0} and closes[0]["date"] < closes[-1]["date"]


def test_after_a_refusal_nothing_is_asked_for_a_while():
    yf = FakeYf()
    yf.refusing = True
    y = Yahoo(yf)
    with pytest.raises(MarketUnavailable):
        y.quotes(["AAPL"])
    asked = len(yf.calls)
    yf.refusing = False
    with pytest.raises(MarketUnavailable):
        y.history("MSFT")
    assert len(yf.calls) == asked


def test_the_facts_of_a_company_and_of_a_fund():
    y = Yahoo(FakeYf())
    tsm, spy = y.profile("TSM"), y.profile("SPY")
    assert tsm["sector"] == "Technology" and tsm["country"] == "Taiwan" and tsm["is_etf"] is False and tsm["last_dividend"] == 3.77
    assert spy["is_etf"] is True and spy["last_dividend"] == 5.6 and spy["beta"] == 1.0
    assert country_name(tsm["country"]) == "Taiwan" and country_name("gb") == "United Kingdom" and country_name(None) == "Unknown"
    # With the share count known, a quote carries the market value.
    assert y.quotes(["TSM"])["TSM"]["market_cap"] == pytest.approx(400.5e9)


TREASURY = 'Date,"1 Mo","2 Yr","10 Yr"\n10/06/2026,4.06,4.79,5.27\n10/05/2026,4.05,4.84,5.31\n'


def markets(yf=None):
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=TREASURY)))
    return YahooMarkets(Yahoo(yf or FakeYf()), ttl=900, today=lambda: TODAY, client=client)


def test_the_overview_from_yahoo_and_the_treasury():
    o = markets().overview()
    assert o["sample"] is False and o["sample_sections"] == [] and o["source"] == "Yahoo Finance"
    spx = next(s for s in o["indices"] if s["symbol"] == "SPX")
    assert spx["name"] == "S&P 500" and spx["price"] == 400.5 and spx["change_pct"] == pytest.approx(2.5 / 398)
    ten = next(r for r in o["rates"] if r["symbol"] == "US10Y")
    assert ten["price"] == 5.27 and ten["change"] == pytest.approx(-0.04)
    assert len(o["sectors"]) == 11 and o["sectors"][0]["name"] == "Technology" and o["sectors"][0]["change_pct"] == pytest.approx(2.5 / 398)
    assert [m["symbol"] for m in o["movers"]["gainers"]] == ["T2", "T3", "T4", "T5", "T6", "T7"]  # nothing under $5
    assert o["movers"]["losers"][0]["change_pct"] == pytest.approx(-0.07)


def test_charts_and_a_quote_page_from_yahoo():
    m = markets()
    day = m.chart("SPX", "1D")
    assert day["interval"] == "5m" and len(day["bars"]) == 78 and day["prev_close"] == 398.0
    assert day["bars"][0]["time"] == 1791279000  # 2026-10-06 09:30 on the exchange's clock, read as UTC
    assert m.chart("AAPL", "1M")["interval"] == "1D" and len(m.chart("AAPL", "1M")["bars"]) == 22
    q = m.quote("TSM")
    assert q["price"] == 400.5 and q["pe"] == 30.0 and q["eps"] == 13.3 and q["sector"] == "Technology"
    assert q["market_cap"] and q["dividend_yield"] == pytest.approx(3.77 / 400.5) and q["return_1m"] > 0


def test_before_the_open_and_after_the_close_a_quote_says_what_the_share_last_traded_at():
    yf = FakeYf()
    m = markets(yf)
    late = m.quote("AAPL")["extended"]
    assert late["session"] == "pre" and late["price"] == 411.0 and late["at"] == "2026-10-07T04:09:00-04:00"
    assert late["change"] == pytest.approx(10.5) and late["change_pct"] == pytest.approx(10.5 / 400.5)  # against the last session's price
    assert m.quote("AAPL")["extended"] == late and yf.calls.count("AAPL 1m") == 1  # kept for a while
    yf.clock = "2026-10-07 11:00"
    assert markets(yf).quote("MSFT")["extended"] is None  # the market is open: the quote is the price
    yf.clock = "2026-10-07 17:30"
    assert markets(yf).quote("KO")["extended"]["session"] == "post"
    assert markets(yf).quote("SPX")["extended"] is None  # an index has no such hours


def test_a_part_yahoo_does_not_answer_is_sample_and_named():
    yf = FakeYf()
    yf.screen = lambda which, count: (_ for _ in ()).throw(YFRateLimitError())
    m = markets(yf)
    m._section("indices", lambda: m._instruments("index", False))  # read before Yahoo starts refusing
    o = m.overview()
    assert "movers" in o["sample_sections"] and "indices" not in o["sample_sections"]


class Down:
    def quotes(self, tickers):
        raise MarketUnavailable("down")

    history = profile = quotes


class Other:
    def quotes(self, tickers):
        return {t: {"ticker": t, "price": 1.0} for t in tickers}

    def history(self, ticker):
        return [{"date": "2026-10-06", "close": 1.0}]

    def profile(self, ticker):
        return {"sector": "Energy"}


def test_a_second_provider_answers_when_the_first_does_not():
    both = Fallback(Down(), Other())
    assert both.quotes(["XOM"])["XOM"]["price"] == 1.0 and both.history("XOM") and both.profile("XOM")["sector"] == "Energy"
    with pytest.raises(MarketUnavailable):
        Fallback(Down()).quotes(["XOM"])


def test_yahoo_is_the_provider_unless_the_environment_names_another(monkeypatch):
    monkeypatch.delenv("MARKETHUB_SAMPLE_MARKETS", raising=False)
    monkeypatch.delenv("MARKET_DATA", raising=False)
    monkeypatch.setenv("FMP_API_KEY", "")
    assert isinstance(default_market(), Yahoo) and isinstance(default_markets(default_market()), YahooMarkets)
    monkeypatch.setenv("FMP_API_KEY", "k")
    behind = default_market()
    assert isinstance(behind, Fallback) and isinstance(default_markets(behind), YahooMarkets)
    monkeypatch.setenv("MARKET_DATA", "fmp")
    assert type(default_markets(default_market())) is LiveMarkets
