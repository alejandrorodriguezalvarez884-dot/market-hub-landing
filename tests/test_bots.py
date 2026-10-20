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
from markethub.bots import (FORMAT, NEW_YORK, Bots, MemoryBots, Prices, Refused, activity, check, decide, describe, examples, first_session,
                            last_settled, packed, resolve, run, unpacked)
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


def test_firestore_takes_no_array_inside_an_array_so_rows_are_packed():
    doc = {"user_id": "u1", "curve": [["2026-10-19", 1.01], ["2026-10-20", 1.02]], "weights": {"AAA": 0.5}, "spec": {"filters": [{"factor": "trend"}]},
           "benchmark": [["2026-10-20", 600.5]], "universe": ["AAA", "BBB"], "empty": []}

    def nested(v):
        if isinstance(v, dict):
            return any(nested(x) for x in v.values())
        if isinstance(v, list):
            return any(isinstance(x, list) or nested(x) for x in v)
        return False

    assert nested(doc) and not nested(packed(doc))
    assert packed(doc)["curve"][0] == {"row": ["2026-10-19", 1.01]}
    assert unpacked(packed(doc)) == doc


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


def competition(day: int, hour: int = 17):
    clock, market = Clock(at(LONG[day], hour)), Market(LONG[day])
    store = MemoryBots()
    bots = Bots(store, market, lambda n: NAMES[:n], now=clock)
    return bots, store, clock, market


TREND = {"format": FORMAT, "name": "Trend", "universe": {"largest": 20}, "rebalance": "weekly",
         "filters": [{"factor": "trend", "days": 50, "min": 0}], "score": [{"factor": "momentum", "days": 63, "weight": 1}], "hold": 5}


def test_a_bot_is_measured_from_its_first_close_and_moved_on_session_by_session():
    bots, store, clock, market = competition(380, hour=11)
    bots.submit("u1", TREND, name="Ana Torres")
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
    bots.submit("u1", TREND, name="Ana Torres")
    market.upto, clock.when = LONG[383], at(LONG[383], 17)
    bots.refresh()
    assert len(store.get("u1")["curve"]) == 3
    bots.submit("u1", {**TREND, "name": "Trend two"})  # the name it showed under stays
    assert store.get("u1")["curve"] == [] and store.get("u1")["handle"] == "Ana"


def test_a_refresh_does_not_bring_back_a_bot_withdrawn_meanwhile():
    bots, store, clock, market = competition(380)
    bots.submit("u1", TREND, name="Ana Torres")
    market.upto, clock.when = LONG[381], at(LONG[381], 17)
    real = store.get
    store.get = lambda user_id: None  # withdrawn while the refresh ran
    bots.refresh()
    store.get = real
    assert store.get("u1")["curve"] == []


def test_a_bot_is_shown_under_the_first_name_of_its_account():
    bots, store, *_ = competition(380)
    key = bots.issue_key("u1", "Ana María Torres")
    assert bots.submit("u1", TREND)["handle"] == "Ana"  # the agent sends no name: it was kept with its key
    assert store.keys_of("u1")[0]["name"] == "Ana" and "Torres" not in str(store.get("u1"))
    first = store.get("u1")["public_id"]
    assert len(first) == 10 and bots.submit("u1", {**TREND, "name": "Again"})["id"] == first  # the same id for the member's bot
    assert bots.submit("u2", TREND, name="Ana López")["handle"] == "Ana"  # two players may share a first name
    assert store.get("u2")["public_id"] != first
    assert bots.submit("u3", TREND)["handle"] == "Member"  # no key, no session: a neutral name
    bots.sync_player("u1", "Anabel Ruiz")
    assert store.get("u1")["handle"] == "Anabel" and store.keys_of("u1")[0]["name"] == "Anabel"
    assert bots.who(key) == "u1"


def test_renaming_a_bot_keeps_its_record_and_is_not_the_days_change():
    bots, store, clock, market = competition(380)
    bots.submit("u1", TREND, name="Ana Torres")
    market.upto, clock.when = LONG[382], at(LONG[382], 17)
    bots.refresh()
    clock.when = at(LONG[383], 10)
    bots.edit("u1", {**TREND, "hold": 4})
    mine = bots.rename("u1", "Calm trend", "Over the average, calmly.")
    assert mine["name"] == "Calm trend" and mine["about"] == "Over the average, calmly." and mine["pending"]["bot"]["name"] == "Calm trend"
    assert mine["versions"][-1]["what"] == ["renamed from Trend"] and len(store.get("u1")["curve"]) == 2
    with pytest.raises(Refused, match="name"):
        bots.rename("u1", "x")
    market.upto, clock.when = LONG[384], at(LONG[384], 17)
    bots.refresh(force=True)
    assert store.get("u1")["spec"]["name"] == "Calm trend" and store.get("u1")["spec"]["hold"] == 4
    assert store.get("u1")["versions"][-1]["what"] == ["rules"]  # the rules changed at the close; the name already had


def test_a_bot_sent_in_before_public_ids_gets_one():
    bots, store, *_ = competition(380)
    bots.submit("u1", TREND, name="Ana Torres")
    old = store.get("u1")
    old.pop("public_id")
    store.put(old)
    assert bots.ensure_ids() == 1 and len(store.get("u1")["public_id"]) == 10 and bots.ensure_ids() == 0


def test_the_board_ranks_each_period_among_the_bots_that_ran_it():
    bots, store, clock, market = competition(300)
    bots.submit("u1", TREND, name="Early Bird")
    market.upto, clock.when = LONG[330], at(LONG[330], 17)
    bots.refresh()
    bots.submit("u2", {**TREND, "name": "Late", "hold": 10}, name="Late Comer")
    market.upto, clock.when = LONG[333], at(LONG[333], 17)
    bots.refresh(force=True)
    o = bots.overview("u2")
    rows = {r["handle"]: r for r in o["rows"]}
    assert set(rows) == {"Early", "Late"} and all("user_id" not in r for r in o["rows"])
    assert rows["Late"]["you"] and not rows["Early"]["you"]
    assert rows["Late"]["returns"]["1m"] is None and "1m" not in rows["Late"]["ranks"]
    assert rows["Early"]["ranks"]["1m"] == 1 and rows["Early"]["sessions"] == 33
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
    bots.submit("u1", TREND, name="Ana Torres")
    bots.forget("u1")
    assert bots.who(second) is None and store.get("u1") is None


# --- What a bot does, and changing it live -----------------------------------------------------


def test_each_rebalance_is_logged_with_what_it_bought_sold_raised_and_cut():
    log = []
    run(bot(hold=2, universe={"tickers": ["AAA", "BBB", "CCC"]}), ["AAA", "BBB", "CCC"], prices(), 10, 30, log=log)
    first = activity(log)[-1]
    assert first["date"] == DAYS[10] and {b["ticker"] for b in first["bought"]} == {"AAA", "BBB"} and first["sold"] == []
    assert first["turnover"] == pytest.approx(1.0) and first["cost"] == pytest.approx(BOT_COST)
    # Daily, two equal weights drift apart and are traded back: logged, but neither raised nor cut by MOVED.
    assert len(log) > 1 and all(not e["bought"] and not e["sold"] for e in activity(log)[:-1])
    sold = activity([{"date": "d", "turnover": 0.6, "cost": 0.0006, "before": {"AAA": 0.5, "BBB": 0.5}, "after": {"AAA": 0.8, "CCC": 0.2}}])[0]
    assert sold["sold"] == [{"ticker": "BBB", "weight": 0.5}] and sold["bought"] == [{"ticker": "CCC", "weight": 0.2}]
    assert sold["raised"] == [{"ticker": "AAA", "before": 0.5, "after": 0.8}] and sold["cut"] == []


def test_new_rules_keep_the_record_and_apply_from_the_next_close():
    bots, store, clock, market = competition(380)
    bots.submit("u1", TREND, name="Ana Torres")
    market.upto, clock.when = LONG[383], at(LONG[383], 17)
    bots.refresh()
    before = store.get("u1")["curve"]
    clock.when = at(LONG[384], 11)  # during the session: from its close
    mine = bots.edit("u1", {**TREND, "name": "Trend, fewer", "hold": 3})
    assert mine["name"] == "Trend" and mine["pending"]["what"] == ["rules"] and mine["pending"]["bot"]["hold"] == 3
    with pytest.raises(Refused, match="once a day"):
        bots.edit("u1", {**TREND, "hold": 4})
    market.upto, clock.when = LONG[386], at(LONG[386], 17)
    bots.refresh(force=True)
    kept = store.get("u1")
    assert kept["curve"][:3] == before and len(kept["curve"]) == 6  # the record goes on, never rewritten
    assert kept["spec"]["hold"] == 3 and "pending" not in kept and len(kept["weights"]) == 3
    assert kept["versions"] == [{"from": LONG[384], "changed_utc": mine["pending"]["changed_utc"], "what": ["rules"], "spec": kept["spec"]}]
    assert kept["log"][-1]["date"] in (LONG[384], LONG[385], LONG[386]) and any(e["date"] == LONG[384] for e in kept["log"])  # rebalanced at its close
    row = next(r for r in bots.overview("u2")["rows"] if r["handle"] == "Ana")
    assert row["changed"] == LONG[384] and "spec" not in row and "versions" not in row
    clock.when = at(LONG[387], 11)
    assert bots.edit("u1", {**TREND, "hold": 4})["pending"]["what"] == ["rules"]  # a new day, a new change


def test_a_bot_that_has_not_started_just_becomes_the_new_one():
    bots, store, clock, market = competition(380, hour=11)
    bots.submit("u1", TREND, name="Ana Torres")
    assert store.get("u1")["preview"]["as_of"] == LONG[379] and len(store.get("u1")["preview"]["weights"]) == 5
    mine = bots.edit("u1", {**TREND, "hold": 2})
    assert mine["pending"] is None and mine["bot"]["hold"] == 2 and len(mine["preview"]["weights"]) == 2
    assert "versions" not in store.get("u1") or store.get("u1")["versions"] == []


def test_pause_exclude_and_resume_apply_at_the_next_close():
    bots, store, clock, market = competition(380)
    bots.submit("u1", {**TREND, "hold": 5}, name="Ana Torres")
    market.upto, clock.when = LONG[382], at(LONG[382], 17)
    bots.refresh()
    held = max(store.get("u1")["weights"], key=store.get("u1")["weights"].get)
    clock.when = at(LONG[383], 10)
    with pytest.raises(Refused, match="not among"):
        bots.switch("u1", "exclude", "ZZZ")
    mine = bots.switch("u1", "exclude", held)
    assert mine["pending"]["what"] == [f"excluded {held}"] and held in mine["pending"]["exclude"]
    assert bots.switch("u1", "pause")["pending"]["what"] == [f"excluded {held}", "paused"]
    bots.edit("u1", {**TREND, "hold": 4})  # a switch is not the day's change of rules
    market.upto, clock.when = LONG[384], at(LONG[384], 17)
    bots.refresh(force=True)
    kept = store.get("u1")
    assert kept["paused"] and kept["weights"] == {} and held not in kept["universe"] and kept["spec"]["hold"] == 4
    assert kept["versions"][-1]["what"] == ["rules", f"excluded {held}", "paused"]
    assert kept["curve"][-1][1] == pytest.approx(kept["curve"][-2][1])  # in cash, nothing moves
    clock.when = at(LONG[385], 10)
    bots.switch("u1", "resume")
    bots.switch("u1", "include", held)
    market.upto, clock.when = LONG[386], at(LONG[386], 17)
    bots.refresh(force=True)
    kept = store.get("u1")
    assert not kept["paused"] and len(kept["weights"]) == 4 and held in kept["universe"]
    assert kept["versions"][-1]["what"] == [f"included {held}", "resumed"]


def test_a_refresh_does_not_undo_a_change_made_meanwhile():
    bots, store, clock, market = competition(380)
    bots.submit("u1", TREND, name="Ana Torres")
    market.upto, clock.when = LONG[382], at(LONG[382], 17)
    bots.refresh()
    clock.when = at(LONG[383], 17)
    market.upto = LONG[383]
    real = store.get

    def edited_meanwhile(user_id):
        doc = real(user_id)
        return {**doc, "paused": True} if doc else doc
    store.get = edited_meanwhile
    bots.refresh(force=True)
    store.get = real
    assert len(store.get("u1")["curve"]) == 2  # not kept: the next refresh does it again, on the edited bot


def test_a_preview_of_what_new_rules_would_hold():
    bots, *_ = competition(380)
    got = bots.preview({**TREND, "hold": 3})
    assert got["rules"][0] == "Looks at the 20 largest US companies." and got["holds"]["as_of"] == LONG[380]
    assert len(got["holds"]["weights"]) == 3


# --- Through the API -------------------------------------------------------------------------------

API_DAYS = sessions(700, date(2023, 11, 6))
COMPANIES = [Company(f"C{i:02d}", f"Company {i}", i + 1) for i in range(40)]


class League:
    """Bot League, as the portal asks it to move the bots on."""

    def __init__(self):
        self.asked = 0

    def __call__(self):
        self.asked += 1


@pytest.fixture
def api(users, market, opinion, shared, writer, logins, captcha, entries, reader, submissions, posts, x_posts, option_strategies, bot_store):
    clock = Clock(at(API_DAYS[-1], 18))
    league = League()
    closes = lambda tickers: {t: walk(t, API_DAYS) for t in tickers}  # noqa: E731
    app = create_app(users=users, market=market, directory=Directory(loader=lambda: list(COMPANIES)), verifier=fake_verifier,
                     client_id=CLIENT_ID, session_secret="test-secret", secure_cookies=False, opinion=opinion, community_store=shared,
                     insight_writer=writer, logins=logins, password_cost=(10, 8, 1), captcha=captcha, competition_store=entries,
                     stock_reader=reader, submissions=submissions, posts=Posts(posts), x_posts=XPosts(x_posts),
                     option_strategies=option_strategies, bot_store=bot_store, clock=clock, bot_closes=closes, bot_league=league)
    page = TestClient(app)
    page.headers.update({"origin": ORIGIN})
    # What Bot League does on the same documents: makes the key, takes the bot in, moves it on.
    app.state.clock, app.state.league = clock, league
    app.state.engine = Bots(bot_store, closes, lambda n: [c.ticker for c in COMPANIES][:n], now=clock)
    return page, TestClient(app)


BOT = {"format": FORMAT, "name": "Api bot", "universe": {"largest": 30}, "score": [{"factor": "momentum", "days": 126, "skip": 21, "weight": 1}],
       "hold": 8, "rebalance": "monthly"}
USER = "1001"  # the account sign_in() makes


def test_the_page_reads_the_bot_bot_league_took_in(api, bot_store):
    page, _ = api
    sign_in(page)
    assert page.get("/api/bots/mine").json() == {"bot": None, "key": None}
    engine = page.app.state.engine
    engine.issue_key(USER)
    engine.submit(USER, BOT, name="Ana Torres")
    board = page.get("/api/bots").json()  # the board is held a couple of minutes: read after Bot League took it in
    assert board["league"] == "https://bots.themarkethub.app"
    assert board["you"]["name"] == "Api bot" and board["rows"][0]["you"] and "user_id" not in board["rows"][0]
    assert board["key"]["created_utc"]
    assert page.get("/api/bots/mine").json()["bot"]["handle"] == "Ana"


def test_the_kit_and_the_keys_are_made_in_bot_league_now(api):
    page, agent = api
    sign_in(page)
    assert page.post("/api/bots/kit").status_code in (404, 405)
    assert page.post("/api/bots/key").status_code == 405


def test_an_old_kit_is_told_where_the_competition_went(api):
    page, agent = api
    key = page.app.state.engine.issue_key(USER)
    for method, path in (("get", "/api/bot/spec"), ("post", "/api/bot/check"), ("put", "/api/bot"), ("get", "/api/bot")):
        got = getattr(agent, method)(path, headers={"authorization": f"Bearer {key}"}, **({"json": {"bot": BOT}} if method != "get" else {}))
        assert got.status_code == 410, (method, path)  # no Origin needed: the agent sends none
        assert got.json()["moved_to"] == "https://bots.themarkethub.app" and "MARKETHUB_URL=" in got.json()["detail"]


def test_withdrawing_taking_the_key_back_and_deleting_the_account(api, bot_store):
    page, _ = api
    sign_in(page)
    engine = page.app.state.engine
    key = engine.issue_key(USER)
    engine.submit(USER, BOT, name="Ana Torres")
    assert page.delete("/api/bots/mine").json() == {"withdrawn": True} and bot_store.bots == {}
    assert page.delete("/api/bots/key").json() == {"revoked": True} and engine.who(key) is None
    key = engine.issue_key(USER)
    engine.submit(USER, BOT, name="Ana Torres")
    assert page.delete("/api/me").json() == {"deleted": True}
    assert bot_store.bots == {} and bot_store.keys == {} and engine.who(key) is None


def test_a_visit_asks_bot_league_to_move_the_bots_on(api, bot_store):
    page, _ = api
    sign_in(page)
    engine, clock, league = page.app.state.engine, page.app.state.clock, page.app.state.league
    clock.when = at(API_DAYS[-6], 12)  # sent in a week ago
    engine.submit(USER, BOT, name="Ana Torres")
    clock.when = at(API_DAYS[-1], 18)
    assert page.get("/api/bots").json()["stale"] is True
    assert page.post("/api/bots/refresh").json() == {"moved": 0, "asked": True} and league.asked == 1
    engine.refresh()  # Bot League moves it on, on the same documents
    board = page.get("/api/bots").json()
    assert board["stale"] is False and board["you"]["since"] == API_DAYS[-6] and board["you"]["sessions"] == 6
    assert page.post("/api/bots/refresh").json() == {"moved": 0} and league.asked == 1


def test_the_portal_asks_bot_league_within_the_request_and_does_not_wait(monkeypatch, users, market, opinion, shared, writer, logins, captcha,
                                                                         entries, reader, submissions, posts, x_posts, option_strategies, bot_store):
    import httpx

    import markethub.api as portal

    clock = Clock(at(API_DAYS[-6], 12))
    closes = lambda tickers: {t: walk(t, API_DAYS) for t in tickers}  # noqa: E731
    app = create_app(users=users, market=market, directory=Directory(loader=lambda: list(COMPANIES)), verifier=fake_verifier,
                     client_id=CLIENT_ID, session_secret="test-secret", secure_cookies=False, opinion=opinion, community_store=shared,
                     insight_writer=writer, logins=logins, password_cost=(10, 8, 1), captcha=captcha, competition_store=entries,
                     stock_reader=reader, submissions=submissions, posts=Posts(posts), x_posts=XPosts(x_posts),
                     option_strategies=option_strategies, bot_store=bot_store, clock=clock, bot_closes=closes)
    page = TestClient(app)
    page.headers.update({"origin": ORIGIN})
    sign_in(page)
    Bots(bot_store, closes, lambda n: [c.ticker for c in COMPANIES][:n], now=clock).submit(USER, BOT, name="Ana Torres")
    clock.when = at(API_DAYS[-1], 18)
    sent = []

    def post(url, **kw):
        sent.append(url)
        raise httpx.ReadTimeout("still moving the bots on")  # Bot League goes on with it; the portal does not wait

    monkeypatch.setattr(portal.httpx, "post", post)
    assert page.post("/api/bots/refresh").json() == {"moved": 0, "asked": True}
    assert sent == ["https://bots.themarkethub.app/api/board/refresh"]  # sent before the answer, not left to a thread
