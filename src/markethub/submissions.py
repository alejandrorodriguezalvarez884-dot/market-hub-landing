"""Readers' articles, sent in for review.

A signed-in reader writes an article for the opinion section and sends it. Sending is not
publishing: the article is kept, as it was sent, in a bucket only this service and the owner
reach. The owner reads it there (the market-hub-opinion repo lists what is waiting), and an
article that is to run is published by hand from that repo, as every article is. Nothing here
publishes, and nothing is sent anywhere else.

What is kept with an article is what its review needs: the account it came from (its id, to list
it and to remove it with the account; its name and email, to know whose it is and to answer its
author; how it signs in, because the address of an account with a password of ours is not
verified) and the name its author wants it signed with. The author can take it back, and deleting
the account removes it. The text of an article never goes to a log.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .config import DATA_DIR, SUBMISSIONS_BUCKET, SUBMISSIONS_KEPT_PER_USER

log = logging.getLogger("markethub.submissions")

# The same measures a published article is checked against (market-hub-opinion, articles.py), so
# what is sent can run as it is.
TITLE = (10, 110)
DEK = (60, 260)
WORDS = (450, 1500)
SOURCES = (2, 10)
TICKERS_MAX = 6
BYLINE = (2, 40)
BODY_CHARS = 20000
LIMITS = {"title": TITLE, "dek": DEK, "words": WORDS, "sources": SOURCES, "tickers": TICKERS_MAX, "byline": BYLINE}

ID = re.compile(r"[A-Za-z0-9_\-]{6,40}")
ACCOUNT = re.compile(r"[A-Za-z0-9_\-]{1,80}")  # an account id is part of the name its articles are kept under
TICKER = re.compile(r"[A-Z][A-Z0-9.\-]{0,9}")
ADDRESS = re.compile(r"https?://[^\s<>\"|]{4,400}")
WORD = re.compile(r"\b[\w'’%$.,-]+\b")
# An article argues; it does not tell a reader what to do with their money.
ADVICE = re.compile(r"\b(you should (buy|sell|hold)|we recommend|(buy|sell|hold) rating|strong buy|price target of|our (price )?target"
                    r"|time to (buy|sell)|must[- ]own|top picks?|buy (it |them )?now|guaranteed returns?)\b", re.I)

IN_REVIEW = "in review"


class Refused(ValueError):
    """An article that cannot be taken, with the reason to tell its author."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def words(body: str) -> int:
    return len(WORD.findall(re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)))


def _line(value) -> str:
    """One line of text: a title, a name or an address has no line breaks."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sized(what: str, text: str, limits: tuple[int, int]) -> str:
    if not limits[0] <= len(text) <= limits[1]:
        raise Refused(f"{what} needs {limits[0]} to {limits[1]} characters; it has {len(text)}.")
    return text


def _source(value) -> dict:
    """A source as its author wrote it: an address, or "what it is | its address"."""
    what, _, url = _line(value).rpartition("|")
    what, url = what.strip()[:200], url.strip()
    if not ADDRESS.fullmatch(url):
        raise Refused(f"A source must be a web address starting with https://. This one is not: {url[:60]}")
    return {"title": what or url.split("/")[2], "url": url}


def clean(title, dek, body, sources, tickers, byline, agreed, name: str = "") -> dict:
    """An article as it is kept, or Refused with what to change."""
    if agreed is not True:
        raise Refused("Tick the box to say the article is yours and may be published.")
    title = _sized("The title", _line(title), TITLE)
    dek = _sized("The summary", _line(dek), DEK)
    body = re.sub(r"\n{3,}", "\n\n", str(body or "").replace("\r\n", "\n").replace("\r", "\n")).strip()
    if len(body) > BODY_CHARS:
        raise Refused(f"The text can have up to {BODY_CHARS:,} characters.")
    count = words(body)
    if not WORDS[0] <= count <= WORDS[1]:
        raise Refused(f"The text needs {WORDS[0]} to {WORDS[1]:,} words; it has {count:,}.")
    if re.search(r"<[a-zA-Z/!]", f"{title} {dek} {body}"):
        raise Refused("Write the text plainly, without HTML: paragraphs, ## headings, **bold**, *emphasis* and [links](address).")
    advice = ADVICE.search(f"{title} {dek} {body}")
    if advice:
        raise Refused(f"An article argues; it does not tell readers what to do with their money (\"{advice.group(0)}\").")
    if not isinstance(sources, list) or not all(isinstance(s, str) for s in sources):
        raise Refused("The sources are a list of web addresses.")
    kept = []
    for s in (s for s in sources if s.strip()):
        found = _source(s)
        if found["url"] not in {k["url"] for k in kept}:
            kept.append(found)
    if not SOURCES[0] <= len(kept) <= SOURCES[1]:
        raise Refused(f"Name {SOURCES[0]} to {SOURCES[1]} sources: where the figures and the facts come from.")
    if not isinstance(tickers, list) or len(tickers) > TICKERS_MAX * 3:
        raise Refused("The tickers are a short list.")
    symbols = list(dict.fromkeys(_line(t).upper() for t in tickers if _line(t)))
    if len(symbols) > TICKERS_MAX or not all(TICKER.fullmatch(t) for t in symbols):
        raise Refused(f"Up to {TICKERS_MAX} tickers, written like AAPL.")
    byline = _sized("The name to sign it with", _line(byline) or _line(name), BYLINE)
    return {"title": title, "dek": dek, "body": body, "sources": kept, "tickers": symbols, "byline": byline, "words": count}


# --- Where the articles are kept ----------------------------------------------------------------


class SubmissionStore(Protocol):
    def put(self, doc: dict) -> None: ...
    def by(self, user_id: str) -> list[dict]: ...
    def delete(self, user_id: str, id_: str) -> bool: ...


class MemorySubmissions:
    def __init__(self):
        self.kept: dict[tuple[str, str], dict] = {}

    def put(self, doc: dict) -> None:
        self.kept[(doc["user_id"], doc["id"])] = dict(doc)

    def by(self, user_id: str) -> list[dict]:
        return [dict(d) for (owner, _), d in self.kept.items() if owner == user_id]

    def delete(self, user_id: str, id_: str) -> bool:
        return self.kept.pop((user_id, id_), None) is not None


class FileSubmissions:
    """For local development only: data/submissions/<account>/<id>.json."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "submissions")
        self._lock = threading.Lock()

    def _path(self, user_id: str, id_: str) -> Path:
        return self.root / user_id / f"{id_}.json"

    def put(self, doc: dict) -> None:
        with self._lock:
            path = self._path(doc["user_id"], doc["id"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    def by(self, user_id: str) -> list[dict]:
        folder = self.root / user_id
        return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []

    def delete(self, user_id: str, id_: str) -> bool:
        path = self._path(user_id, id_)
        if not path.exists():
            return False
        path.unlink()
        return True


class BucketSubmissions:
    """A Cloud Storage bucket: submissions/<account>/<id>.json, one object per article."""

    def __init__(self, bucket: str = SUBMISSIONS_BUCKET):
        from google.cloud import storage

        self.name = bucket
        self.bucket = storage.Client().bucket(bucket)

    @staticmethod
    def _path(user_id: str, id_: str) -> str:
        return f"submissions/{user_id}/{id_}.json"

    def put(self, doc: dict) -> None:
        self.bucket.blob(self._path(doc["user_id"], doc["id"])).upload_from_string(
            json.dumps(doc, ensure_ascii=False, indent=1), content_type="application/json; charset=utf-8")

    def by(self, user_id: str) -> list[dict]:
        return [json.loads(b.download_as_bytes()) for b in self.bucket.list_blobs(prefix=f"submissions/{user_id}/")]

    def delete(self, user_id: str, id_: str) -> bool:
        from google.api_core.exceptions import NotFound

        try:
            self.bucket.blob(self._path(user_id, id_)).delete()
        except NotFound:
            return False
        return True


class NoSubmissions:
    """A deployed service that was given no bucket: it takes no articles, and keeps none on a
    disk that is gone with the instance."""

    closed = True

    def put(self, doc: dict) -> None:
        raise RuntimeError("no bucket for readers' articles")

    def by(self, user_id: str) -> list[dict]:
        return []

    def delete(self, user_id: str, id_: str) -> bool:
        return False


def default_submissions() -> SubmissionStore:
    if SUBMISSIONS_BUCKET:
        return BucketSubmissions()
    # Files are for a developer's machine. Where the data lives in Firestore, the service is deployed.
    return NoSubmissions() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileSubmissions()


# --- The desk -------------------------------------------------------------------------------------


class Submissions:
    def __init__(self, store: SubmissionStore, kept_per_user: int = SUBMISSIONS_KEPT_PER_USER):
        self.store, self.kept_per_user = store, kept_per_user

    @property
    def open(self) -> bool:
        """Articles are taken only where there is somewhere to keep them."""
        return not getattr(self.store, "closed", False)

    @staticmethod
    def _view(doc: dict) -> dict:
        """An article as its author gets it back: nothing of the account."""
        return {k: doc.get(k) for k in ("id", "title", "dek", "body", "sources", "tickers", "byline", "words", "received_utc", "status", "slug")}

    def room(self, user: dict) -> None:
        """Refused when this account cannot send one more."""
        if not ACCOUNT.fullmatch(str(user.get("id") or "")):
            raise Refused("This account cannot send articles.")
        if len(self.store.by(user["id"])) >= self.kept_per_user:
            raise Refused(f"You have {self.kept_per_user} articles with us already. Take one back before sending another.")

    def send(self, user: dict, article: dict) -> dict:
        """Keep an article that ``clean`` passed, for the owner to review."""
        self.room(user)
        doc = {**article, "id": secrets.token_urlsafe(9), "user_id": user["id"], "email": _line(user.get("email"))[:300],
               "account_name": _line(user.get("name"))[:120], "provider": user.get("provider", "google"),
               "received_utc": _now(), "status": IN_REVIEW, "slug": None}
        self.store.put(doc)
        log.info("article received words=%s", doc["words"])
        return self._view(doc)

    def mine(self, user_id: str) -> list[dict]:
        """A reader's own articles, newest first: what is kept of them, for their account page."""
        if not ACCOUNT.fullmatch(user_id):
            return []
        return [self._view(d) for d in sorted(self.store.by(user_id), key=lambda d: d["received_utc"], reverse=True)]

    def withdraw(self, user_id: str, id_: str) -> bool:
        """Its author takes an article back: the copy kept for review is removed."""
        if not ACCOUNT.fullmatch(user_id) or not ID.fullmatch(id_):
            return False
        return self.store.delete(user_id, id_)

    def forget(self, user_id: str) -> int:
        """Deleting an account removes the articles it sent."""
        if not ACCOUNT.fullmatch(user_id):
            return 0
        mine = self.store.by(user_id)
        for doc in mine:
            self.store.delete(user_id, doc["id"])
        return len(mine)
