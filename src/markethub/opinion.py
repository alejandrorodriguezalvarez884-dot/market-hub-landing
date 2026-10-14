"""Opinion: the articles, and the comments readers leave under them.

The articles are not written here. The market-hub-opinion repo writes them and publishes them
into the store (an article per document, and one "front" document with their cards, so the list
is one read), and with each its cover: a picture, kept as it was published. This service only
reads them.

The comments are written here, by signed-in readers, as threads: a comment can answer another.
What is kept of a comment's author is their account id (to let them delete it, and to remove
their comments with their account) and the first name shown next to it. Nothing else of the
account is shown: no email, no picture, no surname. A deleted comment stays as an empty place in
its thread, so the answers under it keep their sense. Comment texts are never logged.

A reader can report a comment and can block its author. A reported comment is no longer shown to
whoever reported it; reported by two readers, it is shown to nobody until the owner has looked at
it, and the owner keeps it or takes it down. A blocked author's comments are not shown to whoever
blocked them, anywhere. What is kept: with a comment, the account ids of who reported it; and a
block as a document of its own (who blocked whom, the name the comment was shown under, when).
Both go with the account of whoever made them, and a block goes with the blocked account too.
A comment in language nobody should have to read is not taken at all.
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
HOLD_AT = 2  # reported by this many readers, a comment is hidden from everybody until it is reviewed
BLOCKS_MAX = 200  # authors one reader can block
FRONT_CACHE_SECONDS = 60
COVERS_KEPT = 48  # covers held in memory, so a picture is read from the store once
TEXTS_KEPT = 200  # whole articles held in memory, for the pages the server fills (previews.py)
# Threads that hang from something other than an article keep their comments in the same store,
# under a name of their own. The community's competition has one a month ("competition-2026-11");
# only signed-in members read those, so the public thread of an article never answers for them.
MEMBERS_ONLY = "competition-"


class Refused(ValueError):
    """A comment that cannot be taken, with the reason to tell its author."""


# Words a comment is not published with: slurs and the coarsest insults, in English and in
# Spanish, as whole words. It is a floor, not the moderation: the rest is reported and reviewed.
_UNPUBLISHED = re.compile(r"(?<![a-z])(?:" + "|".join((
    "n[i1]gg(?:er|a)s?", "f[a4]gg?[o0]ts?", "k[i1]kes?", "sp[i1]cs?", "ch[i1]nks?", "tr[a4]nn(?:y|ies)", "r[e3]t[a4]rd(?:s|ed)?",
    "c[u*]nts?", "wh[o0]res?", "sl[u*]ts?", "f[u*]ck(?:er|ers|ing|ed|s)?", "m[o0]therf[u*]ck(?:er|ers|ing)?", "b[i1]tch(?:es)?",
    "assh[o0]les?", "kill yourself", "kys",
    "maric[oó]n(?:es)?", "put[ao]s?", "hijo(?:s)? de puta", "hijueputa", "zorras?", "subnormal(?:es)?", "gilipollas", "cabr[oó]n(?:es)?",
    "sudacas?", "panchitos?", "mátate", "matate",
)) + r")(?![a-z])", re.IGNORECASE)


def publishable(text: str) -> bool:
    return not _UNPUBLISHED.search(text)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- Stores ------------------------------------------------------------------------------------


class OpinionStore(Protocol):
    def front(self) -> list[dict]: ...
    def article(self, slug: str) -> dict | None: ...
    def cover(self, slug: str) -> bytes | None: ...
    def comments(self, slug: str) -> list[dict]: ...
    def comment(self, id_: str) -> dict | None: ...
    def put_comment(self, comment: dict) -> None: ...
    def comments_by(self, user_id: str) -> list[dict]: ...
    def reported(self) -> list[dict]: ...  # the comments somebody has reported
    def reported_by(self, user_id: str) -> list[dict]: ...
    def blocks(self, field: str, user_id: str) -> list[dict]: ...  # field: "by" (who blocked) or "of" (who is blocked)
    def put_block(self, block: dict) -> None: ...
    def delete_block(self, id_: str) -> None: ...


class MemoryOpinion:
    def __init__(self, articles: list[dict] | None = None):
        self.articles = {a["slug"]: a for a in articles or []}
        self.covers: dict[str, bytes] = {}
        self.kept: dict[str, dict] = {}
        self.blocked: dict[str, dict] = {}

    def front(self) -> list[dict]:
        cards = [{k: v for k, v in a.items() if k not in ("body", "sources")} for a in self.articles.values()]
        return sorted(cards, key=lambda a: a["published_utc"], reverse=True)

    def article(self, slug: str) -> dict | None:
        return self.articles.get(slug)

    def cover(self, slug: str) -> bytes | None:
        return self.covers.get(slug)

    def comments(self, slug: str) -> list[dict]:
        return [dict(c) for c in self.kept.values() if c["slug"] == slug]

    def comment(self, id_: str) -> dict | None:
        found = self.kept.get(id_)
        return dict(found) if found else None

    def put_comment(self, comment: dict) -> None:
        self.kept[comment["id"]] = dict(comment)

    def comments_by(self, user_id: str) -> list[dict]:
        return [dict(c) for c in self.kept.values() if c.get("user_id") == user_id]

    def reported(self) -> list[dict]:
        return [dict(c) for c in self.kept.values() if c.get("reported")]

    def reported_by(self, user_id: str) -> list[dict]:
        return [dict(c) for c in self.kept.values() if user_id in (c.get("reported_by") or [])]

    def blocks(self, field: str, user_id: str) -> list[dict]:
        return [dict(b) for b in self.blocked.values() if b.get(field) == user_id]

    def put_block(self, block: dict) -> None:
        self.blocked[block["id"]] = dict(block)

    def delete_block(self, id_: str) -> None:
        self.blocked.pop(id_, None)


class FileOpinion:
    """For local development only: data/opinion/front.json, articles/, covers/ and comments/."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "opinion")
        self._lock = threading.Lock()

    def _read(self, path: Path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def front(self) -> list[dict]:
        return (self._read(self.root / "front.json") or {}).get("articles", [])

    def article(self, slug: str) -> dict | None:
        return self._read(self.root / "articles" / f"{slug}.json") if SLUG.fullmatch(slug) else None

    def cover(self, slug: str) -> bytes | None:
        path = self.root / "covers" / f"{slug}.jpg"
        return path.read_bytes() if path.exists() else None

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

    def reported(self) -> list[dict]:
        return [c for c in self._all() if c.get("reported")]

    def reported_by(self, user_id: str) -> list[dict]:
        return [c for c in self._all() if user_id in (c.get("reported_by") or [])]

    def blocks(self, field: str, user_id: str) -> list[dict]:
        folder = self.root / "blocks"
        every = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []
        return [b for b in every if b.get(field) == user_id]

    def put_block(self, block: dict) -> None:
        with self._lock:
            path = self.root / "blocks" / f"{block['id']}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(block), encoding="utf-8")

    def delete_block(self, id_: str) -> None:
        if COMMENT_ID.fullmatch(id_):
            (self.root / "blocks" / f"{id_}.json").unlink(missing_ok=True)


class FirestoreOpinion:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore
        from google.cloud.firestore_v1.base_query import FieldFilter

        self.client = firestore.Client(database=database)
        self.where = lambda field, value: FieldFilter(field, "==", value)
        self.holds = lambda field, value: FieldFilter(field, "array_contains", value)
        self.state = self.client.collection("opinion_state").document("front")
        self.articles = self.client.collection("opinion")
        self.covers = self.client.collection("opinion_covers")
        self.kept = self.client.collection("opinion_comments")
        self.blocked = self.client.collection("opinion_blocks")

    def front(self) -> list[dict]:
        snap = self.state.get()
        return (snap.to_dict() or {}).get("articles", []) if snap.exists else []

    def article(self, slug: str) -> dict | None:
        snap = self.articles.document(slug).get()
        return snap.to_dict() if snap.exists else None

    def cover(self, slug: str) -> bytes | None:
        snap = self.covers.document(slug).get()
        return (snap.to_dict() or {}).get("jpeg") if snap.exists else None

    def comments(self, slug: str) -> list[dict]:
        return [s.to_dict() for s in self.kept.where(filter=self.where("slug", slug)).limit(PER_ARTICLE_MAX).stream()]

    def comment(self, id_: str) -> dict | None:
        snap = self.kept.document(id_).get()
        return snap.to_dict() if snap.exists else None

    def put_comment(self, comment: dict) -> None:
        self.kept.document(comment["id"]).set(comment)

    def comments_by(self, user_id: str) -> list[dict]:
        return [s.to_dict() for s in self.kept.where(filter=self.where("user_id", user_id)).stream()]

    def reported(self) -> list[dict]:
        return [s.to_dict() for s in self.kept.where(filter=self.where("reported", True)).limit(PER_ARTICLE_MAX).stream()]

    def reported_by(self, user_id: str) -> list[dict]:
        return [s.to_dict() for s in self.kept.where(filter=self.holds("reported_by", user_id)).stream()]

    def blocks(self, field: str, user_id: str) -> list[dict]:
        return [s.to_dict() for s in self.blocked.where(filter=self.where(field, user_id)).limit(BLOCKS_MAX * 5).stream()]

    def put_block(self, block: dict) -> None:
        self.blocked.document(block["id"]).set(block)

    def delete_block(self, id_: str) -> None:
        self.blocked.document(id_).delete()


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
        self._covers: dict[tuple[str, str], bytes] = {}
        self._texts: dict[tuple[str, str, str], dict] = {}

    def articles(self, limit: int = 50) -> list[dict]:
        hit = self._cached
        if not hit or time.monotonic() - hit[0] > FRONT_CACHE_SECONDS:
            hit = self._cached = (time.monotonic(), self.store.front())
        return hit[1][:limit]

    def card(self, slug: str) -> dict | None:
        """The card of one article, from the list held in memory: no read of the store, however
        often it is asked for. An article older than the list holds has none."""
        return next((a for a in self.articles(limit=10**6) if a["slug"] == slug), None)

    def article(self, slug: str) -> dict | None:
        return self.store.article(slug) if SLUG.fullmatch(slug) else None

    def kept(self, slug: str) -> dict | None:
        """The whole article for a slug the list names, read from the store once and then held,
        so the page a crawler asks for over and over costs one read. An article published again
        (a new date or a new cover on its card) is read again; a slug the list does not name is
        not read at all."""
        card = self.card(slug)
        if not card:
            return None
        key = (slug, str(card.get("updated_utc") or card.get("published_utc") or ""), str((card.get("cover") or {}).get("v") or ""))
        found = self._texts.get(key)
        if found is None:
            found = self.store.article(slug)
            if found:
                if len(self._texts) >= TEXTS_KEPT:
                    self._texts.pop(next(iter(self._texts)))
                self._texts[key] = found
        return found

    def cover(self, slug: str, version: str = "") -> bytes | None:
        """The picture of an article, as JPEG. ``version`` is the one the article's card names: a
        cover that is drawn again is another version, and is read again."""
        if not SLUG.fullmatch(slug):
            return None
        found = self._covers.get((slug, version))
        if found is None:
            found = self.store.cover(slug)
            if found:
                if len(self._covers) >= COVERS_KEPT:
                    self._covers.pop(next(iter(self._covers)))
                self._covers[(slug, version)] = found
        return found

    def can_moderate(self, user: dict | None) -> bool:
        """The owner, by an address Google has verified. An account with a password of ours can
        be made with any address, so its email proves nothing."""
        return bool(user and user.get("provider", "google") == "google" and str(user.get("email", "")).lower() in self.admins)

    def _view(self, c: dict, user: dict | None, blocked: frozenset[str] = frozenset(), moderator: bool = False) -> dict:
        """A comment as readers get it: never the author's account id, nor who reported it.
        ``hidden`` says why a comment that is there is not shown to this reader: they blocked
        its author, they reported it, or it is held until the owner has looked at it."""
        gone = bool(c.get("deleted"))
        reporters = c.get("reported_by") or []
        hidden = None
        if not gone and user and c.get("user_id") in blocked:
            hidden = "blocked"
        elif not gone and user and user["id"] in reporters:
            hidden = "reported"
        elif not gone and len(reporters) >= HOLD_AT and not moderator:
            hidden = "held"
        blank = gone or bool(hidden)
        view = {"id": c["id"], "parent_id": c.get("parent_id"), "depth": c.get("depth", 0), "created_utc": c["created_utc"],
                "deleted": gone, "hidden": hidden, "name": "" if blank else c.get("name", ""), "text": "" if blank else c.get("text", ""),
                "mine": bool(user and not gone and c.get("user_id") == user["id"])}
        if moderator and not gone:
            view["reports"] = len(reporters)
        return view

    def _blocked_by(self, user: dict | None) -> frozenset[str]:
        return frozenset(b["of"] for b in self.store.blocks("by", user["id"])) if user else frozenset()

    def comments(self, slug: str, user: dict | None = None) -> list[dict]:
        """A thread, oldest first: the page nests it by ``parent_id``."""
        if not SLUG.fullmatch(slug):
            return []
        blocked, moderator = self._blocked_by(user), self.can_moderate(user)
        return [self._view(c, user, blocked, moderator) for c in sorted(self.store.comments(slug), key=lambda c: c["created_utc"])]

    def add(self, user: dict, slug: str, text: str, parent_id: str | None = None) -> dict:
        """A comment under an article."""
        if slug.startswith(MEMBERS_ONLY) or not self.article(slug):
            raise Refused("There is no such article.")
        return self.post(user, slug, text, parent_id)

    def post(self, user: dict, slug: str, text: str, parent_id: str | None = None, name: str | None = None) -> dict:
        """A comment in the thread ``slug``, whatever it hangs from: the caller has checked that
        it exists. ``name`` is what stands next to it, when that is not the account's first name."""
        if not SLUG.fullmatch(slug):
            raise Refused("There is no such thread.")
        text = re.sub(r"\n{3,}", "\n\n", str(text).replace("\r\n", "\n")).strip()
        if not text:
            raise Refused("Write something first.")
        if len(text) > COMMENT_MAX:
            raise Refused(f"A comment can have up to {COMMENT_MAX} characters.")
        if not publishable(text):
            raise Refused("That has language we do not publish. Say it another way.")
        depth = 0
        if parent_id:
            parent = self.store.comment(parent_id) if COMMENT_ID.fullmatch(str(parent_id)) else None
            if not parent or parent["slug"] != slug or parent.get("deleted"):
                raise Refused("The comment you are answering is no longer there.")
            depth = parent.get("depth", 0) + 1
            if depth > DEPTH_MAX:
                raise Refused("This thread is too deep to answer here. Answer further up.")
        if len(self.store.comments(slug)) >= PER_ARTICLE_MAX:
            raise Refused("This thread has reached its limit of comments.")
        comment = {"id": secrets.token_urlsafe(9), "slug": slug, "parent_id": parent_id or None, "depth": depth,
                   "user_id": user["id"], "name": (name or shown_name(user))[:30], "text": text, "created_utc": _now(), "deleted": False}
        self.store.put_comment(comment)
        return self._view(comment, user)

    def _erase(self, c: dict) -> None:
        self.store.put_comment({**c, "deleted": True, "text": "", "name": "", "user_id": "", "reported": False, "reported_by": []})

    def _there(self, id_: str) -> dict | None:
        c = self.store.comment(id_) if COMMENT_ID.fullmatch(str(id_)) else None
        return c if c and not c.get("deleted") else None

    # --- Reporting a comment, and blocking its author ------------------------------------------

    def report(self, user: dict, id_: str) -> bool:
        """A reader says a comment should not be there. It is hidden from them at once, and from
        everybody when ``HOLD_AT`` readers have said so, until the owner keeps it or takes it down."""
        c = self._there(id_)
        if not c:
            raise Refused("That comment is no longer there.")
        if c.get("user_id") == user["id"]:
            raise Refused("That is your own comment: you can delete it.")
        reporters = list(c.get("reported_by") or [])
        if user["id"] not in reporters:
            self.store.put_comment({**c, "reported": True, "reported_by": [*reporters, user["id"]]})
        return True

    def reports(self, user: dict) -> list[dict]:
        """For the owner: the reported comments, the most reported first."""
        if not self.can_moderate(user):
            raise PermissionError("Only the owner reviews reports.")
        waiting = [c for c in self.store.reported() if not c.get("deleted") and c.get("reported_by")]
        return [{"id": c["id"], "slug": c["slug"], "name": c.get("name", ""), "text": c.get("text", ""), "created_utc": c["created_utc"],
                 "reports": len(c["reported_by"]), "held": len(c["reported_by"]) >= HOLD_AT}
                for c in sorted(waiting, key=lambda c: (-len(c["reported_by"]), c["created_utc"]))]

    def keep(self, user: dict, id_: str) -> bool:
        """The owner has looked at a reported comment and it stays: its reports are dropped."""
        if not self.can_moderate(user):
            raise PermissionError("Only the owner reviews reports.")
        c = self._there(id_)
        if not c:
            return False
        self.store.put_comment({**c, "reported": False, "reported_by": []})
        return True

    def block(self, user: dict, id_: str) -> bool:
        """A reader stops seeing whatever the author of a comment writes. The author is named by
        one of their comments: readers never have anybody's account id."""
        c = self._there(id_)
        if not c:
            raise Refused("That comment is no longer there.")
        if c.get("user_id") == user["id"]:
            raise Refused("That is your own comment.")
        mine = self.store.blocks("by", user["id"])
        if any(b["of"] == c["user_id"] for b in mine):
            return True
        if len(mine) >= BLOCKS_MAX:
            raise Refused(f"You can block up to {BLOCKS_MAX} members. Unblock one first, on your account page.")
        self.store.put_block({"id": secrets.token_urlsafe(9), "by": user["id"], "of": c["user_id"], "name": c.get("name", "")[:30], "created_utc": _now()})
        return True

    def blocked(self, user_id: str) -> list[dict]:
        """Who a reader has blocked, newest first: the name their comment was shown under, and a
        key to unblock them with. Never their account id."""
        return [{"key": b["id"], "name": b.get("name", ""), "since_utc": b["created_utc"]}
                for b in sorted(self.store.blocks("by", user_id), key=lambda b: b["created_utc"], reverse=True)]

    def unblock(self, user_id: str, key: str) -> bool:
        found = [b for b in self.store.blocks("by", user_id) if b["id"] == key]
        for b in found:
            self.store.delete_block(b["id"])
        return bool(found)

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
        # What they reported is no longer reported by them, and no block of theirs or of them stays.
        for c in self.store.reported_by(user_id):
            left = [r for r in c.get("reported_by") or [] if r != user_id]
            self.store.put_comment({**c, "reported_by": left, "reported": bool(left)})
        for b in [*self.store.blocks("by", user_id), *self.store.blocks("of", user_id)]:
            self.store.delete_block(b["id"])
        return len(mine)
