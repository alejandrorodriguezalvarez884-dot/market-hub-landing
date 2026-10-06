"""The news desk: what the portal shows as news, and how it stays current.

Three kinds of item:
- official documents (newsfeeds.py), written by the model from the document when there is a key
  (newswriter.py), else titled by code;
- the day's market, written by code from the figures the portal already shows;
- headlines from the press, as links.

Nothing runs on a timer. The items live in a store (Firestore on Cloud Run, a folder locally,
memory in tests) as one "front" document, so a visit is one read. A visit that finds the front
older than NEWS_TTL_SECONDS is told so (``stale``); the page then asks for a refresh, which runs
inside that request, reads the sources, writes what is new and saves the front. Every item also
goes to an archive, one document each, which nothing reads yet: it is the record the opinion
section will be written from.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from datetime import time as clock
from pathlib import Path
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from . import sample
from .config import (DATA_DIR, FIRESTORE_DATABASE, NEWS_BUDGET_SECONDS, NEWS_FIRST_RUN_HOURS, NEWS_FRONT_ITEMS,
                     NEWS_LOCK_SECONDS, NEWS_PRESS_ITEMS, NEWS_TTL_SECONDS)
from .newsfeeds import SourceDown, default_sources, item, recent, utc
from .newswriter import NewsWriter, default_writer

log = logging.getLogger("markethub.news")

CATEGORIES = ["Markets", "Economy", "Companies", "Earnings"]
NEW_YORK = ZoneInfo("America/New_York")
FRONT_CACHE_SECONDS = 20  # the front document is kept in memory this long between reads
PRESS_DAYS = 3
SEEN_IDS = 1000  # documents read and found not to be news: remembered so they are not read again


def _when(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


# --- Stores ------------------------------------------------------------------------------------


class NewsStore(Protocol):
    def front(self) -> dict | None: ...
    def save_front(self, doc: dict) -> None: ...
    def archive(self, items: list[dict]) -> None: ...


class MemoryNews:
    def __init__(self):
        self.doc: dict | None = None
        self.items: dict[str, dict] = {}

    def front(self) -> dict | None:
        return json.loads(json.dumps(self.doc)) if self.doc else None

    def save_front(self, doc: dict) -> None:
        self.doc = json.loads(json.dumps(doc))

    def archive(self, items: list[dict]) -> None:
        self.items.update({i["id"]: dict(i) for i in items})


class FileNews:
    """For local development only: data/news/front.json and one file per item."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "news")
        self._lock = threading.Lock()

    def front(self) -> dict | None:
        path = self.root / "front.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def _write(self, path: Path, doc: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        tmp.replace(path)

    def save_front(self, doc: dict) -> None:
        with self._lock:
            self._write(self.root / "front.json", doc)

    def archive(self, items: list[dict]) -> None:
        with self._lock:
            for i in items:
                if re.fullmatch(r"[A-Za-z0-9_\-]{1,80}", i["id"]):
                    self._write(self.root / "items" / f"{i['id']}.json", i)


class FirestoreNews:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore

        self.client = firestore.Client(database=database)
        self.state = self.client.collection("news_state").document("front")
        self.items = self.client.collection("news")

    def front(self) -> dict | None:
        snap = self.state.get()
        return snap.to_dict() if snap.exists else None

    def save_front(self, doc: dict) -> None:
        self.state.set(doc)

    def archive(self, items: list[dict]) -> None:
        for start in range(0, len(items), 400):  # a batch takes up to 500 writes
            batch = self.client.batch()
            for i in items[start:start + 400]:
                batch.set(self.items.document(i["id"]), i)
            batch.commit()


# --- The day's market, in words ----------------------------------------------------------------


def market_day(as_of: datetime) -> date:
    """The trading day a set of figures belongs to: before the New York open and at the weekend
    they are still the previous session's."""
    local = as_of.astimezone(NEW_YORK)
    day = local.date() - timedelta(days=1 if local.time() < clock(9, 30) else 0)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def _pct(v: float) -> str:
    return f"{abs(v) * 100:.2f}%"


def _move(v: float) -> str:
    return "little changed" if abs(v) < 0.0005 else f"{'up' if v > 0 else 'down'} {_pct(v)}"


def _signed(v: float) -> str:
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{_pct(v)}"


def _join(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def _moved(rows: list[dict]) -> list[dict]:
    return [r for r in rows if isinstance(r.get("change_pct"), (int, float))]


def market_items(overview: dict) -> list[dict]:
    """Up to three items a trading day, written from the overview: the indices, the sectors and
    the stocks that moved most. Their id carries the day, so a later refresh rewrites them with
    the newer figures instead of adding more. Sample figures are never written up as news."""
    if overview.get("sample"):
        return []
    skip = set(overview.get("sample_sections") or [])
    as_of = _when(overview["as_of"])
    day = market_day(as_of).isoformat()
    source, out = "Market Hub, from the day's figures", []

    def add(kind: str, title: str, summary: str, url: str, tickers: list[str] | None = None) -> None:
        out.append(item(f"mkt-{day}-{kind}", "market", "Markets", title, source, url, as_of, summary=summary,
                        tickers=tickers, written_by="code"))

    indices = {s["symbol"]: s for s in _moved(overview.get("indices") or [])}
    spx = indices.get("SPX")
    if spx and spx.get("price") and "indices" not in skip:
        others = [f"the {name} is {_move(indices[s]['change_pct'])}"
                  for s, name in (("NDX", "Nasdaq 100"), ("DJI", "Dow"), ("RUT", "Russell 2000")) if s in indices]
        summary = f"T{_join(others)[1:]}." if others else ""
        vix = indices.get("VIX")
        if vix and vix.get("price"):
            summary = f"{summary} The VIX is at {vix['price']:.2f}.".strip()
        add("indices", f"S&P 500 {_move(spx['change_pct'])} at {spx['price']:,.2f}", summary, "/today/",
            [s for s in ("SPX", "NDX", "DJI", "RUT") if s in indices])

    sectors = sorted(_moved(overview.get("sectors") or []), key=lambda s: s["change_pct"], reverse=True)
    if len(sectors) >= 2 and "sectors" not in skip:
        top, last = sectors[0], sectors[-1]
        higher = sum(1 for s in sectors if s["change_pct"] > 0)
        add("sectors", f"{top['name']} leads the US sectors, {_move(top['change_pct'])}; {last['name']} is last, {_move(last['change_pct'])}",
            f"{higher} of {len(sectors)} sectors are higher on the day, by the average move of each sector's stocks.", "/today/")

    movers = overview.get("movers") or {}
    gainers, losers = _moved(movers.get("gainers") or [])[:3], _moved(movers.get("losers") or [])[:3]
    if gainers and losers and "movers" not in skip:
        listed = lambda rows: "; ".join(f"{r.get('name') or r['symbol']} ({r['symbol']}) {_signed(r['change_pct'])}" for r in rows)  # noqa: E731
        add("movers", f"Largest moves among US stocks: {gainers[0]['symbol']} {_signed(gainers[0]['change_pct'])}, "
                      f"{losers[0]['symbol']} {_signed(losers[0]['change_pct'])}",
            f"Largest gains: {listed(gainers)}. Largest falls: {listed(losers)}. Stocks under $5 are left out.", "/markets/",
            [r["symbol"] for r in gainers + losers])
    return out


# --- The desk ----------------------------------------------------------------------------------


class NewsDesk:
    sample = False

    def __init__(self, store: NewsStore, sources: list[Callable[[datetime], list[dict]]], writer: NewsWriter | None = None,
                 markets=None, ttl: float = NEWS_TTL_SECONDS, budget: float = NEWS_BUDGET_SECONDS,
                 now: Callable[[], datetime] | None = None):
        self.store, self.sources, self.writer, self.markets = store, sources, writer, markets
        self.ttl, self.budget = ttl, budget
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._cached: tuple[float, dict] | None = None
        self._running = threading.Lock()

    def _front(self) -> dict:
        hit = self._cached
        if hit and time.monotonic() - hit[0] < FRONT_CACHE_SECONDS:
            return hit[1]
        front = self.store.front() or {}
        self._cached = (time.monotonic(), front)
        return front

    def _stale(self, front: dict, now: datetime) -> bool:
        at = front.get("refreshed_utc")
        return not at or (now - _when(at)).total_seconds() > self.ttl

    def news(self, category: str | None = None, tickers: set[str] | None = None, limit: int = 20,
             name: str | None = None) -> dict:
        """The items, newest first. ``press`` (the headlines) only comes with the unfiltered list."""
        front = self._front()
        items = front.get("items", [])
        if tickers:
            items = [i for i in items if tickers.intersection(i["tickers"])]
        if category in CATEGORIES:
            items = [i for i in items if i["category"] == category]
        return {"sample": False, "categories": CATEGORIES, "items": items[:limit],
                "press": [] if tickers or category else front.get("press", [])[:20],
                "refreshed_utc": front.get("refreshed_utc"), "stale": self._stale(front, self.now())}

    def refresh(self) -> dict:
        """Read the sources and save a new front, unless it is fresh or a refresh is running."""
        if not self._running.acquire(blocking=False):
            return {"refreshed": False, "reason": "running"}
        try:
            now = self.now()
            front = self.store.front() or {}
            if not self._stale(front, now):
                return {"refreshed": False, "reason": "fresh"}
            started = front.get("started_utc")
            if started and (now - _when(started)).total_seconds() < NEWS_LOCK_SECONDS:
                return {"refreshed": False, "reason": "running"}  # on another instance
            self.store.save_front({**front, "started_utc": utc(now)})
            front = self._refreshed(front, now, time.monotonic() + self.budget)
            self.store.save_front(front)
            self._cached = (time.monotonic(), front)
            return {"refreshed": True}
        finally:
            self._running.release()

    def _refreshed(self, front: dict, now: datetime, deadline: float) -> dict:
        since = _when(front["since_utc"]) if front.get("since_utc") else now - timedelta(hours=NEWS_FIRST_RUN_HOURS)
        items = {i["id"]: i for i in front.get("items", [])}
        press = {i["id"]: i for i in front.get("press", [])}
        seen = list(front.get("seen", []))
        known = set(items) | set(press) | set(seen)
        found: list[dict] = []
        for source in self.sources:
            try:
                found += source(since)
            except SourceDown as exc:
                log.warning("news source down: %s", exc)
            except Exception as exc:  # one source's surprise must not cost the others
                log.warning("news source failed: %s (%s)", type(source).__name__, type(exc).__name__)
        fresh = {i["id"]: i for i in recent(found, now) if i["id"] not in known}
        done, left = self._write(sorted(fresh.values(), key=lambda i: i["published_utc"], reverse=True), deadline)
        added = []
        for i in done:
            if i.pop("_hidden", False):
                seen.append(i["id"])
            else:
                (press if i["layer"] == "press" else items)[i["id"]] = i
                added.append(i)
        market = self._market()
        items.update({i["id"]: i for i in market})  # the day's market items are rewritten in place
        self.store.archive(added + market)
        log.info("news refresh: %d new, %d left for the next one", len(added), len(left))
        newest = lambda rows: sorted(rows, key=lambda i: i["published_utc"], reverse=True)  # noqa: E731
        return {
            "items": newest(items.values())[:NEWS_FRONT_ITEMS],
            "press": newest(recent(list(press.values()), now, days=PRESS_DAYS))[:NEWS_PRESS_ITEMS],
            "seen": seen[-SEEN_IDS:],
            "refreshed_utc": utc(now), "started_utc": None,
            # Where the next refresh starts: at the oldest document left unread, or a little
            # before now, since a filing can show up in the feed some minutes after its time.
            "since_utc": min([i["published_utc"] for i in left] + [utc(now - timedelta(minutes=45))]),
        }

    def _write(self, drafts: list[dict], deadline: float) -> tuple[list[dict], list[dict]]:
        """(items ready to show, drafts left for the next refresh). A draft with a document is
        written by the model while the time lasts; without a model it keeps the code's title."""
        done = [d for d in drafts if "_read" not in d]
        reading = [d for d in drafts if "_read" in d]
        if self.writer is None:
            for d in reading:
                del d["_read"]
            return done + reading, []
        writer = self.writer

        def one(draft: dict) -> dict | None:
            if time.monotonic() > deadline:
                return None
            read = draft.pop("_read")
            try:
                written = writer.write(draft, read())
            except SourceDown as exc:
                log.warning("news document not read: %s", exc)
                return draft
            except Exception as exc:
                log.warning("news document failed: %s (%s)", draft["id"], type(exc).__name__)
                return draft
            if written is None:
                return draft
            if not written["newsworthy"]:
                # Only a filing can be nothing: an agency's release always is news.
                return draft | {"_hidden": True} if draft["id"].startswith("sec-") else draft
            return draft | {"title": written["title"], "summary": written["summary"], "written_by": "model"}

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(one, reading))
        left = [d for d, r in zip(reading, results) if r is None]
        return done + [r for r in results if r is not None], left

    def _market(self) -> list[dict]:
        if self.markets is None:
            return []
        try:
            return market_items(self.markets.overview())
        except Exception as exc:
            log.warning("news market items failed: %s", type(exc).__name__)
            return []


class SampleNews:
    """The sample headlines behind the same interface (tests, MARKETHUB_SAMPLE_NEWS=1)."""

    sample = True

    def news(self, category: str | None = None, tickers: set[str] | None = None, limit: int = 20,
             name: str | None = None) -> dict:
        if tickers and len(tickers) == 1:
            out = sample.news(category=category, ticker=next(iter(tickers)), limit=limit, name=name)
        else:
            out = sample.news(category=category, limit=50)
            if tickers:
                out["items"] = [i for i in out["items"] if tickers.intersection(i["tickers"])]
            out["items"] = out["items"][:limit]
        return out | {"press": [], "refreshed_utc": None, "stale": False}

    def refresh(self) -> dict:
        return {"refreshed": False, "reason": "sample"}


def default_news(markets, directory) -> NewsDesk | SampleNews:
    if os.environ.get("MARKETHUB_SAMPLE_NEWS") == "1":
        return SampleNews()
    store = FirestoreNews() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileNews()
    return NewsDesk(store, default_sources(directory), writer=default_writer(), markets=markets)
