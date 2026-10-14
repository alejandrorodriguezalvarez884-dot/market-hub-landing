"""Media: what Market Hub's account last posted on X, as the Media page shows it.

Nothing is asked of X here, and nothing by the page either: X's API is paid by the read. The posts
are written and recorded in the-market-hub-media, which knows each one's text and address, and it
publishes the latest of them into the store (one "front" document with a card per post), as it does
with Instagram's. This service only reads them.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Protocol

from .config import DATA_DIR, FIRESTORE_DATABASE

FRONT_CACHE_SECONDS = 60


class XStore(Protocol):
    def front(self) -> dict: ...  # {"posts": [...], "handle": "...", "read_utc": "..."}


class MemoryX:
    def __init__(self, front: dict | None = None):
        self.kept = front or {}

    def front(self) -> dict:
        return self.kept


class FileX:
    """For local development only: data/x/front.json."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "x")

    def front(self) -> dict:
        path = self.root / "front.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


class FirestoreX:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore

        self.state = firestore.Client(database=database).collection("x_state").document("front")

    def front(self) -> dict:
        snap = self.state.get()
        return (snap.to_dict() or {}) if snap.exists else {}


def default_x() -> XStore:
    return FirestoreX() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileX()


class XPosts:
    def __init__(self, store: XStore):
        self.store = store
        self._cached: tuple[float, dict] | None = None

    def latest(self, limit: int = 12) -> dict:
        """The account's latest posts, newest first, the account's name and when they were read."""
        hit = self._cached
        if not hit or time.monotonic() - hit[0] > FRONT_CACHE_SECONDS:
            hit = self._cached = (time.monotonic(), self.store.front())
        front = hit[1]
        return {"posts": list(front.get("posts") or [])[:limit], "handle": front.get("handle") or "", "read_utc": front.get("read_utc")}
