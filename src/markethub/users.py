"""The user's document: profile, positions and watchlist.

One document per user, keyed by Google's ``sub``. Firestore on Cloud Run, a folder locally,
memory in tests. Portfolio contents are never logged.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .config import DATA_DIR, FIRESTORE_COLLECTION, FIRESTORE_DATABASE, MAX_POSITIONS, MAX_WATCHLIST

TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class InvalidPortfolio(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty(user_id: str) -> dict:
    return {"id": user_id, "positions": [], "watchlist": [], "created_utc": _now(), "updated_utc": _now()}


def normalise_ticker(raw: str) -> str:
    t = str(raw).strip().upper().replace("/", "-").replace(".", "-")  # BRK.B -> BRK-B, as the SEC and FMP write it
    if not TICKER.match(t):
        raise InvalidPortfolio(f"Not a ticker: {raw!r}")
    return t


def clean(positions: list, watchlist: list, known=None) -> tuple[list[dict], list[str]]:
    """Validate what the visitor sent. ``known(ticker)`` says whether a ticker exists; unknown
    tickers are rejected so typos do not end up on the dashboard. Repeated tickers in the
    positions are merged at their weighted average cost."""
    if not isinstance(positions, list) or not isinstance(watchlist, list):
        raise InvalidPortfolio("Positions and watchlist must be lists.")
    if len(positions) > MAX_POSITIONS or len(watchlist) > MAX_WATCHLIST:
        raise InvalidPortfolio(f"Up to {MAX_POSITIONS} positions and {MAX_WATCHLIST} favourites.")
    merged: dict[str, dict] = {}
    for p in positions:
        if not isinstance(p, dict):
            raise InvalidPortfolio("Each position needs a ticker, shares and an average cost.")
        ticker = normalise_ticker(p.get("ticker", ""))
        try:
            shares = float(p.get("shares"))
            cost = float(p.get("avg_cost")) if p.get("avg_cost") not in (None, "") else None
        except (TypeError, ValueError):
            raise InvalidPortfolio(f"{ticker}: shares and average cost must be numbers.") from None
        if not 0 < shares < 1e9:
            raise InvalidPortfolio(f"{ticker}: shares must be positive.")
        if cost is not None and not 0 <= cost < 1e7:
            raise InvalidPortfolio(f"{ticker}: the average cost must be zero or positive.")
        if known and not known(ticker):
            raise InvalidPortfolio(f"{ticker} is not a US-listed ticker.")
        if ticker in merged:
            prev = merged[ticker]
            total = prev["shares"] + shares
            if prev["avg_cost"] is not None and cost is not None:
                prev["avg_cost"] = (prev["avg_cost"] * prev["shares"] + cost * shares) / total
            else:
                prev["avg_cost"] = None
            prev["shares"] = total
        else:
            merged[ticker] = {"ticker": ticker, "shares": shares, "avg_cost": cost}
    seen, favourites = set(merged), []
    for raw in watchlist:
        ticker = normalise_ticker(raw)
        if ticker in seen:
            continue
        if known and not known(ticker):
            raise InvalidPortfolio(f"{ticker} is not a US-listed ticker.")
        seen.add(ticker)
        favourites.append(ticker)
    return list(merged.values()), favourites


class UserStore(Protocol):
    def get(self, user_id: str) -> dict | None: ...
    def put(self, user_id: str, doc: dict) -> None: ...
    def delete(self, user_id: str) -> None: ...


class MemoryUsers:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    def get(self, user_id: str) -> dict | None:
        doc = self.docs.get(user_id)
        return json.loads(json.dumps(doc)) if doc else None

    def put(self, user_id: str, doc: dict) -> None:
        self.docs[user_id] = json.loads(json.dumps(doc))

    def delete(self, user_id: str) -> None:
        self.docs.pop(user_id, None)


class FileUsers:
    """For local development only: one JSON file per user under data/users."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "users")
        self._lock = threading.Lock()

    def _path(self, user_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_\-]{1,128}", user_id):
            raise ValueError("bad user id")
        return self.root / f"{user_id}.json"

    def get(self, user_id: str) -> dict | None:
        path = self._path(user_id)
        return json.loads(path.read_text()) if path.exists() else None

    def put(self, user_id: str, doc: dict) -> None:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = self._path(user_id).with_suffix(".tmp")
            tmp.write_text(json.dumps(doc))
            tmp.replace(self._path(user_id))

    def delete(self, user_id: str) -> None:
        self._path(user_id).unlink(missing_ok=True)


class FirestoreUsers:
    def __init__(self, collection: str = FIRESTORE_COLLECTION, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore

        self.collection = firestore.Client(database=database).collection(collection)

    def get(self, user_id: str) -> dict | None:
        snap = self.collection.document(user_id).get()
        return snap.to_dict() if snap.exists else None

    def put(self, user_id: str, doc: dict) -> None:
        self.collection.document(user_id).set(doc)

    def delete(self, user_id: str) -> None:
        self.collection.document(user_id).delete()


def default_users() -> UserStore:
    return FirestoreUsers() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileUsers()


def touch(doc: dict, **changes) -> dict:
    doc.update(changes)
    doc["updated_utc"] = _now()
    return doc
