"""The monthly competition: when an entry can be sent, what one may hold, how a month is measured
and settled, the record of the months that ended, and what is kept of a member."""

from datetime import datetime, timezone

import pytest

from conftest import sign_in
from markethub.competitions import Competitions, MemoryCompetitions, Refused, label, last_day, next_month, prev_month, thread
from markethub.holdings import SampleData
from markethub.market import MarketUnavailable

KNOWN = {"AAPL", "MSFT", "KO", "NVDA", "JPM", "SPY", "QQQ"}
PICKS = [{"ticker": "AAPL", "weight": 50}, {"ticker": "MSFT", "weight": 30}, {"ticker": "KO", "weight": 20}]
# Closes around October 2026: the last of September, three sessions of October, the first of November.
DAYS = ["2026-09-29", "2026-09-30", "2026-10-01", "2026-10-15", "2026-10-30", "2026-11-02"]
CLOSES = {
    "AAPL": [99, 100, 102, 110, 120, 90],
    "MSFT": [201, 200, 198, 190, 180, 400],
    "KO": [50, 50, 50, 51, 52, 52],
    "NVDA": [10, 10, 11, 12, 13, 13],
    "SPY": [498, 500, 505, 510, 515, 520],
}


class Clock:
    def __init__(self, at: str):
        self.at = datetime.fromisoformat(at).replace(tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.at

    def set(self, at: str) -> None:
        self.at = datetime.fromisoformat(at).replace(tzinfo=timezone.utc)


class Closes:
    """A provider with a few closes, as many of them as the test has let out so far."""

    def __init__(self, upto: str = "2026-11-02", closes=CLOSES):
        self.upto, self.closes, self.asked = upto, closes, []

    def history(self, ticker):
        self.asked.append(ticker)
        return [{"date": d, "close": float(c)} for d, c in zip(DAYS, self.closes.get(ticker, [])) if d <= self.upto]

    def profile(self, ticker):
        return {"is_etf": ticker in ("SPY", "QQQ")}


class Down:
    def history(self, ticker):
        raise MarketUnavailable("The market data quota is used up for now.")

    profile = history


def game(at="2026-09-20T12:00:00", market=None, **kw):
    clock = Clock(at)
    return Competitions(MemoryCompetitions(), market or Closes(), known=KNOWN.__contains__, now=clock, **kw), clock


# --- When ------------------------------------------------------------------------------------------


def test_months_follow_one_another():
    assert next_month("2026-12") == "2027-01" and prev_month("2027-01") == "2026-12"
    assert last_day("2026-02").isoformat() == "2026-02-28" and label("2026-11") == "November 2026" and thread("2026-11") == "competition-2026-11"


def test_entries_close_when_the_month_starts_in_new_york():
    c, clock = game("2026-10-07T12:00:00")
    assert c.months() == ("2026-10", "2026-11")
    clock.set("2026-11-01T03:59:00")  # still the 31st of October in New York
    assert c.months() == ("2026-10", "2026-11")
    clock.set("2026-11-01T04:00:00")
    assert c.months() == ("2026-11", "2026-12")


def test_an_entry_can_be_changed_until_its_month_starts_and_not_after():
    c, clock = game()
    first = c.enter("u1", "quiet hands", PICKS)
    assert first["month"] == "2026-10" and [p["weight"] for p in first["picks"]] == [50, 30, 20]
    c.enter("u1", "quiet hands", [{"ticker": "AAPL", "weight": 40}, {"ticker": "MSFT", "weight": 40}, {"ticker": "KO", "weight": 20}])
    assert [p["weight"] for p in c.store.entry("2026-10", "u1")["picks"]] == [0.4, 0.4, 0.2]
    clock.set("2026-10-05T12:00:00")  # October is being played: what is sent now is November's
    assert c.enter("u1", "quiet hands", PICKS)["month"] == "2026-11"
    assert [p["weight"] for p in c.store.entry("2026-10", "u1")["picks"]] == [0.4, 0.4, 0.2]
    c.withdraw("u1")
    assert c.store.entry("2026-11", "u1") is None and c.store.entry("2026-10", "u1")


# --- What an entry may hold ------------------------------------------------------------------------


@pytest.mark.parametrize("picks, why", [
    (PICKS[:2], "Pick 3 to 10"),
    ([{"ticker": t, "weight": 5} for t in "ABCDEFGHIJK"], "Pick 3 to 10"),
    ([{"ticker": "AAPL", "weight": 50}, {"ticker": "MSFT", "weight": 30}, {"ticker": "ZZZZ", "weight": 20}], "not a US-listed ticker"),
    ([{"ticker": "AAPL", "weight": 50}, {"ticker": "MSFT", "weight": 30}, {"ticker": "SPY", "weight": 20}], "single stocks only"),
    ([{"ticker": "AAPL", "weight": 50}, {"ticker": "MSFT", "weight": 30}, {"ticker": "QQQ", "weight": 20}], "single stocks only"),
    ([{"ticker": "AAPL", "weight": 50}, {"ticker": "aapl", "weight": 30}, {"ticker": "KO", "weight": 20}], "twice"),
    ([{"ticker": "AAPL", "weight": 60}, {"ticker": "MSFT", "weight": 20}, {"ticker": "KO", "weight": 20}], "between 5% and 50%"),
    ([{"ticker": "AAPL", "weight": 50}, {"ticker": "MSFT", "weight": 46}, {"ticker": "KO", "weight": 4}], "between 5% and 50%"),
    ([{"ticker": "AAPL", "weight": 50}, {"ticker": "MSFT", "weight": 30}, {"ticker": "KO", "weight": 10}], "add up to 100%"),
    ([{"ticker": "AAPL", "weight": 33.5}, {"ticker": "MSFT", "weight": 33.5}, {"ticker": "KO", "weight": 33}], "whole number"),
    ([{"ticker": "AAPL", "weight": "50"}, {"ticker": "MSFT", "weight": 30}, {"ticker": "KO", "weight": 20}], "whole number"),
    ("AAPL", "Pick 3 to 10"),
])
def test_entries_that_are_refused(picks, why):
    c, _ = game()
    with pytest.raises(Refused, match=why):
        c.enter("u1", "quiet hands", picks)
    assert c.store.entries("2026-10") == []


def test_a_name_is_one_players():
    c, _ = game(taken=lambda key, user_id: key == "sharedname")
    c.enter("u1", "Quiet Hands", PICKS)
    for name in ("quiet_hands", "sharedname", "admin", "northwind", "x"):  # another's, a shared one, a reserved one, a stand-in's, too short
        with pytest.raises(Refused):
            c.enter("u2", name, PICKS)
    assert c.enter("u1", "Quiet Hands", PICKS)["handle"] == "Quiet Hands"  # one's own is kept
    assert c.name("u1") == "Quiet Hands" and c.name("u2") == ""


# --- Measuring a month -----------------------------------------------------------------------------


def played(market=None, at="2026-10-16T15:00:00"):
    """October with two entries, sent in September."""
    c, clock = game(market=market or Closes(upto="2026-10-15"))
    c.enter("u1", "quiet hands", PICKS)
    c.enter("u2", "tape", [{"ticker": "NVDA", "weight": 50}, {"ticker": "KO", "weight": 25}, {"ticker": "MSFT", "weight": 25}])
    clock.set(at)
    return c, clock


def test_a_month_is_measured_from_the_last_close_before_it():
    c, _ = played()
    o = c.overview("u1")
    run = o["running"]
    assert (run["month"], run["start_date"], run["days"], run["as_of"]) == ("2026-10", "2026-09-30", ["2026-10-01", "2026-10-15"], "2026-10-15")
    assert o["sample"] is False and run["partial"] is False and run["entrants"] == 2
    tape, quiet = run["standings"]
    assert (tape["handle"], tape["rank"], tape["you"]) == ("tape", 1, False) and (quiet["rank"], quiet["you"]) == (2, True)
    # 50% of +10%, 30% of −5%, 20% of +2%: what the mix, bought at the last close of September, has done.
    assert quiet["return"] == pytest.approx(0.5 * 0.10 + 0.3 * -0.05 + 0.2 * 0.02)
    assert quiet["series"] == pytest.approx([0.5 * 0.02 + 0.3 * -0.01, quiet["return"]])
    assert [(p["ticker"], p["weight"], round(p["return"], 4)) for p in quiet["picks"]] == [("AAPL", 0.5, 0.1), ("MSFT", 0.3, -0.05), ("KO", 0.2, 0.02)]
    assert tape["return"] == pytest.approx(0.5 * 0.20 + 0.25 * 0.02 + 0.25 * -0.05)
    assert run["benchmark"]["return"] == pytest.approx(0.02) and run["you"] == {"rank": 2, "of": 2, "return": quiet["return"]}
    assert "user_id" not in str(o)  # the account id never leaves the server
    assert o["open"]["month"] == "2026-11" and o["open"]["entry"] is None and o["open"]["closes_utc"] == "2026-11-01T04:00:00+00:00"
    assert o["history"] == {"months": [], "record": [], "you": None}


def test_before_the_first_close_of_the_month_nobody_has_moved():
    c, _ = played(Closes(upto="2026-09-30"), at="2026-10-01T12:00:00")
    run = c.overview("u1")["running"]
    assert run["days"] == [] and run["as_of"] is None and [r["return"] for r in run["standings"]] == [0.0, 0.0]


def test_a_stock_with_no_close_before_the_month_counts_as_flat_and_the_page_is_told():
    c, _ = played(Closes(upto="2026-10-15", closes={k: v for k, v in CLOSES.items() if k != "NVDA"}))
    run = c.overview("u2")["running"]
    tape = next(r for r in run["standings"] if r["you"])
    assert run["partial"] is True and tape["picks"][0]["return"] is None
    assert tape["return"] == pytest.approx(0.25 * 0.02 + 0.25 * -0.05)


# --- A month that ended ----------------------------------------------------------------------------


def test_a_month_is_settled_once_and_stays_as_it_was():
    market = Closes(upto="2026-10-30")
    c, clock = played(market, at="2026-11-01T12:00:00")
    assert c.overview("u1")["history"]["months"] == []  # no close of November yet: the last session may be missing
    assert c.store.results() == []
    market.upto, c._cached = "2026-11-02", None
    clock.set("2026-11-03T12:00:00")
    o = c.overview("u1")
    [october] = o["history"]["months"]
    assert (october["label"], october["entrants"], october["sample"]) == ("October 2026", 2, False)
    assert [(r["handle"], r["rank"]) for r in october["standings"]] == [("tape", 1), ("quiet hands", 2)]
    assert october["standings"][1]["return"] == pytest.approx(0.5 * 0.20 + 0.3 * -0.10 + 0.2 * 0.04)  # to the last close of October
    assert october["benchmark"]["return"] == pytest.approx(0.03)
    kept = c.store.results()[0]
    assert kept["end_date"] == "2026-10-30" and kept["standings"][0]["user_id"] == "u2"
    assert o["running"]["month"] == "2026-11" and o["running"]["standings"] == []
    # Later prices change nothing of a month that is settled.
    market.closes = {k: [v * 3 for v in row] for k, row in CLOSES.items()}
    market.upto, c._cached = "2026-11-02", None
    assert c.overview("u1")["history"]["months"][0]["standings"][1]["return"] == october["standings"][1]["return"]
    assert len(c.store.results()) == 1


def test_the_record_counts_wins_and_averages_the_months_played():
    c, _ = played(at="2026-11-03T12:00:00")
    c.store.put_result({"month": "2026-09", "entrants": 2, "benchmark": None, "standings": [
        {"user_id": "u1", "handle": "quiet hands", "rank": 1, "return": 0.10, "picks": []},
        {"user_id": "u3", "handle": "gone", "rank": 2, "return": -0.02, "picks": []}]})
    c.market.upto = "2026-11-02"
    h = c.overview("u1")["history"]
    assert [m["month"] for m in h["months"]] == ["2026-10", "2026-09"]
    quiet = next(r for r in h["record"] if r["handle"] == "quiet hands")
    assert (quiet["months"], quiet["wins"], quiet["you"]) == (2, 1, True)
    assert quiet["average"] == pytest.approx((0.10 + 0.078) / 2) and quiet["best"] == pytest.approx(0.10)  # +10% in September, +7.8% in October
    assert [r["handle"] for r in h["record"]] == ["tape", "quiet hands", "gone"]  # most wins, then the best average
    assert h["you"]["rank"] == 2 and h["record"][0]["wins"] == 1


def test_sample_figures_never_settle_a_month_and_bring_their_own_field():
    c, clock = played(Down(), at="2026-11-03T12:00:00")
    c.stand_in = SampleData()
    o = c.overview("u1")
    assert o["sample"] is True and c.store.results() == []
    stand_ins = [r for r in o["running"]["standings"] if r["stand_in"]]
    assert len(stand_ins) >= 8 and all(not r["you"] for r in stand_ins)
    assert len(o["history"]["months"]) == 4 and all(m["sample"] for m in o["history"]["months"])
    assert all(r["stand_in"] for r in o["history"]["record"])
    # With real figures there is nobody but the members.
    c.market, c._cached = Closes(upto="2026-10-15"), None
    clock.set("2026-10-16T12:00:00")
    real = c.overview("u1")
    assert real["sample"] is False and not any(r["stand_in"] for r in real["running"]["standings"]) and real["history"]["months"] == []


def test_deleting_an_account_takes_its_entries_and_leaves_a_nameless_line():
    market = Closes()
    c, clock = played(market, at="2026-11-03T12:00:00")
    c.overview("u1")  # settles October
    c.enter("u1", "quiet hands", PICKS)  # and December's entry
    assert [e["month"] for e in c.mine("u1")] == ["2026-12", "2026-10"]
    c.forget("u1")
    assert c.mine("u1") == [] and c.store.entries_by("u1") == []
    october = c.overview("u2")["history"]
    line = october["months"][0]["standings"][1]
    assert (line["handle"], line["you"], line["rank"]) == ("", False, 2) and "u1" not in str(c.store.results())
    assert [r["handle"] for r in october["record"]] == ["tape"]


# --- Through the API -------------------------------------------------------------------------------


def test_the_competition_is_for_members(client):
    for call in (client.get("/api/competitions"), client.put("/api/competitions/entry", json={"handle": "x", "picks": []}),
                 client.get("/api/competitions/comments", params={"month": "2026-10"}), client.get("/api/competitions/mine")):
        assert call.status_code == 401


def test_entering_through_the_api(client, entries):
    sign_in(client)
    o = client.get("/api/competitions").json()
    assert o["open"]["entry"] is None and o["rules"] == {"picks_min": 3, "picks_max": 10, "weight_min": 5, "weight_max": 50} and o["name"] == ""
    month = o["open"]["month"]
    bad = client.put("/api/competitions/entry", json={"handle": "ana plays", "picks": PICKS[:2]})
    assert bad.status_code == 400 and "Pick 3 to 10" in bad.json()["detail"]
    assert client.put("/api/competitions/entry", json={"handle": "ana plays", "picks": PICKS}, headers={"origin": "https://evil.example"}).status_code == 403
    sent = client.put("/api/competitions/entry", json={"handle": "ana plays", "picks": PICKS})
    assert sent.status_code == 200 and sent.json()["month"] == month and sent.json()["picks"][0] == {"ticker": "AAPL", "name": "Apple Inc.", "weight": 50}
    o = client.get("/api/competitions").json()
    assert o["open"]["entry"]["handle"] == "ana plays" and o["open"]["entrants"] == 1 and o["name"] == "ana plays"
    assert client.get("/api/competitions/mine").json()["entries"][0]["month"] == month
    assert client.delete("/api/competitions/entry").json() == {"withdrawn": True}
    assert entries.entries(month) == []


def test_the_months_discussion_is_the_members_and_shows_the_name_played_under(client):
    sign_in(client)
    o = client.get("/api/competitions").json()
    running, month = o["running"]["month"], o["open"]["month"]
    first = client.post("/api/competitions/comments", json={"month": running, "text": "Who is in?"}).json()
    assert first["name"] == "Ana"  # no entry yet: the first name, as under an article
    client.put("/api/competitions/entry", json={"handle": "ana plays", "picks": PICKS})
    answer = client.post("/api/competitions/comments", json={"month": running, "text": "Me.", "parent_id": first["id"]}).json()
    assert (answer["name"], answer["depth"]) == ("ana plays", 1)
    got = client.get("/api/competitions/comments", params={"month": running}).json()
    assert [c["text"] for c in got["comments"]] == ["Who is in?", "Me."] and all(c["mine"] for c in got["comments"])
    assert client.get("/api/competitions/comments", params={"month": month}).json()["comments"] == []
    # Not a public thread, not an article's, and not any month.
    assert client.get("/api/public/opinion/comments", params={"slug": f"competition-{running}"}).status_code == 404
    assert client.post("/api/opinion/comments", json={"slug": f"competition-{running}", "text": "Hello"}).status_code == 400
    assert client.post("/api/competitions/comments", json={"month": "2099-01", "text": "Hello"}).status_code == 404
    assert client.post("/api/competitions/comments", json={"month": "2020-01", "text": "Hello"}).status_code == 404
    assert client.get("/api/competitions/comments", params={"month": "nope"}).status_code == 404
    # The comments are the member's own: on their account page, deleted where they stand, gone with the account.
    assert len(client.get("/api/opinion/mine").json()["comments"]) == 2
    assert client.delete(f"/api/opinion/comments/{answer['id']}").json() == {"deleted": True}


def test_deleting_the_account_through_the_api_takes_the_entry(client, entries):
    sign_in(client)
    client.put("/api/competitions/entry", json={"handle": "ana plays", "picks": PICKS})
    assert len(entries.kept) == 1
    assert client.delete("/api/me").json() == {"deleted": True}
    assert entries.kept == {}
