"""The public portal's sample data: shape, stability and labelling."""

import re
from datetime import date, datetime, timezone

from markethub import sample


def test_every_public_answer_is_labelled_sample(client):
    for path in ["/api/public/overview", "/api/public/chart?symbol=SPX&range=1M", "/api/public/quote?t=AAPL",
                 "/api/public/news"]:
        r = client.get(path)
        assert r.status_code == 200, (path, r.text)
        assert r.json()["sample"] is True


def test_public_endpoints_need_no_sign_in_and_check_tickers(client):
    assert client.get("/api/public/quote?t=KO").json()["name"]
    assert client.get("/api/public/quote?t=../etc").status_code == 400
    assert client.get("/api/public/chart?symbol=1ABC").status_code == 400
    assert client.get("/api/public/news?ticker=<b>").status_code == 400


def test_quote_uses_the_company_list_for_unknown_tickers(client):
    # MSFT is in the sample table; BRK-B too. NVDA is too. A ticker only in the SEC list gets its name.
    q = client.get("/api/public/quote?t=KO").json()
    assert q["name"] == "Coca-Cola Co."
    assert client.get("/api/public/quote?t=ZZZZ").json()["name"] == "ZZZZ"


def test_history_is_stable_and_grows_by_one_bar_a_day():
    monday, tuesday = date(2026, 9, 28), date(2026, 9, 29)
    a = sample.daily("SPX", today=monday)
    b = sample.daily("SPX", today=tuesday)
    assert len(b) == len(a) + 1
    assert b[-1][4] == sample.spec("SPX").level  # the last close sits at the target level
    # Shape of the path is the same: daily returns over the shared days match.
    ra = [a[i][4] / a[i - 1][4] for i in range(1, len(a))]
    rb = [b[i][4] / b[i - 1][4] for i in range(1, len(a))]
    assert max(abs(x - y) for x, y in zip(ra, rb)) < 1e-3


def test_weekends_use_the_last_trading_day():
    assert sample.trading_day(date(2026, 10, 4)) == date(2026, 10, 2)  # Sunday -> Friday


def test_chart_ranges():
    today = date(2026, 10, 2)
    one_day = sample.chart("AAPL", "1D", today=today)
    assert one_day["interval"] == "5m" and len(one_day["bars"]) == 78
    assert one_day["bars"][0]["open"] == sample.daily("AAPL", today=today)[-2][4]
    assert len(sample.chart("AAPL", "5D", today=today)["bars"]) == 5 * 13
    assert len(sample.chart("AAPL", "1M", today=today)["bars"]) == 22
    ytd = sample.chart("AAPL", "YTD", today=today)["bars"]
    assert all(b["time"].startswith("2026") for b in ytd)
    five = sample.chart("AAPL", "5Y", today=today)
    assert five["interval"] == "1W" and 250 < len(five["bars"]) < 270
    assert sample.chart("AAPL", "bogus", today=today)["range"] == "1Y"
    for b in sample.chart("AAPL", "1Y", today=today)["bars"]:
        assert b["low"] <= min(b["open"], b["close"]) and b["high"] >= max(b["open"], b["close"])


def test_overview_movers_are_sorted():
    o = sample.overview(today=date(2026, 10, 2))
    gains = [x["change_pct"] for x in o["movers"]["gainers"]]
    losses = [x["change_pct"] for x in o["movers"]["losers"]]
    assert gains == sorted(gains, reverse=True) and losses == sorted(losses)
    assert len(o["sectors"]) == 11 and len(o["tape"]) == 10


def test_news_filters_and_never_recommends():
    now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    allnews = sample.news(now=now)["items"]
    assert allnews == sorted(allnews, key=lambda n: n["published_utc"], reverse=True)
    assert {n["category"] for n in sample.news(category="Economy", now=now)["items"]} == {"Economy"}
    assert all("NVDA" in n["tickers"] for n in sample.news(ticker="NVDA", now=now)["items"])
    assert len(sample.news(ticker="ZZZZ", now=now)["items"]) == 3
    words = " ".join(f"{t} {s}" for _, t, s, _, _ in sample.HEADLINES).lower()
    for banned in ["buy", "sell", "upgrade", "downgrade", "price target", "undervalued", "overvalued", "cheap"]:
        assert not re.search(rf"\b{banned}\b", words), banned
