"""The community: portfolios their owners chose to share, and how each one has done.

Nothing is shared unless a user turns it on and picks a name to be shown under. What others
then see is that name, the tickers held with each one's share of the portfolio in percent, and
the returns of those holdings. Never the account's name, email or picture, never how many shares
are held, what was paid or what it is worth. Turning it off, or deleting the account, removes
it at once. Only signed-in users see the board.

What is kept of a shared portfolio is a document of its own, under the user's account id (which
never leaves the server): the name, a snapshot of the figures, and each holding's "units", its
weight over its price, which let the figures be worked out again later without knowing the size
of anything. A user who shares nothing still sees where their own figures would stand.

Every return here is that of today's holdings held through the period, the same measure for
everybody. It ranks portfolios as they are now; it does not say who traded well.
"""

from __future__ import annotations

import json
import os
import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from . import sample
from .config import (COMMUNITY_MEMBERS, COMMUNITY_REFRESH_PER_VISIT, COMMUNITY_STALE_SECONDS, DATA_DIR,
                     FIRESTORE_DATABASE)
from .market import MarketUnavailable

PERIODS = ["1d", "1m", "3m", "ytd", "1y"]
HANDLE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_\-]| (?! )){1,18}[A-Za-z0-9]")
RESERVED = {"you", "average", "admin", "markethub", "market hub", "market-hub", "sp500", "s&p 500", "index"}
SHOWN_POSITIONS = 25


class Refused(ValueError):
    """Sharing that cannot be turned on as asked, with the reason to tell the user."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def handle_key(handle: str) -> str:
    return re.sub(r"[\s_\-]+", "", handle).lower()


def snapshot(d: dict) -> dict:
    """What a shared portfolio shows, taken from the figures of ``dashboard.build``."""
    rows = [r for r in d["positions"] if r["weight"]]
    return {
        "positions": [{"ticker": r["ticker"], "name": r["name"], "sector": r["sector"], "weight": round(r["weight"], 4)} for r in rows[:SHOWN_POSITIONS]],
        "count": len(rows),
        "top_sector": d["sectors"][0]["sector"] if d["sectors"] else None,
        "performance": {p["key"]: p["portfolio"] for p in d["performance"]["periods"]},
        "volatility": d["risk"]["volatility"],
        "sample": bool(d.get("sample")),
        "updated_utc": _now(),
    }


def units(d: dict) -> list[dict]:
    """Each holding's weight over its price: enough to value the same mix again, and nothing
    about how large it is."""
    return [{"ticker": r["ticker"], "shares": round(r["weight"] * 1000 / r["price"], 6), "avg_cost": None}
            for r in d["positions"] if r["weight"] and r["price"]]


# --- Stores ------------------------------------------------------------------------------------


class CommunityStore(Protocol):
    def get(self, user_id: str) -> dict | None: ...
    def put(self, user_id: str, doc: dict) -> None: ...
    def delete(self, user_id: str) -> None: ...
    def all(self, limit: int) -> list[dict]: ...


class MemoryCommunity:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    def get(self, user_id: str) -> dict | None:
        doc = self.docs.get(user_id)
        return json.loads(json.dumps(doc)) if doc else None

    def put(self, user_id: str, doc: dict) -> None:
        self.docs[user_id] = json.loads(json.dumps(doc))

    def delete(self, user_id: str) -> None:
        self.docs.pop(user_id, None)

    def all(self, limit: int) -> list[dict]:
        return [json.loads(json.dumps(d)) for d in list(self.docs.values())[:limit]]


class FileCommunity:
    """For local development only: one JSON file per shared portfolio under data/shared."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "shared")
        self._lock = threading.Lock()

    def _path(self, user_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_\-]{1,128}", user_id):
            raise ValueError("bad user id")
        return self.root / f"{user_id}.json"

    def get(self, user_id: str) -> dict | None:
        path = self._path(user_id)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def put(self, user_id: str, doc: dict) -> None:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            self._path(user_id).write_text(json.dumps(doc), encoding="utf-8")

    def delete(self, user_id: str) -> None:
        self._path(user_id).unlink(missing_ok=True)

    def all(self, limit: int) -> list[dict]:
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.root.glob("*.json"))[:limit]] if self.root.is_dir() else []


class FirestoreCommunity:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore

        self.collection = firestore.Client(database=database).collection("shared_portfolios")

    def get(self, user_id: str) -> dict | None:
        snap = self.collection.document(user_id).get()
        return snap.to_dict() if snap.exists else None

    def put(self, user_id: str, doc: dict) -> None:
        self.collection.document(user_id).set(doc)

    def delete(self, user_id: str) -> None:
        self.collection.document(user_id).delete()

    def all(self, limit: int) -> list[dict]:
        return [s.to_dict() for s in self.collection.limit(limit).stream()]


def default_community() -> CommunityStore:
    return FirestoreCommunity() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileCommunity()


# --- Stand-ins ---------------------------------------------------------------------------------

# While the market data is sample data, so is the company on the board: these are not people.
# They are there so the page has its shape, each one says "sample", and none is shown once the
# figures are real.
SAMPLE_NAMES = ["northwind", "tape_reader", "quiet compounder", "delta nine", "harbour lane", "second derivative", "plainvanilla",
                "long_duration", "copper kettle", "margin of error", "sunday charts", "basis point"]


def _sample_members(value: Callable[[list[dict]], dict]) -> list[dict]:
    out = []
    stocks = [s for s in sample.STOCKS if s.kind == "stock"]
    for i, name in enumerate(SAMPLE_NAMES):
        r = random.Random(sample._seed("member", name))
        picks = r.sample(stocks, r.randint(4, 11))
        weights = [r.uniform(0.4, 1.0) ** 2 for _ in picks]
        positions = [{"ticker": s.symbol, "shares": w / sum(weights) * 1000 / s.level, "avg_cost": None} for s, w in zip(picks, weights)]
        out.append({"handle": name, "since_utc": None, **snapshot(value(positions)), "sample": True, "stand_in": True})
    return out


# --- The board ---------------------------------------------------------------------------------


class Community:
    def __init__(self, store: CommunityStore, value: Callable[[list[dict]], dict], sample_value: Callable[[list[dict]], dict] | None = None):
        """``value(positions)`` works out the figures of a list of positions (dashboard.build);
        ``sample_value`` does it from the sample data, for the stand-ins."""
        self.store, self.value, self.sample_value = store, value, sample_value
        self._stand_ins: tuple[str, list[dict]] | None = None
        self._lock = threading.Lock()

    def status(self, user_id: str) -> dict:
        doc = self.store.get(user_id)
        return {"enabled": bool(doc), "handle": doc["handle"] if doc else "", "since_utc": doc.get("since_utc") if doc else None}

    def share(self, user_id: str, handle: str, d: dict) -> dict:
        """Turn sharing on (or change the name) for the portfolio whose figures are ``d``."""
        handle = " ".join(str(handle).split())
        if not HANDLE.fullmatch(handle):
            raise Refused("Pick a name of 3 to 20 letters, digits, spaces, hyphens or underscores.")
        key = handle_key(handle)
        if key in {handle_key(r) for r in RESERVED}:
            raise Refused("That name is not available.")
        if not any(r["weight"] for r in d["positions"]):
            raise Refused("Add a position first: there is nothing to share yet.")
        mine = self.store.get(user_id)
        if any(m.get("handle_key") == key and m.get("user_id") != user_id for m in self.store.all(COMMUNITY_MEMBERS)):
            raise Refused("Someone already shares under that name.")
        self.store.put(user_id, {"user_id": user_id, "handle": handle, "handle_key": key, "since_utc": (mine or {}).get("since_utc") or _now(),
                                 "units": units(d), **snapshot(d)})
        return self.status(user_id)

    def stop(self, user_id: str) -> dict:
        self.store.delete(user_id)
        return self.status(user_id)

    def refresh(self, user_id: str, d: dict) -> None:
        """Called with the owner's fresh figures: a shared portfolio follows what is held now. One
        that no longer holds anything stops being shared."""
        mine = self.store.get(user_id)
        if not mine:
            return
        if not any(r["weight"] for r in d["positions"]):
            return self.store.delete(user_id)
        self.store.put(user_id, {**mine, "units": units(d), **snapshot(d)})

    def _fresh(self, docs: list[dict]) -> list[dict]:
        """The shared portfolios, with the oldest figures worked out again, a few per visit."""
        now, done = time.time(), 0
        for i, doc in enumerate(docs):
            try:
                age = now - datetime.fromisoformat(doc["updated_utc"]).timestamp()
            except (KeyError, ValueError):
                age = COMMUNITY_STALE_SECONDS + 1
            if age <= COMMUNITY_STALE_SECONDS or done >= COMMUNITY_REFRESH_PER_VISIT or not doc.get("units"):
                continue
            done += 1
            try:
                docs[i] = {**doc, **snapshot(self.value(doc["units"]))}
            except MarketUnavailable:
                continue
            self.store.put(doc["user_id"], docs[i])
        return docs

    def _stand_in_members(self) -> list[dict]:
        if not self.sample_value:
            return []
        day = datetime.now(timezone.utc).date().isoformat()
        with self._lock:
            if not self._stand_ins or self._stand_ins[0] != day:
                self._stand_ins = (day, _sample_members(self.sample_value))
            return self._stand_ins[1]

    def board(self, user_id: str, d: dict | None) -> dict:
        """The shared portfolios, the average of them, and where the figures ``d`` of the user
        asking stand among them, per period. A user who does not share is counted in for their
        own view only: nobody else sees them."""
        docs = self._fresh(self.store.all(COMMUNITY_MEMBERS))
        mine = next((m for m in docs if m.get("user_id") == user_id), None)
        own = snapshot(d) if d and any(r["weight"] for r in d["positions"]) else None
        sampled = bool(d and d.get("sample"))
        members = [{"handle": m["handle"], "since_utc": m.get("since_utc"), "you": m.get("user_id") == user_id, "stand_in": False,
                    **{k: m.get(k) for k in ("positions", "count", "top_sector", "performance", "volatility", "sample", "updated_utc")}}
                   for m in docs]
        if mine and own:  # the owner sees their own row as it is this minute
            members = [{**m, **own} if m["you"] else m for m in members]
        if sampled:
            members += [{**m, "you": False} for m in self._stand_in_members()]
        field = members + ([{"you": True, "performance": own["performance"]}] if own and not mine else [])
        average, standing = {}, {}
        for key in PERIODS:
            marks = sorted((m["performance"].get(key) for m in field if m["performance"].get(key) is not None), reverse=True)
            average[key] = sum(marks) / len(marks) if marks else None
            yours = own["performance"].get(key) if own else None
            if yours is None or len(marks) < 2:
                standing[key] = None
                continue
            rank = 1 + sum(mark > yours for mark in marks)
            standing[key] = {"rank": rank, "of": len(marks), "return": yours, "average": average[key], "above_average": yours > average[key],
                             "ahead_of": (len(marks) - rank) / (len(marks) - 1)}
        return {"members": members, "average": average, "sample": sampled, "shared": len(docs),
                "you": {"sharing": bool(mine), "handle": mine["handle"] if mine else "", "since_utc": mine.get("since_utc") if mine else None,
                        "performance": own["performance"] if own else None, "standing": standing}}
