"""The bot competition: what a bot file can be, how a bot is run on paper and measured from the
close after it is sent in, its key, and the routes of the page and of the member's agent."""

import io
import json
import math
import zipfile
from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from conftest import CLIENT_ID, ORIGIN, fake_verifier, sign_in
from markethub.api import create_app
from markethub.bots import (FORMAT, NEW_YORK, Bots, MemoryBots, Prices, Refused, check, decide, describe, examples, first_session,
                            last_settled, resolve, run)
from markethub.config import BOT_COST
from markethub.instagram import Posts
from markethub.market import Company, Directory
from markethub.xposts import XPosts


def sessions(n: int, first: date = date(2024, 1, 8)) -> list[str]:
    out, d = [], first
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def at(day: str, hour: int, minute: int = 0) -> datetime:
    """A moment of a session's day, in New York, as the clock gives it (UTC)."""
    return datetime.combine(date.fromisoformat(day), time(hour, minute), NEW_YORK).astimezone(timezone.utc)


def walk(ticker: str, days: list[str]) -> list[tuple[str, float]]:
    seed = sum(map(ord, ticker))
    price, out = 40.0 + seed % 60, []
    for i, d in enumerate(days):
        price *= 1 + 0.0004 * (seed % 5 - 2) + 0.012 * math.sin(i / (5 + seed % 7) + seed)
        out.append((d, round(price, 4)))
    return out


def steady(days: list[str], daily: float, start: float = 100.0) -> list[tuple[str, float]]:
    return [(d, start * (1 + daily) ** i) for i, d in enumerate(days)]


def bot(**over) -> dict:
    raw = {"format": FORMAT, "name": "Test bot", "about": "A bot for the tests.", "universe": {"tickers": ["AAA", "BBB", "CCC"]},
           "rebalance": "daily", "score": [{"factor": "momentum", "days": 5, "weight": 1}], "hold": 1}
    return check({**raw, **over})


# --- The file ------------------------------------------------------------------------------------


def test_a_file_gets_every_default_filled_in():
    b = bot()
    assert (b["filters"], b["weighting"], b["max_weight"], b["universe"]["exclude"]) == ([], "equal", 1.0, [])
    assert b["score"] == [{"factor": "momentum", "days": 5, "skip": 0, "weight": 1.0}]
    assert "market" not in b


def test_a_file_that_is_not_a_bot_is_refused_with_every_problem():
    with pytest.raises(Refused) as exc:
        check({"format": "other", "name": "x", "universe": {"largest": 5, "sector": "Tech"}, "score": [{"factor": "magic"}],
               "hold": 0, "weighting": "random", "colour": "red", "filters": [{"factor": "rsi", "days": 14}],
               "market": {"factor": "sma_cross", "fast": 50, "slow": 20, "min": 0, "cash": 2}})
    problems = " | ".join(exc.value.problems)
    for words in ('no field "colour"', '"format" is', '"name"', 'no field "sector"', "universe.largest", '"factor" is one of',
                  '"hold"', '"weighting"', 'give a "min", a "max"', '"fast" is shorter', '"market.cash"'):
        assert words in problems, words
    assert len(exc.value.problems) >= 11


@pytest.mark.parametrize("raw", examples(), ids=lambda r: r["name"])
def test_every_example_of_the_kit_is_a_bot(raw):
    b = check(raw)
    assert describe(b)[0].startswith("Looks at")


def test_the_rules_in_words():
    words = describe(check(next(r for r in examples() if r["name"] == "Trend follower")))
    assert words[0] == "Looks at the 300 largest US companies."
    assert "Keeps those where its close against its 200-session average is at least 0%." in words
    assert words[-1] == "When, for the S&P 500, its close against its 200-session average is not at least 0%, holds 100% in cash."


def test_the_universe_is_among_the_largest_companies():
    largest = lambda n: ["AAA", "BBB", "CCC", "DDD"][:n]  # noqa: E731
    assert resolve(bot(universe={"largest": 20, "exclude": ["BBB"]}), largest) == ["AAA", "CCC", "DDD"]
    with pytest.raises(Refused, match="ZZZ"):
        resolve(bot(universe={"tickers": ["AAA", "ZZZ"]}), largest)
    with pytest.raises(Refused, match='"hold" is 3'):
        resolve(bot(universe={"tickers": ["AAA", "BBB"]}, hold=3), largest)


# --- Running it ------------------------------------------------------------------------------------

DAYS = sessions(40)


def prices(**extra) -> Prices:
    closes = {"SPY": steady(DAYS, 0.001), "AAA": steady(DAYS, 0.01), "BBB": steady(DAYS, 0.0), "CCC": steady(DAYS, -0.01)}
    return Prices({**closes, **extra})


def test_it_holds_the_best_scored_and_pays_on_what_it_trades():
    curve, held, traded = run(bot(), ["AAA", "BBB", "CCC"], prices(), 10, 30)
    assert held == {"AAA": 1.0} and traded == 1.0  # bought once, then nothing to trade
    assert curve[0] == (DAYS[10], pytest.approx(1 - BOT_COST))
    assert curve[-1][1] == pytest.approx((1 - BOT_COST) * 1.01 ** 20)


def test_weights_drift_between_closes_and_a_rebalance_trades_them_back():
    b = bot(hold=2, universe={"tickers": ["AAA", "BBB"]})
    curve, held, _ = run(b, ["AAA", "BBB"], prices(), 10, 11)
    after = (1 - BOT_COST) * (0.5 * 1.01 + 0.5)
    drift = abs(0.5 - 0.505 / 1.005) + abs(0.5 - 0.5 / 1.005)
    assert curve[1][1] == pytest.approx(after * (1 - BOT_COST * drift))
    assert held == {"AAA": 0.5, "BBB": 0.5}
    weekly = bot(hold=2, universe={"tickers": ["AAA", "BBB"]}, rebalance="weekly")
    _, held, _ = run(weekly, ["AAA", "BBB"], prices(), 10, 11)  # a Monday, then a Tuesday: no rebalance
    assert held["AAA"] == pytest.approx(0.505 / 1.005)


def test_filters_caps_and_the_market_switch():
    p = prices()
    trending = bot(hold=3, filters=[{"factor": "trend", "days": 10, "min": 0}])
    assert set(decide(trending, ["AAA", "BBB", "CCC"], p, 20)) == {"AAA", "BBB"}  # BBB sits on its average, CCC under it
    capped = bot(hold=2, universe={"tickers": ["AAA", "BBB"]}, max_weight=0.4)
    assert decide(capped, ["AAA", "BBB"], p, 20) == {"AAA": 0.4, "BBB": 0.4}  # the rest in cash
    falling = Prices({"SPY": steady(DAYS, -0.005), "AAA": steady(DAYS, 0.01), "BBB": steady(DAYS, 0.0)})
    careful = bot(hold=1, market={"factor": "trend", "days": 10, "min": 0, "cash": 0.5})
    assert decide(careful, ["AAA", "BBB"], falling, 20) == {"AAA": 0.5}
    assert decide(careful, ["AAA", "BBB"], p, 20) == {"AAA": 1.0}


def test_lower_is_better_with_a_negative_weight():
    calm = bot(score=[{"factor": "momentum", "days": 5, "weight": -1}])
    assert decide(calm, ["AAA", "BBB", "CCC"], prices(), 20) == {"CCC": 1.0}


def test_a_stock_with_no_close_keeps_its_last_one():
    gappy = [(d, c) for d, c in steady(DAYS, 0.01) if d not in DAYS[15:25]]
    p = prices(AAA=gappy)
    curve, _, _ = run(bot(), ["AAA", "BBB", "CCC"], p, 10, 30)
    assert all(not math.isnan(v) for _, v in curve)


def test_a_record_starts_at_the_close_after_it_is_sent_in():
    assert DAYS[first_session(DAYS, at(DAYS[3], 11))] == DAYS[3]
    assert DAYS[first_session(DAYS, at(DAYS[3], 16, 5))] == DAYS[4]
    assert first_session(DAYS, at(DAYS[-1], 17)) is None
    assert DAYS[last_settled(DAYS, at(DAYS[-1], 15))] == DAYS[-2]  # today's bar is not a close yet
    assert DAYS[last_settled(DAYS, at(DAYS[-1], 16, 45))] == DAYS[-1]


# --- The competition ---------------------------------------------------------------------------

LONG = sessions(420)
NAMES = [f"T{i:02d}" for i in range(30)]


class Market:
    """Closes for any ticker, up to a session the test moves on."""

    def __init__(self, upto: str):
        self.upto, self.gone, self.asked = upto, set(), 0

    def __call__(self, tickers):
        self.asked += 1
        return {t: [] if t in self.gone else [(d, c) for d, c in walk(t, LONG) if d <= self.upto] for t in tickers}


class Clock:
    def __init__(self, when: datetime):
        self.when = when

    def __call__(self):
        return self.when


def competition(day: int, hour: int = 17, names=None):
    clock, market = Clock(at(LONG[day], hour)), Market(LONG[day])
    store = MemoryBots()
    bots = Bots(store, market, lambda n: NAMES[:n], member_name=names or (lambda user_id: ""), now=clock)
    return bots, store, clock, market


TREND = {"format": FORMAT, "name": "Trend", "universe": {"largest": 20}, "rebalance": "weekly",
         "filters": [{"factor": "trend", "days": 50, "min": 0}], "score": [{"factor": "momentum", "days": 63, "weight": 1}], "hold": 5}


def test_a_bot_is_measured_from_its_first_close_and_moved_on_session_by_session():
    bots, store, clock, market = competition(380, hour=11)
    bots.submit("u1", TREND, handle="ana bots")
    assert bots.mine("u1")["since"] is None and bots.mine("u1")["returns"] is None
    clock.when = at(LONG[380], 17)
    assert bots.behind() is True
    assert bots.refresh()["moved"] == 1
    assert store.get("u1")["curve"][0][0] == LONG[380] and len(store.get("u1")["curve"]) == 1
    assert bots.behind() is False and bots.refresh() == {"moved": 0}  # asked again too soon
    # Five sessions later, moved on from where it was: the same as running it in one go.
    market.upto, clock.when = LONG[385], at(LONG[385], 17)
    assert bots.refresh()["moved"] == 1
    kept = store.get("u1")
    whole, held, _ = run(check(TREND), NAMES[:20], Prices(market(set(NAMES) | {"SPY"})), 380, 385)
    assert [d for d, _ in kept["curve"]] == LONG[380:386]
    assert [v for _, v in kept["curve"]] == pytest.approx([v for _, v in whole], abs=2e-6)
    assert kept["weights"] == pytest.approx(held, abs=1e-6)
    # The record is kept: a stock the provider stops answering for does not change the past.
    past = kept["curve"]
    market.gone, market.upto, clock.when = {"T03", "T07"}, LONG[386], at(LONG[386], 17)
    bots.refresh()
    assert store.get("u1")["curve"][:6] == past and len(store.get("u1")["curve"]) == 7


def test_sending_in_another_bot_starts_the_record_again():
    bots, store, clock, market = competition(380)
    bots.submit("u1", TREND, handle="ana bots")
    market.upto, clock.when = LONG[383], at(LONG[383], 17)
    bots.refresh()
    assert len(store.get("u1")["curve"]) == 3
    bots.submit("u1", {**TREND, "name": "Trend two"})  # the name it showed under stays
    assert store.get("u1")["curve"] == [] and store.get("u1")["handle"] == "ana bots"


def test_a_refresh_does_not_bring_back_a_bot_withdrawn_meanwhile():
    bots, store, clock, market = competition(380)
    bots.submit("u1", TREND, handle="ana bots")
    market.upto, clock.when = LONG[381], at(LONG[381], 17)
    real = store.get
    store.get = lambda user_id: None  # withdrawn while the refresh ran
    bots.refresh()
    store.get = real
    assert store.get("u1")["curve"] == []


def test_the_name_a_bot_shows_under():
    bots, *_ = competition(380, names=lambda user_id: "plays already" if user_id == "u2" else "")
    with pytest.raises(Refused, match="Pick a name"):
        bots.submit("u1", TREND)
    for bad in ("x", "admin", "northwind"):
        with pytest.raises(Refused):
            bots.submit("u1", TREND, handle=bad)
    bots.submit("u1", TREND, handle="ana bots")
    with pytest.raises(Refused, match="Someone else"):
        bots.submit("u3", TREND, handle="Ana-Bots")
    assert bots.submit("u2", TREND)["handle"] == "plays already"  # the name they already show under


def test_the_board_ranks_each_period_among_the_bots_that_ran_it():
    bots, store, clock, market = competition(300)
    bots.submit("u1", TREND, handle="early bird")
    market.upto, clock.when = LONG[330], at(LONG[330], 17)
    bots.refresh()
    bots.submit("u2", {**TREND, "name": "Late", "hold": 10}, handle="late comer")
    market.upto, clock.when = LONG[333], at(LONG[333], 17)
    bots.refresh(force=True)
    o = bots.overview("u2")
    rows = {r["handle"]: r for r in o["rows"]}
    assert set(rows) == {"early bird", "late comer"} and all("user_id" not in r for r in o["rows"])
    assert rows["late comer"]["you"] and not rows["early bird"]["you"]
    assert rows["late comer"]["returns"]["1m"] is None and "1m" not in rows["late comer"]["ranks"]
    assert rows["early bird"]["ranks"]["1m"] == 1 and rows["early bird"]["sessions"] == 33
    assert {rows[h]["ranks"]["1d"] for h in rows} == {1, 2}
    assert o["benchmark"]["returns"]["1d"] is not None and o["benchmark"]["returns"]["all"] is None
    assert o["you"]["rules"][0] == "Looks at the 20 largest US companies." and o["you"]["bot"]["hold"] == 10


def test_a_backtest_is_measured_against_the_index():
    bots, *_ = competition(410)
    got = bots.backtest(TREND, 1)
    assert got["sessions"] == 252 and got["end"] == LONG[410]
    assert set(got["bot"]) >= {"total_return", "annual_return", "volatility", "max_drawdown"} and got["benchmark"]["ticker"] == "SPY"
    assert got["months"][-1]["benchmark"] is not None and len(got["notes"]) == 3
    with pytest.raises(Refused, match="years"):
        bots.backtest(TREND, 9)
    with pytest.raises(Refused, match="not enough closes"):
        competition(60)[0].backtest(TREND, 1)


def test_the_key_is_kept_hashed_and_a_new_one_replaces_it():
    bots, store, *_ = competition(380)
    key = bots.issue_key("u1")
    assert key.startswith("mhb_") and bots.who(key) == "u1"
    assert key not in json.dumps(store.keys) and store.keys_of("u1")[0]["used_utc"]
    second = bots.issue_key("u1")
    assert bots.who(key) is None and bots.who(second) == "u1"
    assert bots.who("mhb_nothing") is None and bots.who(None) is None and bots.who("other") is None
    bots.submit("u1", TREND, handle="ana bots")
    bots.forget("u1")
    assert bots.who(second) is None and store.get("u1") is None


# --- Through the API -------------------------------------------------------------------------------

API_DAYS = sessions(700, date(2023, 11, 6))
COMPANIES = [Company(f"C{i:02d}", f"Company {i}", i + 1) for i in range(40)]


@pytest.fixture
def api(users, market, opinion, shared, writer, logins, captcha, entries, reader, submissions, posts, x_posts, option_strategies, bot_store):
    clock = Clock(at(API_DAYS[-1], 18))
    app = create_app(users=users, market=market, directory=Directory(loader=lambda: list(COMPANIES)), verifier=fake_verifier,
                     client_id=CLIENT_ID, session_secret="test-secret", secure_cookies=False, opinion=opinion, community_store=shared,
                     insight_writer=writer, logins=logins, password_cost=(10, 8, 1), captcha=captcha, competition_store=entries,
                     stock_reader=reader, submissions=submissions, posts=Posts(posts), x_posts=XPosts(x_posts),
                     option_strategies=option_strategies, bot_store=bot_store, clock=clock,
                     bot_closes=lambda tickers: {t: walk(t, API_DAYS) for t in tickers})
    page = TestClient(app)
    page.headers.update({"origin": ORIGIN})
    app.state.clock = clock
    return page, TestClient(app)


BOT = {"format": FORMAT, "name": "Api bot", "universe": {"largest": 30}, "score": [{"factor": "momentum", "days": 126, "skip": 21, "weight": 1}],
       "hold": 8, "rebalance": "monthly"}


def test_the_kit_comes_with_a_key_and_the_agent_uses_it(api, bot_store):
    page, agent = api
    sign_in(page)
    assert page.get("/api/bots").json()["key"] is None
    got = page.post("/api/bots/kit")
    assert got.status_code == 200 and got.headers["content-type"] == "application/zip"
    files = zipfile.ZipFile(io.BytesIO(got.content))
    names = set(files.namelist())
    assert {"markethub-bot/AGENTS.md", "markethub-bot/CLAUDE.md", "markethub-bot/SPEC.md", "markethub-bot/tools/mh.py",
            "markethub-bot/.claude/skills/build-bot/SKILL.md", "markethub-bot/examples/momentum.json", "markethub-bot/.env"} <= names
    env = files.read("markethub-bot/.env").decode()
    assert "MARKETHUB_URL=http://testserver" in env and "{{SITE}}" not in files.read("markethub-bot/.env.example").decode()
    key = env.split("MARKETHUB_BOT_KEY=")[1].strip()
    assert page.get("/api/bots").json()["key"]["created_utc"]

    with_key = {"authorization": f"Bearer {key}"}
    assert agent.get("/api/bot/spec").json()["format"] == FORMAT
    assert agent.post("/api/bot/check", json={"bot": BOT}).status_code == 401
    ok = agent.post("/api/bot/check", json={"bot": BOT}, headers=with_key).json()
    assert ok["ok"] and ok["universe"] == 30 and ok["rules"][0] == "Looks at the 30 largest US companies."
    bad = agent.post("/api/bot/check", json={"bot": {**BOT, "hold": 99, "extra": 1}}, headers=with_key)
    assert bad.status_code == 400 and len(bad.json()["problems"]) == 2
    test = agent.post("/api/bot/backtest", json={"bot": BOT, "years": 2}, headers=with_key).json()
    assert test["sessions"] == 504 and test["holdings"]
    # No name yet anywhere in the community: the first bot needs one.
    assert "Pick a name" in agent.put("/api/bot", json={"bot": BOT}, headers=with_key).json()["detail"]
    sent = agent.put("/api/bot", json={"bot": BOT, "handle": "ana bots"}, headers=with_key).json()
    assert sent["name"] == "Api bot" and sent["handle"] == "ana bots"
    assert agent.get("/api/bot", headers=with_key).json()["bot"]["since"] is None  # it starts at the next close

    # The page sees it; the board never shows an account id.
    board = page.get("/api/bots").json()
    assert board["you"]["name"] == "Api bot" and board["rows"][0]["you"] and "user_id" not in board["rows"][0]
    assert page.get("/api/bots/mine").json()["bot"]["handle"] == "ana bots"


def test_the_agent_routes_take_the_key_and_never_the_cookie(api):
    page, agent = api
    sign_in(page)
    assert page.post("/api/bot/check", json={"bot": BOT}).status_code == 401  # signed in, but no key
    assert agent.post("/api/bots/key").status_code == 403  # the page's routes still check the Origin
    key = page.post("/api/bots/key").json()["key"]
    assert agent.get("/api/bot", headers={"authorization": f"Bearer {key}"}).status_code == 200
    newer = page.post("/api/bots/key").json()["key"]
    assert agent.get("/api/bot", headers={"authorization": f"Bearer {key}"}).status_code == 401
    assert page.delete("/api/bots/key").json() == {"revoked": True}
    assert agent.get("/api/bot", headers={"authorization": f"Bearer {newer}"}).status_code == 401


def test_withdrawing_and_deleting_the_account(api, bot_store):
    page, agent = api
    sign_in(page)
    key = page.post("/api/bots/key").json()["key"]
    agent.put("/api/bot", json={"bot": BOT, "handle": "ana bots"}, headers={"authorization": f"Bearer {key}"})
    assert page.delete("/api/bots/mine").json() == {"withdrawn": True} and bot_store.bots == {}
    agent.put("/api/bot", json={"bot": BOT, "handle": "ana bots"}, headers={"authorization": f"Bearer {key}"})
    assert page.delete("/api/me").json() == {"deleted": True}
    assert bot_store.bots == {} and bot_store.keys == {}
    assert agent.get("/api/bot", headers={"authorization": f"Bearer {key}"}).status_code == 401


def test_a_visit_moves_the_bots_on(api, bot_store):
    page, agent = api
    sign_in(page)
    key = page.post("/api/bots/key").json()["key"]
    clock = page.app.state.clock
    clock.when = at(API_DAYS[-6], 12)  # sent in a week ago
    agent.put("/api/bot", json={"bot": BOT, "handle": "ana bots"}, headers={"authorization": f"Bearer {key}"})
    clock.when = at(API_DAYS[-1], 18)
    assert page.get("/api/bots").json()["stale"] is True
    assert page.post("/api/bots/refresh").json()["moved"] == 1
    board = page.get("/api/bots").json()
    assert board["stale"] is False and board["you"]["since"] == API_DAYS[-6] and board["you"]["sessions"] == 6
    assert board["you"]["returns"]["1w"] is not None and board["as_of"] == API_DAYS[-1]
