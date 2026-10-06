"""My Hub beyond the totals: what the portfolio is made of, how it stands against the indices, the
sentences that read it back, the stand-in for a provider that does not answer, and sharing."""

import json
from datetime import date, timedelta

import pytest

from conftest import FakeFmp, sign_in
from markethub import dashboard, insights
from markethub.community import Community, MemoryCommunity, Refused, handle_key
from markethub.holdings import INDICES, SampleData
from markethub.market import MarketUnavailable

POSITIONS = [{"ticker": "AAPL", "shares": 10, "avg_cost": 150.0}, {"ticker": "MSFT", "shares": 5, "avg_cost": 500.0},
             {"ticker": "KO", "shares": 20, "avg_cost": None}]


class Down:
    """A provider that does not answer: the quota used up, or no key."""

    def quotes(self, tickers):
        raise MarketUnavailable("The market data quota is used up for now.")

    history = profile = quotes


def doc(positions=POSITIONS, watchlist=()):
    return {"positions": list(positions), "watchlist": list(watchlist)}


def sampled(positions=POSITIONS):
    return dashboard.build(doc(positions), Down(), SampleData())


# --- What it is made of ----------------------------------------------------------------------------


def test_the_portfolio_is_grouped_four_ways():
    d = sampled()
    groups = {g["key"]: g["items"] for g in d["groups"]}
    assert list(groups) == ["sector", "country", "volatility", "size"]
    for items in groups.values():
        assert sum(g["weight"] for g in items) == pytest.approx(1.0)
        assert sum(g["count"] for g in items) == 3
    assert {g["label"] for g in groups["sector"]} == {"Technology", "Consumer Defensive"}
    tech = next(g for g in groups["sector"] if g["label"] == "Technology")
    assert set(tech["tickers"]) == {"AAPL", "MSFT"} and tech["return_1y"] is not None and tech["day_change_pct"] is not None
    assert [g["label"] for g in groups["country"]] == ["United States"]
    # Volatility and size keep their own order, from the least to the most and from the largest down.
    assert [g["label"] for g in groups["volatility"]] == [n for n in ("Low", "Medium", "High") if n in {g["label"] for g in groups["volatility"]}]
    assert all(g["label"] in ("Mega cap", "Large cap", "Mid cap", "Small cap") for g in groups["size"])


def test_a_foreign_company_and_a_fund_have_their_own_groups():
    d = sampled([{"ticker": "ASML", "shares": 1, "avg_cost": None}, {"ticker": "SPY", "shares": 1, "avg_cost": None},
                 {"ticker": "AAPL", "shares": 1, "avg_cost": None}])
    groups = {g["key"]: {i["label"] for i in g["items"]} for g in d["groups"]}
    assert groups["country"] == {"Netherlands", "Funds", "United States"}
    assert "ETF / fund" in groups["size"] and "ETF / fund" in groups["sector"]


def test_returns_are_set_against_the_four_indices():
    d = sampled()
    periods = d["performance"]["periods"]
    assert [p["key"] for p in periods] == ["1d", "1m", "3m", "ytd", "1y"]
    assert [i["ticker"] for i in d["performance"]["indices"]] == [t for t, _ in INDICES]
    for p in periods:
        assert p["portfolio"] is not None and set(p["indices"]) == {t for t, _ in INDICES}
    assert periods[0]["portfolio"] == pytest.approx(d["totals"]["day_change_pct"])
    h = d["history"]
    assert set(h["indices"]) == {t for t, _ in INDICES} and all(len(v) == len(h["dates"]) for v in h["indices"].values())
    assert h["indices"]["SPY"] == h["benchmark_rebased"] and h["portfolio_rebased"][0] == 100.0
    # The year's return is the one the chart draws: from the last value a year back or before.
    back = (date.fromisoformat(h["dates"][-1]) - timedelta(days=365)).isoformat()
    then = [v for day, v in zip(h["dates"], h["value"]) if day <= back][-1]
    assert periods[-1]["portfolio"] == pytest.approx(h["value"][-1] / then - 1)


def test_how_much_it_moves_and_how_concentrated_it_is():
    d = sampled()
    risk = d["risk"]
    assert 0.03 < risk["volatility"] < 0.6 and -0.6 < risk["max_drawdown"] <= 0 and 0.2 < risk["up_days"] < 0.8
    assert risk["beta"] is not None and risk["best_day"]["return"] > 0 > risk["worst_day"]["return"]
    weights = sorted((p["weight"] for p in d["positions"]), reverse=True)
    assert risk["top1"] == pytest.approx(weights[0]) and risk["top3"] == pytest.approx(1.0)
    assert 1 <= risk["effective_positions"] <= 3
    assert sum(p["day_contribution"] for p in d["positions"]) == pytest.approx(d["totals"]["day_change_pct"])
    one = sampled([{"ticker": "AAPL", "shares": 1, "avg_cost": None}])
    assert one["risk"]["effective_positions"] == pytest.approx(1.0)


# --- When the provider does not answer -------------------------------------------------------------


def test_a_provider_that_does_not_answer_is_stood_in_for_and_said_so():
    d = sampled()
    assert d["sample"] is True and d["totals"]["value"] > 0 and all(p["price"] for p in d["positions"])
    assert dashboard.build(doc(), FakeFmp(), SampleData())["sample"] is False
    with pytest.raises(MarketUnavailable):
        dashboard.build(doc(), Down())
    # Never a mix: one that prices nothing is replaced whole.
    assert dashboard.build(doc(), FakeFmp(prices={"ZZZ": 1.0}), SampleData())["sample"] is True
    # The sample figures are the same from one visit to the next.
    assert sampled()["totals"]["value"] == d["totals"]["value"]


def test_the_endpoint_answers_with_sample_figures_instead_of_failing(client, market):
    sign_in(client)
    client.put("/api/portfolio", json={"positions": POSITIONS, "watchlist": []})
    market.quotes = Down().quotes
    d = client.get("/api/dashboard")
    assert d.status_code == 200 and d.json()["sample"] is True and d.json()["insights"]["items"]


# --- The sentences ---------------------------------------------------------------------------------


def test_the_code_writes_sentences_that_describe_and_do_not_advise():
    d = sampled()
    said = d["insights"]
    assert said["written"] is False and said["headline"] and len(said["items"]) >= 5
    assert {i["kind"] for i in said["items"]} <= set(insights.KINDS)
    for text in [said["headline"], *(i["text"] for i in said["items"])]:
        assert not insights.reads_as_advice(text), text
    assert dashboard.build(doc([]), Down(), SampleData())["insights"]["items"] == []


@pytest.mark.parametrize("text", ["You should trim NVDA.", "Consider diversifying into bonds.", "NVDA looks undervalued here.",
                                  "Technology will outperform next year.", "The portfolio is too concentrated.", "We recommend adding energy."])
def test_what_reads_as_advice(text):
    assert insights.reads_as_advice(text)


def test_what_the_model_is_given_has_no_amounts_and_nothing_of_the_user():
    d = sampled()
    given = json.dumps(insights.facts(d))
    for kept in ("shares", "avg_cost", "cost", "value", "pnl", "price"):
        assert f'"{kept}"' not in given
    # No figure of the portfolio's size, in any form.
    for amount in (d["totals"]["value"], d["totals"]["cost"], *(p["value"] for p in d["positions"])):
        assert str(round(amount, 2)) not in given and str(int(amount)) not in given
    assert '"ticker": "AAPL"' in given and '"weight"' in given


class FakeAnthropic:
    def __init__(self, body):
        self.body, self.calls = body, []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        text = type("Block", (), {"type": "text", "text": json.dumps(self.body)})()
        usage = type("Usage", (), {"input_tokens": 900, "output_tokens": 300})()
        return type("Response", (), {"content": [text], "usage": usage, "stop_reason": "end_turn"})()


GOOD = {"headline": "Technology is 77.6% of the portfolio.", "insights": [
    {"kind": "sector", "text": "Two positions carry most of the weight."},
    {"kind": "risk", "text": "It moved more than the index over the year."},
    {"kind": "today", "text": "AAPL accounts for most of today's move."},
    {"kind": "concentration", "text": "You should trim your largest position now."}]}


def test_the_model_reads_an_unchanged_portfolio_once_a_day_and_its_advice_is_left_out():
    api = FakeAnthropic(GOOD)
    writer = insights.InsightWriter(client=api, per_day=2)
    d = sampled()
    first = writer.read("u1", doc(), d)
    assert first["written"] is True and first["headline"] == GOOD["headline"]
    assert [i["kind"] for i in first["items"]] == ["sector", "risk", "today"]  # the fourth advised
    assert writer.read("u1", doc(), d) == first and len(api.calls) == 1
    # What was sent is the figures, and only them.
    sent = api.calls[0]["messages"][0]["content"]
    assert json.loads(sent) == insights.facts(d) and "u1" not in sent
    # A changed portfolio is read again, up to the day's limit; another user has their own.
    changed = doc([{"ticker": "AAPL", "shares": 11, "avg_cost": None}])
    assert writer.read("u1", changed, sampled(changed["positions"])) and len(api.calls) == 2
    again = doc([{"ticker": "AAPL", "shares": 12, "avg_cost": None}])
    assert writer.read("u1", again, sampled(again["positions"])) is None and len(api.calls) == 2
    assert writer.read("u2", again, sampled(again["positions"])) and len(api.calls) == 3
    assert writer.read("u3", doc([]), sampled([])) is None and len(api.calls) == 3


def test_an_answer_that_cannot_be_shown_is_not_shown():
    d = sampled()
    assert insights.InsightWriter(client=FakeAnthropic({"headline": "You should sell.", "insights": GOOD["insights"]})).read("u", doc(), d) is None
    assert insights.InsightWriter(client=FakeAnthropic({"nothing": 1})).read("u", doc(), d) is None


def test_the_insights_endpoint_gives_the_models_sentences_or_the_codes(client, writer, users, market, directory, opinion, shared):
    assert client.get("/api/insights").status_code == 401
    sign_in(client)
    client.put("/api/portfolio", json={"positions": POSITIONS, "watchlist": []})
    assert client.get("/api/insights").json()["headline"] == "Written by the model."
    assert writer.seen[0][0] == "1001"
    writer.read = lambda *a: None  # the model does not answer
    said = client.get("/api/insights").json()
    assert said["written"] is False and said["items"]


# --- Sharing, and the board ------------------------------------------------------------------------


def board_of(store=None):
    value = lambda positions: dashboard.build(doc(positions), Down(), SampleData())  # noqa: E731
    return Community(store or MemoryCommunity(), value, value)


def test_nothing_is_shared_until_its_owner_says_so_and_then_only_weights():
    c = board_of()
    mine = sampled()
    assert c.status("u1") == {"enabled": False, "handle": "", "since_utc": None}
    assert not [m for m in c.board("u1", mine)["members"] if not m["stand_in"]]
    c.share("u1", "  Quiet   Ana ", mine)
    seen = c.board("u2", sampled([{"ticker": "KO", "shares": 1, "avg_cost": None}]))
    ana = next(m for m in seen["members"] if m["handle"] == "Quiet Ana")
    assert ana["you"] is False and ana["count"] == 3 and sum(p["weight"] for p in ana["positions"]) == pytest.approx(1.0, abs=1e-3)
    shown = json.dumps(seen)
    assert "u1" not in shown and '"shares"' not in shown and '"units"' not in shown and '"value"' not in shown and '"avg_cost"' not in shown
    assert str(int(mine["totals"]["value"])) not in shown
    # What is kept lets the same mix be valued again without saying how large it is.
    kept = c.store.get("u1")
    assert {u["ticker"] for u in kept["units"]} == {"AAPL", "MSFT", "KO"} and kept["units"][0]["shares"] != 10
    c.stop("u1")
    assert c.store.get("u1") is None and c.status("u1")["enabled"] is False


@pytest.mark.parametrize("handle", ["ab", "x" * 21, "-ana", "ana!", "Admin", "market hub", "<b>ana</b>"])
def test_names_that_are_refused(handle):
    with pytest.raises(Refused):
        board_of().share("u1", handle, sampled())


def test_a_name_is_one_persons_and_an_empty_portfolio_is_not_shared():
    c = board_of()
    c.share("u1", "Quiet Ana", sampled())
    with pytest.raises(Refused, match="already"):
        c.share("u2", "quiet_ana", sampled())
    assert handle_key("Quiet Ana") == handle_key("quiet_ana")
    c.share("u1", "Quiet-Ana", sampled())  # its owner may write it another way
    with pytest.raises(Refused, match="nothing to share"):
        c.share("u3", "Nobody", sampled([]))
    c.refresh("u1", sampled([]))  # what is shared follows what is held
    assert c.store.get("u1") is None


def test_where_a_portfolio_stands_against_the_others():
    c = board_of()
    c.share("u1", "ana", sampled([{"ticker": "AAPL", "shares": 1, "avg_cost": None}]))
    c.share("u2", "ben", sampled([{"ticker": "KO", "shares": 1, "avg_cost": None}]))
    viewer = sampled([{"ticker": "MSFT", "shares": 1, "avg_cost": None}])
    seen = c.board("u3", viewer)
    real = [m for m in seen["members"] if not m["stand_in"]]
    assert seen["shared"] == 2 and len(real) == 2 and seen["you"]["sharing"] is False
    for key in ("1d", "1m", "3m", "ytd", "1y"):
        st = seen["you"]["standing"][key]
        marks = [m["performance"][key] for m in seen["members"]] + [st["return"]]
        assert st["of"] == len(marks) and st["rank"] == 1 + sum(m > st["return"] for m in marks)
        assert st["average"] == pytest.approx(sum(marks) / len(marks)) and st["above_average"] is (st["return"] > st["average"])
        assert 0 <= st["ahead_of"] <= 1
    # Someone who shares is counted once, and sees their own row marked.
    c.share("u3", "cleo", viewer)
    again = c.board("u3", viewer)
    assert again["you"]["sharing"] is True and [m["handle"] for m in again["members"] if m["you"]] == ["cleo"]
    assert again["you"]["standing"]["1y"]["of"] == seen["you"]["standing"]["1y"]["of"]
    # With nothing held there is no standing, and the board is still there.
    assert c.board("u9", sampled([]))["you"]["performance"] is None


def test_stand_ins_keep_company_only_while_the_figures_are_sample():
    c = Community(MemoryCommunity(), lambda p: dashboard.build(doc(p), FakeFmp()), lambda p: dashboard.build(doc(p), Down(), SampleData()))
    real = c.board("u1", dashboard.build(doc(), FakeFmp()))
    assert real["sample"] is False and real["members"] == [] and real["you"]["standing"]["1y"] is None
    stood = c.board("u1", sampled())
    assert stood["sample"] is True and len(stood["members"]) == 12 and all(m["stand_in"] and m["sample"] for m in stood["members"])


def test_sharing_through_the_api(client, shared, users):
    assert client.get("/api/community").status_code == 401 and client.get("/api/sharing").status_code == 401
    sign_in(client)
    assert client.put("/api/sharing", json={"enabled": True, "handle": "ana"}).status_code == 400  # nothing held yet
    client.put("/api/portfolio", json={"positions": POSITIONS[:2], "watchlist": []})
    assert client.put("/api/sharing", json={"enabled": True, "handle": "a"}).status_code == 400
    assert client.put("/api/sharing", json={"enabled": True, "handle": "ana"}, headers={"origin": "https://evil.example"}).status_code == 403
    on = client.put("/api/sharing", json={"enabled": True, "handle": "ana"}).json()
    assert on["enabled"] is True and on["handle"] == "ana" and client.get("/api/sharing").json() == on
    board = client.get("/api/community").json()
    assert [m["handle"] for m in board["members"]] == ["ana"] and board["members"][0]["you"] is True
    assert [p["key"] for p in board["periods"]] == ["1d", "1m", "3m", "ytd", "1y"] and board["indices"][0]["name"] == "S&P 500"
    assert "1001" not in json.dumps(board)
    # What is shared follows the portfolio, and ends with it.
    client.put("/api/portfolio", json={"positions": POSITIONS[:1], "watchlist": []})
    assert shared.get("1001")["count"] == 1
    client.put("/api/portfolio", json={"positions": [], "watchlist": ["KO"]})
    assert shared.get("1001") is None and users.get("1001")["shared"] is False
    # Turning it off, and deleting the account, both take it away.
    client.put("/api/portfolio", json={"positions": POSITIONS, "watchlist": []})
    client.put("/api/sharing", json={"enabled": True, "handle": "ana"})
    assert client.put("/api/sharing", json={"enabled": False}).json()["enabled"] is False and shared.get("1001") is None
    client.put("/api/sharing", json={"enabled": True, "handle": "ana"})
    client.delete("/api/me")
    assert shared.get("1001") is None
