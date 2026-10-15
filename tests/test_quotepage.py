"""The quote page beyond the price: the past against the S&P 500, a company's and a fund's facts,
and funds in the search. No network."""

from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from markethub.api import merge_found
from markethub.quotepage import company, fund, history, statements
from markethub.yahoo import Yahoo

from conftest import FakeFmp, sign_in
from test_yahoo import FakeTicker, FakeYf, markets


def days(start: str, closes: list[float]) -> list[dict]:
    d, out = date.fromisoformat(start), []
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        out.append({"time": d.isoformat(), "close": c})
        d += timedelta(days=1)
    return out


def test_calendar_years_against_the_benchmark():
    # The last days of 2024, the whole of 2025 and the first days of 2026; each year ends 10% up.
    weekdays = [d["time"] for d in days("2024-12-26", [0] * 270) if d["time"] <= "2026-01-09"]
    last = {d[:4]: d for d in weekdays}
    bars = [{"time": d, "close": {"2024": 100, "2025": 110, "2026": 133.1}[d[:4]] * (1.1 if d == last[d[:4]] else 1)} for d in weekdays]
    bench = [{"time": b["time"], "close": 50.0 if b["time"] < "2025-06-01" else 55.0} for b in bars]
    h = history(bars, bench)
    y = {r["year"]: r for r in h["years"]}
    assert y[2024]["return"] == pytest.approx(0.1) and y[2024]["partial"]  # the data starts late in the year
    assert y[2025]["benchmark"] == pytest.approx(0.1) and not y[2025]["partial"]
    assert y[2025]["return"] == pytest.approx(0.1) and y[2026]["return"] == pytest.approx(133.1 * 1.1 / 121 - 1)
    assert y[2026]["partial"]  # the year is not over
    assert h["benchmark"] == "SPY" and len(h["benchmark_closes"]) == len(h["closes"]) == len(h["dates"])


def test_how_much_the_price_moved():
    closes = [100, 120, 90, 95, 130, 117]
    h = history(days("2026-01-05", closes), None)
    dd = h["risk"]["max_drawdown"]
    assert dd["depth"] == pytest.approx(90 / 120 - 1) and dd["peak"] == "2026-01-06" and dd["trough"] == "2026-01-07"
    assert h["risk"]["best_day"]["return"] == pytest.approx(130 / 95 - 1) and h["risk"]["worst_day"]["return"] == pytest.approx(-0.25)
    assert h["risk"]["volatility_1y"] is None  # too few days to say
    assert h["benchmark"] is None and h["benchmark_closes"] is None and h["risk"]["beta_1y"] is None


def test_beta_is_the_move_with_the_benchmark():
    bench = [100.0]
    for i in range(300):
        bench.append(bench[-1] * (1 + (0.01 if i % 3 else -0.012)))
    stock = [100.0]
    for a, b in zip(bench, bench[1:]):
        stock.append(stock[-1] * (1 + 2 * (b / a - 1)))  # twice the benchmark's move, every day
    bars, marks = days("2025-01-06", stock), days("2025-01-06", bench)
    assert history(bars, marks)["risk"]["beta_1y"] == pytest.approx(2.0)


def test_nothing_to_say_without_prices():
    assert history([], None) is None and history(days("2026-01-05", [10]), None) is None


def test_an_income_statement_oldest_first():
    cols = [pd.Timestamp("2025-09-30"), pd.Timestamp("2024-09-30")]
    frame = pd.DataFrame({cols[0]: [400.0, 100.0, 120.0, 6.1], cols[1]: [380.0, 90.0, 110.0, float("nan")]},
                         index=["Total Revenue", "Net Income", "Operating Income", "Diluted EPS"])
    s = statements(frame)
    assert [p["end"] for p in s] == ["2024-09-30", "2025-09-30"]
    assert s[1] == {"end": "2025-09-30", "revenue": 400.0, "gross_profit": None, "operating_income": 120.0, "net_income": 100.0, "eps": 6.1}
    assert s[0]["eps"] is None and statements(None) == [] and statements(pd.DataFrame()) == []


def test_a_companys_facts_in_the_pages_units():
    c = company({"longBusinessSummary": "Makes things.", "trailingPE": 30.5, "debtToEquity": 150.0, "fiveYearAvgDividendYield": 0.6,
                 "exDividendDate": 1786060800, "grossMargins": 0.46, "targetMeanPrice": 300.0, "recommendationKey": "buy"})
    assert c["summary"] == "Makes things." and c["valuation"]["pe"] == 30.5 and c["profitability"]["gross_margin"] == 0.46
    assert c["health"]["debt_to_equity"] == 1.5 and c["dividends"]["five_year_avg_yield"] == pytest.approx(0.006)
    assert c["dividends"]["ex_date"] == "2026-08-07"
    # What analysts say the price will be, or what to do with it, is not carried.
    assert "300" not in repr(c) and "buy" not in repr(c)


class FundData:
    fund_overview = {"categoryName": "Large Value", "family": "Schwab ETFs", "legalType": "Exchange Traded Fund"}
    top_holdings = pd.DataFrame({"Name": ["Texas Instruments Inc", "ASML Holding NV"], "Holding Percent": [0.046, 0.03]},
                                index=["TXN", "ASML.AS"])
    sector_weightings = {"technology": 0.16, "realestate": 0.0, "energy": 0.15, "healthcare": 0.19}
    asset_classes = {"stockPosition": 0.999, "cashPosition": 0.001, "bondPosition": 0.0}


def test_a_funds_facts():
    f = fund({"netExpenseRatio": 0.06, "totalAssets": 1.08e11, "yield": 0.0324, "ytdReturn": 21.4, "fundInceptionDate": 1319068800}, FundData())
    assert f["expense_ratio"] == pytest.approx(0.0006) and f["assets"] == 1.08e11 and f["return_ytd"] == pytest.approx(0.214)
    assert f["family"] == "Schwab ETFs" and f["category"] == "Large Value" and f["inception"] == "2011-10-20"
    assert [h["symbol"] for h in f["holdings"]] == ["TXN", None]  # a listing abroad is named, not linked
    assert f["holdings_weight"] == pytest.approx(0.076)
    assert [s["name"] for s in f["sectors"]] == ["Healthcare", "Technology", "Energy"]  # largest first, empty ones left out
    assert f["asset_mix"] == [{"name": "Stocks", "weight": 0.999}, {"name": "Cash", "weight": 0.001}]
    # The annual report's ratio comes as a fraction already.
    assert fund({"annualReportExpenseRatio": 0.0004})["expense_ratio"] == 0.0004 and fund({})["holdings"] == []


class FundTicker(FakeTicker):
    @property
    def info(self):
        self.yf.calls.append(f"{self.symbol} info")
        if self.symbol in ("SCHD", "VFIAX"):
            return {"quoteType": "ETF" if self.symbol == "SCHD" else "MUTUALFUND", "longName": f"{self.symbol} Fund", "netExpenseRatio": 0.06}
        return {"quoteType": "EQUITY", "longName": "Apple", "sector": "Technology", "trailingPE": 30.0, "sharesOutstanding": 1e9}

    @property
    def funds_data(self):
        self.yf.calls.append(f"{self.symbol} holdings")
        return FundData()

    @property
    def income_stmt(self):
        self.yf.calls.append(f"{self.symbol} statements")
        return pd.DataFrame({pd.Timestamp("2025-09-30"): [400.0, 100.0]}, index=["Total Revenue", "Net Income"])

    quarterly_income_stmt = income_stmt


class FundYf(FakeYf):
    def __init__(self, found=()):
        super().__init__()
        self.found, self.searches = list(found), []

    def Ticker(self, symbol):  # noqa: N802 (yfinance's name)
        return FundTicker(self, symbol)

    def Search(self, query, **kw):  # noqa: N802
        self.searches.append(query)
        return type("Found", (), {"quotes": self.found})()


def test_the_rest_of_a_stocks_page():
    yf = FundYf()
    m = markets(yf)
    more = m.more("AAPL")
    assert more["type"] == "stock" and more["company"]["valuation"]["pe"] == 30.0
    assert more["financials"]["annual"][0]["revenue"] == 400.0 and more["history"]["benchmark"] == "SPY"
    m.more("AAPL")
    assert yf.calls.count("AAPL info") == 1 and yf.calls.count("AAPL statements") == 2  # one read a day: yearly and quarterly
    assert m.more("SPY")["history"]["benchmark"] is None  # the benchmark is not set against itself
    assert "type" not in m.more("SPX")  # an index has no company behind it


def test_the_rest_of_a_funds_page():
    m = markets(FundYf())
    more = m.more("SCHD")
    assert more["type"] == "fund" and more["fund_type"] == "ETF" and more["fund"]["holdings"][0]["symbol"] == "TXN"
    assert m.more("VFIAX")["fund_type"] == "Mutual fund"
    q = m.quote("VFIAX")
    assert q["kind"] == "etf" and q["fund_type"] == "Mutual fund"


def test_funds_from_yahoos_search():
    yf = FundYf(found=[{"symbol": "VOO", "quoteType": "ETF", "longname": "Vanguard S&P 500 ETF"},
                       {"symbol": "VUAA.L", "quoteType": "ETF", "longname": "Vanguard S&P 500 UCITS ETF"},
                       {"symbol": "VFIAX", "quoteType": "MUTUALFUND", "shortname": "Vanguard 500 Index Admiral"},
                       {"symbol": "AAPL", "quoteType": "EQUITY", "longname": "Apple Inc."}])
    y = Yahoo(yf)
    assert y.find_funds("Vanguard  S&P") == [{"ticker": "VOO", "name": "Vanguard S&P 500 ETF", "kind": "ETF"},
                                             {"ticker": "VFIAX", "name": "Vanguard 500 Index Admiral", "kind": "Mutual fund"}]
    y.find_funds("vanguard s&p")
    assert yf.searches == ["Vanguard  S&P"]  # kept: the same words are not asked twice


def test_a_failed_search_does_not_stop_the_prices():
    yf = FundYf()
    yf.Search = lambda query, **kw: (_ for _ in ()).throw(RuntimeError("down"))
    y = Yahoo(yf)
    assert y.find_funds("vanguard") == [] and y.quotes(["AAPL"])["AAPL"]["price"] == 400.5


def test_the_search_merges_companies_and_funds():
    companies = [{"ticker": t, "name": t} for t in ("SCHW", "SCHL", "A1", "A2", "A3", "A4", "A5")]
    funds = [{"ticker": "SCHD", "name": "Schwab U.S. Dividend Equity ETF", "kind": "ETF"}]
    found = merge_found(companies, funds, "schd")
    assert found[0]["ticker"] == "SCHD" and len(found) == 8 and len({f["ticker"] for f in found}) == 8
    assert [f["ticker"] for f in merge_found(companies, funds, "sch")][5] == "SCHD"  # after five companies


class WithFunds(FakeFmp):
    """The provider with a fund it knows, and a search that finds it."""

    def profile(self, ticker):
        return super().profile(ticker) | {"is_etf": ticker in ("SPY", "SCHD")}

    def find_funds(self, query):
        return [{"ticker": "SCHD", "name": "Schwab U.S. Dividend Equity ETF", "kind": "ETF"}]


@pytest.fixture
def market():
    return WithFunds()


def test_the_rest_of_the_page_from_the_api(client: TestClient):
    more = client.get("/api/public/quote/more", params={"t": "AAPL"}).json()
    assert more["history"]["dates"] and more["history"]["benchmark"] == "SPY"
    assert client.get("/api/public/quote/more", params={"t": "../x"}).status_code == 400


def test_a_fund_the_provider_knows_is_found_and_watched(client: TestClient):
    assert client.get("/api/search", params={"q": "schd"}).json()["companies"][0] == {
        "ticker": "SCHD", "name": "Schwab U.S. Dividend Equity ETF", "kind": "ETF"}
    assert all("kind" not in f for f in client.get("/api/search", params={"q": "s"}).json()["companies"])  # one letter: no fund search
    sign_in(client)
    assert client.put("/api/portfolio", json={"positions": [], "watchlist": ["SCHD"]}).status_code == 200
    assert client.put("/api/portfolio", json={"positions": [], "watchlist": ["ZZZZ"]}).status_code == 400
