"""Opinion: the articles, and the comments readers leave under them.

The articles are not written here. The market-hub-opinion repo writes them and publishes them
into the store (an article per document, and one "front" document with their cards, so the list
is one read). This service only reads them.

The comments are written here, by signed-in readers, as threads: a comment can answer another.
What is kept of a comment's author is their account id (to let them delete it, and to remove
their comments with their account) and the first name shown next to it. Nothing else of the
account is shown: no email, no picture, no surname. A deleted comment stays as an empty place in
its thread, so the answers under it keep their sense. Comment texts are never logged.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .config import DATA_DIR, FIRESTORE_DATABASE

SLUG = re.compile(r"[a-z0-9][a-z0-9\-]{2,90}")
COMMENT_ID = re.compile(r"[A-Za-z0-9_\-]{6,40}")
COMMENT_MAX = 2000  # characters
DEPTH_MAX = 6  # an answer to an answer to an answer...: below this the thread reads no more
PER_ARTICLE_MAX = 1000
FRONT_CACHE_SECONDS = 60


class Refused(ValueError):
    """A comment that cannot be taken, with the reason to tell its author."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Stores ------------------------------------------------------------------------------------


class OpinionStore(Protocol):
    def front(self) -> list[dict]: ...
    def article(self, slug: str) -> dict | None: ...
    def comments(self, slug: str) -> list[dict]: ...
    def comment(self, id_: str) -> dict | None: ...
    def put_comment(self, comment: dict) -> None: ...
    def comments_by(self, user_id: str) -> list[dict]: ...


class MemoryOpinion:
    def __init__(self, articles: list[dict] | None = None):
        self.articles = {a["slug"]: a for a in articles or []}
        self.kept: dict[str, dict] = {}

    def front(self) -> list[dict]:
        cards = [{k: v for k, v in a.items() if k not in ("body", "sources")} for a in self.articles.values()]
        return sorted(cards, key=lambda a: a["published_utc"], reverse=True)

    def article(self, slug: str) -> dict | None:
        return self.articles.get(slug)

    def comments(self, slug: str) -> list[dict]:
        return [dict(c) for c in self.kept.values() if c["slug"] == slug]

    def comment(self, id_: str) -> dict | None:
        found = self.kept.get(id_)
        return dict(found) if found else None

    def put_comment(self, comment: dict) -> None:
        self.kept[comment["id"]] = dict(comment)

    def comments_by(self, user_id: str) -> list[dict]:
        return [dict(c) for c in self.kept.values() if c.get("user_id") == user_id]


class FileOpinion:
    """For local development only: data/opinion/front.json, articles/ and comments/."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "opinion")
        self._lock = threading.Lock()

    def _read(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def front(self) -> list[dict]:
        return (self._read(self.root / "front.json") or {}).get("articles", [])

    def article(self, slug: str) -> dict | None:
        return self._read(self.root / "articles" / f"{slug}.json") if SLUG.fullmatch(slug) else None

    def _all(self) -> list[dict]:
        folder = self.root / "comments"
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []

    def comments(self, slug: str) -> list[dict]:
        return [c for c in self._all() if c["slug"] == slug]

    def comment(self, id_: str) -> dict | None:
        return self._read(self.root / "comments" / f"{id_}.json") if COMMENT_ID.fullmatch(id_) else None

    def put_comment(self, comment: dict) -> None:
        with self._lock:
            path = self.root / "comments" / f"{comment['id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(comment), encoding="utf-8")

    def comments_by(self, user_id: str) -> list[dict]:
        return [c for c in self._all() if c.get("user_id") == user_id]


class FirestoreOpinion:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        self.client = firestore.Client(database=database)
        self.where = lambda field, value: FieldFilter(field, "==", value)
        self.state = self.client.collection("opinion_state").document("front")
        self.articles = self.client.collection("opinion")
        self.kept = self.client.collection("opinion_comments")

    def front(self) -> list[dict]:
        snap = self.state.get()
        return (snap.to_dict() or {}).get("articles", []) if snap.exists else []

    def article(self, slug: str) -> dict | None:
        snap = self.articles.document(slug).get()
        return snap.to_dict() if snap.exists else None

    def comments(self, slug: str) -> list[dict]:
        return [s.to_dict() for s in self.kept.where(filter=self.where("slug", slug)).limit(PER_ARTICLE_MAX).stream()]

    def comment(self, id_: str) -> dict | None:
        snap = self.kept.document(id_).get()
        return snap.to_dict() if snap.exists else None

    def put_comment(self, comment: dict) -> None:
        self.kept.document(comment["id"]).set(comment)

    def comments_by(self, user_id: str) -> list[dict]:
        return [s.to_dict() for s in self.kept.where(filter=self.where("user_id", user_id)).stream()]


def default_opinion() -> OpinionStore:
    return FirestoreOpinion() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileOpinion()


# --- The desk ----------------------------------------------------------------------------------


def shown_name(user: dict) -> str:
    """What stands next to a comment: the first name of the account, and nothing else of it."""
    first = (str(user.get("name") or "").split() or ["Reader"])[0]
    return first[:30]


class Opinion:
    def __init__(self, store: OpinionStore, admins: set[str] | None = None):
        self.store = store
        # The owner's addresses: they can take any comment down.
        self.admins = admins if admins is not None else {a.strip().lower() for a in os.environ.get("MARKETHUB_ADMINS", "").split(",") if a.strip()}
        self._cached: tuple[float, list[dict]] | None = None

    def articles(self, limit: int = 50) -> list[dict]:
        hit = self._cached
        if not hit or time.monotonic() - hit[0] > FRONT_CACHE_SECONDS:
            hit = self._cached = (time.monotonic(), self.store.front())
        return hit[1][:limit]

    def article(self, slug: str) -> dict | None:
        return self.store.article(slug) if SLUG.fullmatch(slug) else None

    def can_moderate(self, user: dict | None) -> bool:
        return bool(user and str(user.get("email", "")).lower() in self.admins)

    def _view(self, c: dict, user: dict | None) -> dict:
        """A comment as readers get it: never the author's account id."""
        gone = bool(c.get("deleted"))
        return {"id": c["id"], "parent_id": c.get("parent_id"), "depth": c.get("depth", 0), "created_utc": c["created_utc"],
                "deleted": gone, "name": "" if gone else c.get("name", ""), "text": "" if gone else c.get("text", ""),
                "mine": bool(user and not gone and c.get("user_id") == user["id"])}

    def comments(self, slug: str, user: dict | None = None) -> list[dict]:
        """The thread under an article, oldest first: the page nests it by ``parent_id``."""
        if not SLUG.fullmatch(slug):
            return []
        return [self._view(c, user) for c in sorted(self.store.comments(slug), key=lambda c: c["created_utc"])]

    def add(self, user: dict, slug: str, text: str, parent_id: str | None = None) -> dict:
        if not self.article(slug):
            raise Refused("There is no such article.")
        text = re.sub(r"\n{3,}", "\n\n", str(text).replace("\r\n", "\n")).strip()
        if not text:
            raise Refused("Write something first.")
        if len(text) > COMMENT_MAX:
            raise Refused(f"A comment can have up to {COMMENT_MAX} characters.")
        depth = 0
        if parent_id:
            parent = self.store.comment(parent_id) if COMMENT_ID.fullmatch(str(parent_id)) else None
            if not parent or parent["slug"] != slug or parent.get("deleted"):
                raise Refused("The comment you are answering is no longer there.")
            depth = parent.get("depth", 0) + 1
            if depth > DEPTH_MAX:
                raise Refused("This thread is too deep to answer here. Answer further up.")
        if len(self.store.comments(slug)) >= PER_ARTICLE_MAX:
            raise Refused("This article has reached its limit of comments.")
        comment = {"id": secrets.token_urlsafe(9), "slug": slug, "parent_id": parent_id or None, "depth": depth,
                   "user_id": user["id"], "name": shown_name(user), "text": text, "created_utc": _now(), "deleted": False}
        self.store.put_comment(comment)
        return self._view(comment, user)

    def _erase(self, c: dict) -> None:
        self.store.put_comment({**c, "deleted": True, "text": "", "name": "", "user_id": ""})

    def remove(self, user: dict, id_: str) -> bool:
        """Its author, or the owner, takes a comment down. Its place in the thread stays, empty."""
        c = self.store.comment(id_) if COMMENT_ID.fullmatch(id_) else None
        if not c or c.get("deleted"):
            return False
        if c.get("user_id") != user["id"] and not self.can_moderate(user):
            raise PermissionError("Not your comment.")
        self._erase(c)
        return True

    def mine(self, user_id: str) -> list[dict]:
        """A reader's own comments, newest first: what is kept of them, for their account page."""
        kept = [c for c in self.store.comments_by(user_id) if not c.get("deleted")]
        return [{"id": c["id"], "slug": c["slug"], "text": c["text"], "created_utc": c["created_utc"]}
                for c in sorted(kept, key=lambda c: c["created_utc"], reverse=True)]

    def forget(self, user_id: str) -> int:
        """Deleting an account takes its comments with it."""
        mine = [c for c in self.store.comments_by(user_id) if not c.get("deleted")]
        for c in mine:
            self._erase(c)
        return len(mine)
