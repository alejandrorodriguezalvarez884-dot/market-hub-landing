"""The watchlist page: a stock read from its daily prices, the sentences that say it, the model
that writes them with its limits, and the endpoints. No network."""

import json
from datetime import date, timedelta

import pandas as pd
import pytest

from conftest import FakeFmp, sign_in
from markethub import watch
from markethub.holdings import SampleData
from markethub.market import MarketUnavailable
from markethub.yahoo import Yahoo, daily_bars


def series(closes, volume=1000):
    """Daily bars for a list of closes, on weekdays up to today, each with a range of 2."""
    days, d = [], date.today()
    while len(days) < len(closes):
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return [{"time": day.isoformat(), "open": c, "high": c + 1, "low": c - 1, "close": c, "volume": volume}
            for day, c in zip(reversed(days), closes)]


FLAT = series([100.0] * 320)
# A year going sideways between 99 and 101, then twenty sessions straight up.
RUN = series([100.0 + (i % 5 - 2) * 0.5 for i in range(300)] + [101.0 + 2 * i for i in range(1, 21)])
FALL = series([200.0 - 0.3 * i for i in range(320)])


class Down:
    def quotes(self, tickers):
        raise MarketUnavailable("The market data provider did not answer.")

    history = profile = quotes


# --- The figures -----------------------------------------------------------------------------------


def test_a_price_far_from_its_average_by_its_own_standard_is_extended():
    r = watch.reading(RUN, FLAT)
    ext = r["extension"]
    assert ext["state"] == "extended_above" and ext["pct"] > 0.15 and ext["ranges"] > 3
    # No gap of the sessions before was as wide as today's, and the usual ones sit around zero.
    assert ext["percentile"] == 1.0 and ext["sessions"] >= watch.GAP_SESSIONS_MIN
    assert ext["band"][0] < 0 < ext["band"][1] < 0.05 and ext["high"] == pytest.approx(ext["pct"])
    assert watch.reading(FLAT, FLAT)["extension"]["state"] == "at"
    low = watch.reading(series([100.0 + (i % 5 - 2) * 0.5 for i in range(300)] + [99.0 - 2 * i for i in range(1, 21)]), FLAT)
    assert low["extension"]["state"] == "extended_below" and low["extension"]["percentile"] == 0.0


def test_a_stock_with_little_history_is_judged_by_its_daily_range_and_one_with_less_is_not_read():
    short = watch.reading(RUN[-90:], FLAT)
    assert short["extension"]["percentile"] is None and short["extension"]["band"] is None
    assert short["extension"]["state"] == "extended_above" and short["trend"]["sma200"] is None and short["trend"]["state"] == "up"
    assert watch.reading(RUN[-40:], FLAT) is None


def test_the_trend_is_the_order_of_the_price_and_its_averages():
    up, down = watch.reading(RUN, FLAT)["trend"], watch.reading(FALL, FLAT)["trend"]
    assert up["state"] == "up" and up["sma20"] > up["sma50"] > up["sma200"] and up["slope_50"] > 0
    assert down["state"] == "down" and down["sma50"] < down["sma200"] and down["slope_200"] < 0
    # Under the 50-day average while it is still over the 200-day one.
    dip = series([100.0 + 0.5 * i for i in range(300)] + [250.0 - 3 * i for i in range(1, 11)])
    assert watch.reading(dip, FLAT)["trend"]["state"] == "pullback"
    bounce = series([300.0 - 0.5 * i for i in range(300)] + [150.0 + 3 * i for i in range(1, 11)])
    assert watch.reading(bounce, FLAT)["trend"]["state"] == "rebound"


def test_strength_is_the_gap_to_the_index_in_points_and_a_line():
    s = watch.reading(RUN, FLAT)["strength"]
    assert s["state"] == "ahead" and s["gaps"]["1m"] == pytest.approx(RUN[-1]["close"] / RUN[-22]["close"] - 1)
    assert s["gaps"]["12m"] == pytest.approx(s["returns"]["12m"]) and s["high_sessions"] == 252 and s["low_sessions"] is None
    assert s["line"][0] == 100.0 and s["line"][-1] > 135 and len(s["line"]) == watch.SPARK
    behind = watch.reading(FALL, FLAT)["strength"]
    assert behind["state"] == "behind" and behind["gaps"]["3m"] < 0 and behind["low_sessions"] == 252
    # Ahead over three months and behind over one.
    fading = series([100.0] * 260 + [100.0 + i for i in range(1, 41)] + [140.0 - 0.5 * i for i in range(1, 21)])
    assert watch.reading(fading, FLAT)["strength"]["state"] == "fading"
    # Sessions the index has no close for are left out, and with too few in common there is no gap.
    assert watch.against(RUN, FLAT[-10:]) is None


def test_momentum_range_and_volume():
    r = watch.reading(RUN, FLAT)
    assert r["momentum"]["rsi"] > 90 and r["momentum"]["returns"]["1w"] == pytest.approx(141 / 131 - 1)
    assert watch.reading(FALL, FLAT)["momentum"]["rsi"] < 10
    assert r["range"]["high"] == 142.0 and r["range"]["from_high"] == pytest.approx(141 / 142 - 1) and r["range"]["sessions_since_high"] == 0
    assert r["range"]["position"] > 0.95 and r["daily_range_pct"] == pytest.approx(3 / 141, rel=0.2)
    # Every session traded the same, and it rose on more of them than it fell.
    assert r["volume"]["week_ratio"] == pytest.approx(1.0) and r["volume"]["up_down"] > 1
    busy = [b | {"volume": 3000} if i >= len(RUN) - 6 else b for i, b in enumerate(RUN)]
    assert watch.reading(busy, FLAT)["volume"]["week_ratio"] == pytest.approx(3000 / 1200)  # against an average those five sessions are part of
    assert watch.reading(series([100.0 + i for i in range(100)], volume=0), FLAT)["volume"] is None


def test_what_analysts_estimate_as_growth():
    table = {"0q": {"growth": 0.1, "analysts": 9}, "+1q": {"growth": 0.2}, "0y": {"growth": 0.3, "analysts": 12}, "+1y": {"growth": -0.05, "analysts": 14}}
    g = watch.growth({"eps": table, "revenue": {"0y": {"growth": 0.08, "analysts": 20}}})
    assert g == {"eps": {"quarter": 0.1, "year": 0.3, "next_year": -0.05}, "revenue": {"year": 0.08}, "analysts": 20}
    assert watch.growth({}) is None and watch.growth({"eps": {"0y": {"avg": 2.0}}}) is None


# --- The page, from a provider ---------------------------------------------------------------------


def page(market=None, **kw):
    return watch.Watch(market or Down(), SampleData(), **kw)


DOC = {"positions": [{"ticker": "AAPL", "shares": 3, "avg_cost": 150.0}], "watchlist": ["NVDA", "KO", "SPY"]}


def test_the_board_reads_what_is_followed_and_what_is_held_and_says_when_figures_are_sample():
    b = page().board(DOC)
    assert b["sample"] is True and b["watchlist"] == ["NVDA", "KO", "SPY"] and b["positions"] == ["AAPL"]
    assert [i["ticker"] for i in b["items"]] == ["NVDA", "KO", "SPY", "AAPL"] and b["benchmark"]["name"] == "S&P 500"
    nvda, ko, spy, _ = b["items"]
    assert nvda["name"] == "NVIDIA Corp." and nvda["sector"] == "Technology" and nvda["kind"] == "stock"
    assert nvda["reading"]["as_of"] == b["as_of"] and len(nvda["reading"]["spark"]) == watch.SPARK
    # The sector is its fund set against the index, and the stock set against that fund.
    assert nvda["sector_strength"]["fund"] == "XLK" and set(nvda["sector_strength"]["against_market"]["gaps"]) == {"1m", "3m", "6m", "12m"}
    assert nvda["sector_strength"]["stock"]["gaps"]["3m"] == pytest.approx(
        nvda["reading"]["momentum"]["returns"]["3m"] - nvda["sector_strength"]["against_market"]["returns"]["3m"])
    assert ko["sector_strength"]["fund"] == "XLP" and ko["valuation"]["pe"] > 0
    # A fund has no sector, no earnings and no estimates, and the index's own fund is not set against itself.
    assert spy["kind"] == "fund" and spy["sector"] is None and spy["sector_strength"] is None and spy["valuation"] is None
    assert spy["reading"]["strength"] is None and spy["analysis"]["headline"] == f"{watch.EXTENSION[spy['reading']['extension']['state']]}."
    assert watch.Watch(Down(), SampleData()).board({"positions": [], "watchlist": []})["items"] == []


def test_a_provider_that_answers_is_never_mixed_with_the_sample():
    b = page(FakeFmp()).board({"positions": [], "watchlist": ["AAPL", "KO"]})
    assert b["sample"] is False and all(i["reading"] for i in b["items"])
    # It only has closes: no range within the day and no volume, and no fund for the sector.
    aapl = b["items"][0]
    assert aapl["reading"]["volume"] is None and aapl["sector"] == "Technology" and aapl["sector_strength"]["fund"] == "XLK"
    assert page(FakeFmp(), sample=True).board({"positions": [], "watchlist": ["AAPL"]})["sample"] is True


def test_the_codes_sentences_say_each_aspect_and_never_advise():
    for item in page().board(DOC)["items"]:
        said = item["analysis"]
        assert said["written"] is False and said["headline"].endswith(".") and said["contrast"] == ""
        aspects = [p["aspect"] for p in said["points"]]
        assert len(set(aspects)) == len(aspects) and set(aspects) <= set(watch.ASPECTS) and "growth" not in aspects
        assert {"extension", "trend", "momentum", "range", "volume"} <= set(aspects) and ("strength" in aspects) == (item["ticker"] != "SPY")
        assert ("sector" in aspects) == (item["kind"] == "stock")
        for text in [said["headline"], *(p["text"] for p in said["points"])]:
            assert not watch.unfit(text), text
    r = watch.reading(RUN, FLAT)
    said = watch.sentences({"ticker": "RUN", "reading": r}, {"eps": {"year": 0.124, "next_year": -0.03}, "analysts": 31})
    text = {p["aspect"]: p["text"] for p in said["points"]}
    assert said["headline"] == "Extended above its 50-day average, and ahead of the S&P 500 over three months."
    assert text["extension"].endswith(f"It stood lower against that average on 100% of the last {r['extension']['sessions']} sessions.")
    assert text["growth"] == "The consensus of 31 analysts has earnings per share 12.4% higher this fiscal year and 3.0% lower the next."
    assert text["range"] == "0.7% under its 52-week high, set 0 sessions ago." and not watch.unfit(text["growth"])
    day_after = watch.reading(RUN + series([139.0])[-1:], FLAT)  # the same day twice is enough for the count
    assert "set 1 session ago." in {p["aspect"]: p["text"] for p in watch.sentences({"ticker": "RUN", "reading": day_after})["points"]}["range"]
    assert watch.sentences({"ticker": "X", "reading": None})["points"] == []


@pytest.mark.parametrize("text", ["RSI above 70 leaves it overbought.", "A breakout over the high.", "There is room to run.",
                                  "Earnings will rise next year.", "You should wait for a pullback.", "The setup is bullish."])
def test_what_no_sentence_may_say(text):
    assert watch.unfit(text)


# --- The model -------------------------------------------------------------------------------------


class FakeAnthropic:
    def __init__(self, body):
        self.body, self.calls = body, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        text = type("Block", (), {"type": "text", "text": json.dumps(self.body)})()
        usage = type("Usage", (), {"input_tokens": 1500, "output_tokens": 350})()
        return type("Response", (), {"content": [text], "usage": usage, "stop_reason": "end_turn"})()


GOOD = {"headline": "NVDA sits above both averages while its sector trails the index.", "points": [
    {"aspect": "extension", "text": "The gap to the 50-day average is inside its usual range."},
    {"aspect": "trend", "text": "Price, 50-day and 200-day averages are in rising order."},
    {"aspect": "strength", "text": "It is ahead of the S&P 500 over every span measured."},
    {"aspect": "strength", "text": "A second sentence on the same aspect."},
    {"aspect": "momentum", "text": "RSI near 75 says it is overbought, so wait for a better entry."}],
    "contrast": "The stock leads the index while its sector's fund lags it."}


def figures(ticker="NVDA"):
    item = next(i for i in page().board({"positions": [], "watchlist": [ticker]})["items"])
    return watch.facts(item, watch.growth(SampleData().estimates(ticker)))


def test_the_model_is_sent_one_stock_and_its_figures_and_nothing_else():
    f = figures()
    sent = json.dumps(f)
    assert f["ticker"] == "NVDA" and f["sector"] == "Technology" and f["states_the_page_shows"]["extension"] in watch.EXTENSION
    assert f["analysts_consensus_growth"]["analysts"] and set(f["analysts_consensus_growth"]["earnings_per_share"]) == {"quarter", "year", "next_year"}
    assert set(f["against_sp500_in_points"]) == {"1m", "3m", "6m", "12m"} and f["price_to_earnings"]["last_12_months"] > 0
    for word in ("user", "email", "shares", "cost", "weight", "watchlist", "position"):
        assert word not in sent.replace("positions_", ""), word
    assert figures("SPY")["analysts_consensus_growth"] is None and figures("SPY")["sector"] is None


def test_a_stock_is_read_once_a_day_for_everybody_and_what_advises_is_left_out():
    api = FakeAnthropic(GOOD)
    reader = watch.StockReader(client=api, per_user=2, per_day=3)
    first = reader.read("u1", figures())
    assert first["written"] and first["headline"] == GOOD["headline"] and first["contrast"] == GOOD["contrast"]
    # One sentence per aspect, and the one that talks like a trade is not there.
    assert [p["aspect"] for p in first["points"]] == ["extension", "trend", "strength"]
    assert reader.read("u2", figures()) == first and len(api.calls) == 1  # the same reading, not a second one
    sent = api.calls[0]["messages"][0]["content"]
    assert json.loads(sent) == figures() and "u1" not in sent and api.calls[0]["system"] == watch.SYSTEM
    # A user's readings in a day have a limit, and so have everybody's together.
    assert reader.read("u1", figures("KO")) and reader.read("u1", figures("AAPL")) is None and len(api.calls) == 2
    assert reader.read("u2", figures("AAPL")) and len(api.calls) == 3
    assert reader.read("u3", figures("MSFT")) is None and len(api.calls) == 3
    assert reader.read("u3", figures("KO"))  # what was read today is still handed out


def test_an_answer_that_cannot_be_shown_is_dropped():
    read = lambda body: watch.StockReader(client=FakeAnthropic(body)).read("u", figures())  # noqa: E731
    assert read({"headline": "A good moment to buy.", "points": GOOD["points"], "contrast": ""}) is None
    assert read({"headline": "Fine.", "points": GOOD["points"][:2], "contrast": ""}) is None  # too little left
    assert read({"nothing": 1}) is None
    kept = read(GOOD | {"contrast": "It is poised to break out."})
    assert kept and kept["contrast"] == ""


def test_sample_figures_are_never_sent_to_the_model(reader):
    said = page(reader=reader).read("u1", "NVDA")
    assert said["sample"] is True and said["analysis"] is None and reader.seen == []
    assert said["growth"]["analysts"] and "growth" in {p["aspect"] for p in said["captions"]["points"]}
    real = page(FakeFmp(), reader=reader).read("u1", "AAPL")
    assert real["sample"] is False and real["analysis"]["written"] and real["growth"] is None  # this provider has no estimates
    assert reader.seen[0][0] == "u1" and reader.seen[0][1]["ticker"] == "AAPL"


# --- Yahoo -----------------------------------------------------------------------------------------


class Table:
    """A table of estimates as yfinance hands it over."""

    def __init__(self, rows):
        self.frame = pd.DataFrame.from_dict(rows, orient="index")

    def __getattr__(self, name):
        return getattr(self.frame, name)


class EstimatesTicker:
    def __init__(self, yf, symbol):
        self.yf, self.symbol = yf, symbol

    def history(self, period, interval, auto_adjust, actions):
        self.yf.calls.append(f"{self.symbol} bars")
        index = pd.bdate_range(end="2026-10-06", periods=900, tz="America/New_York")
        closes = [50.0 + i * 0.1 for i in range(len(index))]
        return pd.DataFrame({"Open": closes, "High": [c + 1 for c in closes], "Low": [c - 1 for c in closes], "Close": closes,
                             "Volume": [500] * len(index)}, index=index)

    history_metadata = {}

    @property
    def earnings_estimate(self):
        self.yf.calls.append(f"{self.symbol} estimates")
        if self.symbol == "SPY":
            return pd.DataFrame()
        return pd.DataFrame.from_dict({"0q": {"avg": 2.4, "growth": 0.9, "numberOfAnalysts": 44}, "0y": {"avg": 9.3, "growth": 0.95, "numberOfAnalysts": 51},
                                       "+1y": {"avg": 15.9, "growth": float("nan"), "numberOfAnalysts": 52}}, orient="index")

    @property
    def revenue_estimate(self):
        return None if self.symbol == "SPY" else pd.DataFrame.from_dict({"0y": {"avg": 4e11, "growth": 0.9, "numberOfAnalysts": 55}}, orient="index")


class EstimatesYf:
    def __init__(self):
        self.calls = []

    def Ticker(self, symbol):  # noqa: N802 (yfinance's name)
        return EstimatesTicker(self, symbol)


def test_yahoo_gives_three_years_of_bars_and_the_consensus_once_a_day():
    yf = EstimatesYf()
    y = Yahoo(yf)
    bars = y.bars("NVDA")
    assert len(bars) == 760 and bars[-1]["time"] == "2026-10-06" and set(bars[0]) == {"time", "open", "high", "low", "close", "volume"}
    assert daily_bars(y, "NVDA") == bars and yf.calls == ["NVDA bars"]
    e = y.estimates("NVDA")
    # A period with no growth figure is left out.
    assert e == {"eps": {"0q": {"avg": 2.4, "growth": 0.9, "analysts": 44.0}, "0y": {"avg": 9.3, "growth": 0.95, "analysts": 51.0}},
                 "revenue": {"0y": {"avg": 4e11, "growth": 0.9, "analysts": 55.0}}}
    assert watch.growth(e) == {"eps": {"quarter": 0.9, "year": 0.95}, "revenue": {"year": 0.9}, "analysts": 55}
    assert y.estimates("NVDA") == e and yf.calls.count("NVDA estimates") == 1
    assert y.estimates("SPY") == {}


def test_a_provider_with_closes_only_gives_them_as_bars():
    bars = daily_bars(FakeFmp(), "AAPL")
    assert bars[-1]["open"] == bars[-1]["high"] == bars[-1]["low"] == bars[-1]["close"] and bars[-1]["volume"] == 0
    assert bars[-1]["time"] == FakeFmp().history("AAPL")[-1]["date"]


# --- The endpoints ---------------------------------------------------------------------------------


def test_the_watchlist_endpoints_ask_for_a_session(client):
    for path in ("/api/watchlist", "/api/watchlist/stock?t=AAPL", "/api/watchlist/bars?t=AAPL", "/api/watchlist/read?t=AAPL"):
        assert client.get(path).status_code == 401, path


def test_the_board_the_bars_and_the_reading_of_a_stock(client, reader):
    sign_in(client)
    assert client.get("/api/watchlist").json()["items"] == []
    client.put("/api/portfolio", json={"positions": [{"ticker": "AAPL", "shares": 2, "avg_cost": None}], "watchlist": ["KO"]})
    b = client.get("/api/watchlist").json()
    assert b["sample"] is False and b["watchlist"] == ["KO"] and b["positions"] == ["AAPL"]
    assert [i["ticker"] for i in b["items"]] == ["KO", "AAPL"] and b["items"][0]["name"] == "Coca Cola Co"
    assert b["items"][0]["analysis"]["points"] and "shares" not in json.dumps(b)
    # A stock on neither list is read the same way; one nobody lists is not a stock.
    other = client.get("/api/watchlist/stock?t=nvda").json()
    assert other["item"]["ticker"] == "NVDA" and other["item"]["reading"]["extension"]
    assert client.get("/api/watchlist/stock?t=ZZZZ").status_code == 404
    assert client.get("/api/watchlist/stock?t=not a ticker").status_code == 400
    bars = client.get("/api/watchlist/bars?t=KO").json()
    assert len(bars["time"]) == len(bars["close"]) == len(bars["volume"]) > 200 and bars["time"][0] < bars["time"][-1]
    assert client.get("/api/watchlist/bars?t=ZZZZ").status_code == 404
    said = client.get("/api/watchlist/read?t=KO").json()
    assert said["analysis"]["headline"] == "KO, read by the model." and said["captions"]["points"] and said["growth"] is None
    assert reader.seen[0][0] == "1001" and reader.seen[0][1]["ticker"] == "KO"
    reader.read = lambda *a: None  # the model does not answer: the code's sentences stand
    assert client.get("/api/watchlist/read?t=KO").json()["analysis"] is None
