"""The community's monthly competition: a portfolio of single stocks, measured over one month.

Each calendar month is a competition. A member builds a portfolio for it: a few single stocks (no
funds), each with its share of the whole. It is sent in before the month starts, until the end of
the last day of the month before in New York, and can be changed until then; from then on it is
fixed. It is measured from the last close of the month before to the last close of its own month:
what the mix, bought at the start and left alone, returned on price (dividends apart). The highest
return wins the month.

What is kept of an entry is the member's account id (which never leaves the server), the name
they chose to be shown under, and the stocks with their weights. A month that is over is settled
once, from the provider's closes and never from sample figures, and its standings are kept as
they were. Deleting the account takes its entries with it; in a settled month its line stays,
without a name.

Nothing runs on a timer: a visit settles a month that has ended. The standings of the running
month are worked out from daily closes, so they are those of the last close.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock
from pathlib import Path
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from . import sample
from .community import HANDLE, RESERVED, SAMPLE_NAMES, handle_key
from .config import (COMPETITION_CACHE_SECONDS, COMPETITION_ENTRANTS, COMPETITION_PICKS_MAX, COMPETITION_PICKS_MIN,
                     COMPETITION_SETTLE_DAYS, COMPETITION_WEIGHT_MAX, COMPETITION_WEIGHT_MIN, DATA_DIR, FIRESTORE_DATABASE)
from .holdings import BENCHMARK, INDICES
from .market import EXTRA, MarketUnavailable
from .users import InvalidPortfolio, normalise_ticker

NEW_YORK = ZoneInfo("America/New_York")
MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
FUNDS = {c.ticker for c in EXTRA}
SAMPLE_MONTHS = 4  # past months the stand-ins fill while the figures are sample ones
SHOWN = 200  # lines of a month's standings sent to the page


class Refused(ValueError):
    """An entry that cannot be taken, with the reason to tell its author."""


def _iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat(timespec="seconds")


# --- Months --------------------------------------------------------------------------------------


def month_of(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def first_day(month: str) -> date:
    return date(int(month[:4]), int(month[5:]), 1)


def next_month(month: str) -> str:
    return month_of(first_day(month) + timedelta(days=32))


def prev_month(month: str) -> str:
    return month_of(first_day(month) - timedelta(days=1))


def last_day(month: str) -> date:
    return first_day(next_month(month)) - timedelta(days=1)


def label(month: str) -> str:
    return first_day(month).strftime("%B %Y")


def starts(month: str) -> datetime:
    """The moment a month begins in New York: until then its entries can be sent and changed."""
    return datetime.combine(first_day(month), clock(0, 0), NEW_YORK)


def thread(month: str) -> str:
    """The name the month's discussion is kept under (opinion.MEMBERS_ONLY)."""
    return f"competition-{month}"


# --- Stores --------------------------------------------------------------------------------------


class CompetitionStore(Protocol):
    def entries(self, month: str) -> list[dict]: ...
    def entry(self, month: str, user_id: str) -> dict | None: ...
    def put_entry(self, doc: dict) -> None: ...
    def delete_entry(self, month: str, user_id: str) -> None: ...
    def entries_by(self, user_id: str) -> list[dict]: ...
    def results(self) -> list[dict]: ...
    def put_result(self, doc: dict) -> None: ...


def _key(month: str, user_id: str) -> str:
    if not MONTH.fullmatch(month) or not re.fullmatch(r"[A-Za-z0-9_\-]{1,128}", user_id):
        raise ValueError("bad entry key")
    return f"{month}_{user_id}"


class MemoryCompetitions:
    def __init__(self):
        self.kept: dict[str, dict] = {}
        self.settled: dict[str, dict] = {}

    def entries(self, month: str) -> list[dict]:
        return [json.loads(json.dumps(e)) for e in self.kept.values() if e["month"] == month]

    def entry(self, month: str, user_id: str) -> dict | None:
        found = self.kept.get(_key(month, user_id))
        return json.loads(json.dumps(found)) if found else None

    def put_entry(self, doc: dict) -> None:
        self.kept[_key(doc["month"], doc["user_id"])] = json.loads(json.dumps(doc))

    def delete_entry(self, month: str, user_id: str) -> None:
        self.kept.pop(_key(month, user_id), None)

    def entries_by(self, user_id: str) -> list[dict]:
        return [json.loads(json.dumps(e)) for e in self.kept.values() if e["user_id"] == user_id]

    def results(self) -> list[dict]:
        return [json.loads(json.dumps(r)) for r in self.settled.values()]

    def put_result(self, doc: dict) -> None:
        self.settled[doc["month"]] = json.loads(json.dumps(doc))


class FileCompetitions:
    """For local development only: data/competitions/entries and data/competitions/results."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "competitions")
        self._lock = threading.Lock()

    def _read(self, folder: str) -> list[dict]:
        at = self.root / folder
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(at.glob("*.json"))] if at.is_dir() else []

    def _write(self, folder: str, name: str, doc: dict) -> None:
        with self._lock:
            path = self.root / folder / f"{name}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc), encoding="utf-8")

    def entries(self, month: str) -> list[dict]:
        return [e for e in self._read("entries") if e["month"] == month]

    def entry(self, month: str, user_id: str) -> dict | None:
        path = self.root / "entries" / f"{_key(month, user_id)}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def put_entry(self, doc: dict) -> None:
        self._write("entries", _key(doc["month"], doc["user_id"]), doc)

    def delete_entry(self, month: str, user_id: str) -> None:
        (self.root / "entries" / f"{_key(month, user_id)}.json").unlink(missing_ok=True)

    def entries_by(self, user_id: str) -> list[dict]:
        return [e for e in self._read("entries") if e["user_id"] == user_id]

    def results(self) -> list[dict]:
        return self._read("results")

    def put_result(self, doc: dict) -> None:
        if not MONTH.fullmatch(doc["month"]):
            raise ValueError("bad month")
        self._write("results", doc["month"], doc)


class FirestoreCompetitions:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        client = firestore.Client(database=database)
        self.where = lambda field, value: FieldFilter(field, "==", value)
        self.kept = client.collection("competition_entries")
        self.settled = client.collection("competition_results")

    def entries(self, month: str) -> list[dict]:
        return [s.to_dict() for s in self.kept.where(filter=self.where("month", month)).limit(COMPETITION_ENTRANTS).stream()]

    def entry(self, month: str, user_id: str) -> dict | None:
        snap = self.kept.document(_key(month, user_id)).get()
        return snap.to_dict() if snap.exists else None

    def put_entry(self, doc: dict) -> None:
        self.kept.document(_key(doc["month"], doc["user_id"])).set(doc)

    def delete_entry(self, month: str, user_id: str) -> None:
        self.kept.document(_key(month, user_id)).delete()

    def entries_by(self, user_id: str) -> list[dict]:
        return [s.to_dict() for s in self.kept.where(filter=self.where("user_id", user_id)).stream()]

    def results(self) -> list[dict]:
        return [s.to_dict() for s in self.settled.stream()]

    def put_result(self, doc: dict) -> None:
        self.settled.document(doc["month"]).set(doc)


def default_competitions() -> CompetitionStore:
    return FirestoreCompetitions() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileCompetitions()


# --- Measuring an entry --------------------------------------------------------------------------


def grid(month: str, histories: dict[str, list[dict]]) -> list[str]:
    """The sessions of a month there are closes for: the benchmark's, or failing that any stock's."""
    first, last = first_day(month).isoformat(), last_day(month).isoformat()
    days = [b["date"] for b in histories.get(BENCHMARK) or [] if first <= b["date"] <= last]
    return days or sorted({b["date"] for bars in histories.values() for b in bars if first <= b["date"] <= last})


def levels(bars: list[dict], month: str, days: list[str]) -> tuple[float | None, list[float | None]]:
    """A stock's close before the month starts, and its close on each of the month's sessions
    (the last one there is, on a day it did not trade)."""
    dates = [b["date"] for b in bars]

    def at(day: str) -> float | None:
        i = bisect_right(dates, day)
        return bars[i - 1]["close"] if i else None

    return at((first_day(month) - timedelta(days=1)).isoformat()), [at(d) for d in days]


def measure(picks: list[dict], priced: dict[str, tuple[float | None, list[float | None]]], sessions: int) -> dict:
    """What the picks returned: each one's, the whole's, and the whole's after each session. A
    stock with no close before the month starts cannot be measured; it counts as flat."""
    series, rows = [0.0] * sessions, []
    for p in picks:
        base, closes = priced.get(p["ticker"], (None, []))
        moves = [c / base - 1 if base and c else 0.0 for c in closes] if base else []
        for i, move in enumerate(moves):
            series[i] += p["weight"] * move
        rows.append({"ticker": p["ticker"], "name": p.get("name") or p["ticker"], "weight": p["weight"],
                     "return": (moves[-1] if moves else 0.0) if base else None})
    return {"return": round(series[-1], 6) if series else 0.0, "series": [round(v, 5) for v in series], "picks": rows,
            "priced": all(r["return"] is not None for r in rows)}


def standings(entries: list[dict], histories: dict[str, list[dict]], month: str) -> tuple[list[str], list[dict]]:
    """The month's sessions and its entries, the best return first (the earlier entry, on a tie)."""
    days = grid(month, histories)
    priced = {t: levels(histories.get(t) or [], month, days) for t in {p["ticker"] for e in entries for p in e["picks"]}}
    rows = [{**{k: e.get(k) for k in ("user_id", "handle", "stand_in", "updated_utc")}, **measure(e["picks"], priced, len(days))} for e in entries]
    rows.sort(key=lambda r: (-r["return"], r.get("updated_utc") or ""))
    return days, [{**r, "rank": i + 1} for i, r in enumerate(rows)]


def benchmark(histories: dict[str, list[dict]], month: str, days: list[str]) -> dict:
    base, closes = levels(histories.get(BENCHMARK) or [], month, days)
    series = [round(c / base - 1, 5) if base and c else 0.0 for c in closes] if base else []
    return {"ticker": BENCHMARK, "name": dict(INDICES)[BENCHMARK], "return": series[-1] if series else None, "series": series}


# --- Stand-ins -----------------------------------------------------------------------------------


def _stand_ins(month: str) -> list[dict]:
    """While the market data is sample data, so is the field: these are not people. Each says
    "sample", none is ever kept, and none is shown once the figures are real."""
    r = random.Random(sample._seed("competition", month))
    stocks = [s for s in sample.STOCKS if s.kind == "stock"]
    out = []
    for name in r.sample(SAMPLE_NAMES, r.randint(8, len(SAMPLE_NAMES))):
        mine = random.Random(sample._seed("competition", month, name))
        chosen = mine.sample(stocks, mine.randint(COMPETITION_PICKS_MIN, 7))
        shares = [COMPETITION_WEIGHT_MIN] * len(chosen)
        while sum(shares) < 100:  # the rest is dealt five points at a time
            i = mine.randrange(len(chosen))
            if shares[i] + 5 <= COMPETITION_WEIGHT_MAX:
                shares[i] += 5
        out.append({"month": month, "user_id": "", "handle": name, "stand_in": True, "updated_utc": "",
                    "picks": [{"ticker": s.symbol, "name": s.name, "weight": w / 100} for s, w in zip(chosen, shares)]})
    return out


# --- The competition -----------------------------------------------------------------------------


class Competitions:
    def __init__(self, store: CompetitionStore, market, stand_in=None, known: Callable[[str], bool] | None = None,
                 name_of: Callable[[str], str | None] | None = None, taken: Callable[[str, str], bool] | None = None,
                 shared_name: Callable[[str], str] | None = None, sample: bool = False, now: Callable[[], datetime] | None = None):
        """``market`` gives the closes (``history``) and says what is a fund (``profile``);
        ``stand_in`` answers for it when it does not. ``known`` says whether a ticker exists,
        ``name_of`` names its company, ``taken(key, user_id)`` whether someone else already shares
        a portfolio under a name, and ``shared_name(user_id)`` the name a member shares under."""
        self.store, self.market, self.stand_in, self.sample = store, market, stand_in, sample
        self.known, self.name_of, self.taken, self.shared_name = known, name_of or (lambda t: None), taken, shared_name
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._cached: tuple[float, str, dict] | None = None
        self._lock = threading.Lock()

    def months(self) -> tuple[str, str]:
        """The month being played, and the one entries are open for."""
        current = month_of(self.now().astimezone(NEW_YORK).date())
        return current, next_month(current)

    def rules(self) -> dict:
        return {"picks_min": COMPETITION_PICKS_MIN, "picks_max": COMPETITION_PICKS_MAX,
                "weight_min": COMPETITION_WEIGHT_MIN, "weight_max": COMPETITION_WEIGHT_MAX}

    # --- Entering ---

    def _is_fund(self, ticker: str) -> bool:
        if ticker in FUNDS:
            return True
        for source in ([] if self.sample else [self.market]) + ([self.stand_in] if self.stand_in else []):
            try:
                return bool(source.profile(ticker).get("is_etf"))
            except MarketUnavailable:
                continue
        return False

    def _picks(self, picks) -> list[dict]:
        low, high = COMPETITION_PICKS_MIN, COMPETITION_PICKS_MAX
        if not isinstance(picks, list) or not low <= len(picks) <= high:
            raise Refused(f"Pick {low} to {high} stocks.")
        out, seen = [], set()
        for p in picks:
            if not isinstance(p, dict):
                raise Refused("Each pick is a ticker and its weight.")
            try:
                ticker = normalise_ticker(p.get("ticker", ""))
            except InvalidPortfolio as exc:
                raise Refused(str(exc)) from None
            weight = p.get("weight")
            if isinstance(weight, bool) or not isinstance(weight, (int, float)) or weight != int(weight):
                raise Refused(f"{ticker}: the weight is a whole number of percent.")
            if ticker in seen:
                raise Refused(f"{ticker} is in the portfolio twice.")
            seen.add(ticker)
            if self.known and not self.known(ticker):
                raise Refused(f"{ticker} is not a US-listed ticker.")
            if self._is_fund(ticker):
                raise Refused(f"{ticker} is a fund: the competition takes single stocks only.")
            if not COMPETITION_WEIGHT_MIN <= weight <= COMPETITION_WEIGHT_MAX:
                raise Refused(f"Each stock takes between {COMPETITION_WEIGHT_MIN}% and {COMPETITION_WEIGHT_MAX}% of the portfolio.")
            out.append({"ticker": ticker, "name": self.name_of(ticker) or ticker, "weight": int(weight) / 100})
        if sum(int(p["weight"]) for p in picks) != 100:
            raise Refused("The weights must add up to 100%.")
        return out

    def enter(self, user_id: str, handle: str, picks) -> dict:
        """Send in, or change, the member's entry for the month that has not started."""
        _, month = self.months()
        handle = " ".join(str(handle).split())
        if not HANDLE.fullmatch(handle):
            raise Refused("Pick a name of 3 to 20 letters, digits, spaces, hyphens or underscores.")
        key = handle_key(handle)
        if key in {handle_key(r) for r in RESERVED} or key in {handle_key(n) for n in SAMPLE_NAMES}:
            raise Refused("That name is not available.")
        others = [e for e in self.store.entries(month) if e["user_id"] != user_id]
        if any(e.get("handle_key") == key for e in others) or (self.taken and self.taken(key, user_id)):
            raise Refused("Someone else already plays under that name.")
        mine = self.store.entry(month, user_id)
        if not mine and len(others) >= COMPETITION_ENTRANTS:
            raise Refused("This month's competition is full.")
        now = _iso(self.now())
        self.store.put_entry({"month": month, "user_id": user_id, "handle": handle, "handle_key": key, "picks": self._picks(picks),
                              "created_utc": (mine or {}).get("created_utc") or now, "updated_utc": now})
        self._cached = None
        return self._entry(self.store.entry(month, user_id))

    def withdraw(self, user_id: str) -> None:
        """Take the entry back, while its month has not started."""
        self.store.delete_entry(self.months()[1], user_id)
        self._cached = None

    # --- Reading ---

    def _closes(self, tickers: set[str]) -> tuple[dict[str, list[dict]], bool]:
        """The daily closes of ``tickers`` and whether they are sample ones. From the provider; a
        stock it does not answer for has none. If it answers for nothing, all of it is sample."""
        wanted = tickers | {BENCHMARK}
        if not self.sample or not self.stand_in:
            got = self._read(self.market, wanted)
            if got.get(BENCHMARK) or not self.stand_in:
                return got, False
        return self._read(self.stand_in, wanted), True

    @staticmethod
    def _read(source, tickers: set[str]) -> dict[str, list[dict]]:
        def one(t: str) -> list[dict]:
            try:
                return source.history(t)
            except MarketUnavailable:
                return []

        wanted = sorted(tickers)
        with ThreadPoolExecutor(max_workers=8) as pool:
            return dict(zip(wanted, pool.map(one, wanted)))

    def _settle(self, month: str, entries: list[dict], histories: dict[str, list[dict]], today: date) -> dict | None:
        """The final standings of a month that ended, once its last closes are in."""
        days = grid(month, histories)
        bench = histories.get(BENCHMARK) or []
        if not days or not bench or bench[-1]["date"] <= last_day(month).isoformat():
            return None  # no close of the following month yet: the last session may still be missing
        if (today - last_day(month)).days <= COMPETITION_SETTLE_DAYS:
            for ticker in {p["ticker"] for e in entries for p in e["picks"]}:
                bars = histories.get(ticker) or []
                if not bars or bars[-1]["date"] < days[-1]:
                    return None
        _, rows = standings(entries, histories, month)
        doc = {"month": month, "start_date": (first_day(month) - timedelta(days=1)).isoformat(), "end_date": days[-1], "sessions": len(days),
               "entrants": len(rows), "benchmark": {k: v for k, v in benchmark(histories, month, days).items() if k != "series"},
               "standings": [{k: v for k, v in r.items() if k not in ("series", "stand_in", "updated_utc", "priced")} for r in rows],
               "settled_utc": _iso(self.now())}
        self.store.put_result(doc)
        return doc

    def _state(self) -> dict:
        """Everything the page shows that is the same for every member, kept for a few minutes."""
        current, open_ = self.months()
        hit = self._cached
        if hit and hit[1] == current and time.monotonic() - hit[0] < COMPETITION_CACHE_SECONDS:
            return hit[2]
        with self._lock:
            today = self.now().astimezone(NEW_YORK).date()
            results = {r["month"]: r for r in self.store.results()}
            running = self.store.entries(current)
            # A month that ended and has entries but no final standings yet: the last few are looked at.
            pending, m = {}, prev_month(current)
            for _ in range(3):
                if m not in results:
                    found = self.store.entries(m)
                    if found:
                        pending[m] = found
                m = prev_month(m)
            tickers = {p["ticker"] for e in running + [e for found in pending.values() for e in found] for p in e["picks"]}
            histories, sampled = self._closes(tickers)
            if not sampled:
                for month, found in pending.items():
                    settled = self._settle(month, found, histories, today)
                    if settled:
                        results[month] = settled
            past = [{**r, "sample": False} for r in results.values()]
            if sampled:
                # The field and its past, so the page has its shape: stand-ins, each one said to be so.
                extra = _stand_ins(current)
                months = [current]
                for _ in range(SAMPLE_MONTHS):
                    months.append(prev_month(months[-1]))
                fields = {m: _stand_ins(m) for m in months[1:] if m not in results}
                more = {p["ticker"] for e in extra + [e for f in fields.values() for e in f] for p in e["picks"]} - set(histories)
                if more:
                    histories.update(self._read(self.stand_in, more))
                running = running + extra
                for month, field in fields.items():
                    days, rows = standings(field, histories, month)
                    if days:
                        past.append({"month": month, "end_date": days[-1], "sessions": len(days), "entrants": len(rows), "sample": True,
                                     "benchmark": {k: v for k, v in benchmark(histories, month, days).items() if k != "series"},
                                     "standings": [{k: v for k, v in r.items() if k != "series"} for r in rows]})
            days, rows = standings(running, histories, current)
            state = {"sample": sampled, "current": current, "open": open_, "days": days, "standings": rows,
                     "benchmark": benchmark(histories, current, days), "partial": any(not r["priced"] for r in rows),
                     "open_entrants": len(self.store.entries(open_)), "past": sorted(past, key=lambda r: r["month"], reverse=True)}
            self._cached = (time.monotonic(), current, state)
            return state

    @staticmethod
    def _line(r: dict, user_id: str, series: bool = False) -> dict:
        """A line of some standings as members get it: never the account id."""
        out = {"rank": r["rank"], "handle": r.get("handle") or "", "you": bool(r.get("user_id")) and r.get("user_id") == user_id,
               "stand_in": bool(r.get("stand_in")), "return": r["return"], "picks": r["picks"]}
        return {**out, "series": r.get("series", [])} if series else out

    @staticmethod
    def _entry(e: dict | None) -> dict | None:
        return {"month": e["month"], "handle": e["handle"], "updated_utc": e.get("updated_utc"),
                "picks": [{"ticker": p["ticker"], "name": p.get("name") or p["ticker"], "weight": round(p["weight"] * 100)} for p in e["picks"]]} if e else None

    @staticmethod
    def _record(past: list[dict], user_id: str) -> list[dict]:
        """Every member's months: how many they played, how many they won, and their average
        return over the months they played. Most wins first, then the best average."""
        people: dict[str, dict] = {}
        for month in sorted(past, key=lambda r: r["month"]):
            for r in month["standings"]:
                who = r.get("user_id") or (f"sample:{r['handle']}" if r.get("stand_in") else "")
                if not who:
                    continue  # an account that was deleted: its line stays in its month, and no further
                p = people.setdefault(who, {"returns": [], "wins": 0, "stand_in": bool(r.get("stand_in"))})
                p["handle"], p["you"] = r["handle"], bool(r.get("user_id")) and r.get("user_id") == user_id
                p["returns"].append(r["return"])
                p["wins"] += r["rank"] == 1
        rows = [{"handle": p["handle"], "you": p["you"], "stand_in": p["stand_in"], "months": len(p["returns"]), "wins": p["wins"],
                 "average": sum(p["returns"]) / len(p["returns"]), "best": max(p["returns"])} for p in people.values()]
        rows.sort(key=lambda r: (-r["wins"], -r["average"]))
        return [{**r, "rank": i + 1} for i, r in enumerate(rows)]

    def name(self, user_id: str) -> str:
        """The name a member plays under: that of their latest entry, or the one they share their
        portfolio under. Empty when they have neither."""
        mine = sorted(self.store.entries_by(user_id), key=lambda e: e["month"], reverse=True)
        return mine[0]["handle"] if mine else (self.shared_name(user_id) if self.shared_name else "")

    def overview(self, user_id: str) -> dict:
        state = self._state()
        current, open_ = state["current"], state["open"]
        now = self.now()
        mine = next((r for r in state["standings"] if r.get("user_id") and r["user_id"] == user_id), None)
        record = self._record(state["past"], user_id)
        entry = self.store.entry(open_, user_id)
        return {
            "sample": state["sample"], "now_utc": _iso(now), "rules": self.rules(),
            "name": (entry or {}).get("handle") or (mine or {}).get("handle") or self.name(user_id),
            "running": {
                "month": current, "label": label(current), "ends": last_day(current).isoformat(), "next_starts_utc": _iso(starts(open_)),
                "start_date": (first_day(current) - timedelta(days=1)).isoformat(), "as_of": state["days"][-1] if state["days"] else None,
                "days": state["days"], "entrants": len(state["standings"]), "partial": state["partial"], "benchmark": state["benchmark"],
                "standings": [self._line(r, user_id, series=True) for r in state["standings"][:SHOWN]],
                "you": {"rank": mine["rank"], "of": len(state["standings"]), "return": mine["return"]} if mine else None,
            },
            "open": {"month": open_, "label": label(open_), "closes_utc": _iso(starts(open_)), "ends": last_day(open_).isoformat(),
                     "entrants": state["open_entrants"], "entry": self._entry(entry)},
            "history": {
                "months": [{"month": r["month"], "label": label(r["month"]), "entrants": r["entrants"], "sample": r["sample"], "benchmark": r.get("benchmark"),
                            "standings": [self._line(x, user_id) for x in r["standings"][:SHOWN]]} for r in state["past"]],
                "record": record[:SHOWN],
                "you": next((r for r in record if r["you"]), None),
            },
        }

    # --- What is kept of a member ---

    def mine(self, user_id: str) -> list[dict]:
        """A member's own entries, the newest month first: what is kept of them, for their account page."""
        return [self._entry(e) for e in sorted(self.store.entries_by(user_id), key=lambda e: e["month"], reverse=True)]

    def forget(self, user_id: str) -> None:
        """Deleting an account takes its entries with it. In a month that is settled its line
        stays where it finished, with nothing of the member on it."""
        for e in self.store.entries_by(user_id):
            self.store.delete_entry(e["month"], user_id)
        for r in self.store.results():
            if any(x.get("user_id") == user_id for x in r["standings"]):
                r["standings"] = [{**x, "user_id": "", "handle": ""} if x.get("user_id") == user_id else x for x in r["standings"]]
                self.store.put_result(r)
        self._cached = None
