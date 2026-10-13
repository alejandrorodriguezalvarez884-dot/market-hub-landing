"""Media: what Market Hub's account last posted on Instagram, as the Media page shows it.

Nothing is asked of Instagram here, and nothing by the page either. Reading an account's posts
takes the account's token, which also publishes on it: it has no place in a public service. The
the-market-hub-media repo, which holds it, reads the account's latest posts and publishes them
into the store (one "front" document with a card per post, and each post's cover as a picture),
as market-hub-opinion does with the articles. This service only reads them. A post is a reel, a
picture or an album: whatever the account posted, newest first.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Protocol

from .config import DATA_DIR, FIRESTORE_DATABASE

POST_ID = re.compile(r"[0-9]{5,30}")  # Instagram's id of a post
FRONT_CACHE_SECONDS = 60
COVERS_KEPT = 24  # covers held in memory, so a picture is read from the store once


class PostStore(Protocol):
    def front(self) -> dict: ...  # {"posts": [...], "handle": "...", "read_utc": "..."}
    def cover(self, id_: str) -> bytes | None: ...


class MemoryPosts:
    def __init__(self, front: dict | None = None, covers: dict[str, bytes] | None = None):
        self.kept, self.covers = front or {}, covers or {}

    def front(self) -> dict:
        return self.kept

    def cover(self, id_: str) -> bytes | None:
        return self.covers.get(id_)


class FilePosts:
    """For local development only: data/instagram/front.json and covers/."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "instagram")

    def front(self) -> dict:
        path = self.root / "front.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def cover(self, id_: str) -> bytes | None:
        path = self.root / "covers" / f"{id_}.jpg"
        return path.read_bytes() if path.exists() else None


class FirestorePosts:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore

        client = firestore.Client(database=database)
        self.state = client.collection("instagram_state").document("front")
        self.covers = client.collection("instagram_covers")

    def front(self) -> dict:
        snap = self.state.get()
        return (snap.to_dict() or {}) if snap.exists else {}

    def cover(self, id_: str) -> bytes | None:
        snap = self.covers.document(id_).get()
        return (snap.to_dict() or {}).get("jpeg") if snap.exists else None


def default_posts() -> PostStore:
    return FirestorePosts() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FilePosts()


class Posts:
    def __init__(self, store: PostStore):
        self.store = store
        self._cached: tuple[float, dict] | None = None
        self._covers: dict[tuple[str, str], bytes] = {}

    def latest(self, limit: int = 12) -> dict:
        """The account's latest posts, newest first, the account's name and when they were read."""
        hit = self._cached
        if not hit or time.monotonic() - hit[0] > FRONT_CACHE_SECONDS:
            hit = self._cached = (time.monotonic(), self.store.front())
        front = hit[1]
        return {"posts": list(front.get("posts") or [])[:limit], "handle": front.get("handle") or "", "read_utc": front.get("read_utc")}

    def cover(self, id_: str, version: str = "") -> bytes | None:
        """The cover of a post, as JPEG. ``version`` is the one the post's card names: a cover that
        is made again is another version, and is read again."""
        if not POST_ID.fullmatch(id_):
            return None
        found = self._covers.get((id_, version))
        if found is None:
            found = self.store.cover(id_)
            if found:
                if len(self._covers) >= COVERS_KEPT:
                    self._covers.pop(next(iter(self._covers)))
                self._covers[(id_, version)] = found
        return found
