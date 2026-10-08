"""Readers' articles, sent in for review.

A signed-in reader writes an article for the opinion section and sends it. Sending is not
publishing: the article is kept, as it was sent, in a bucket only this service and the owner
reach, and the owner is told by email. The owner reads it, and an article that is to run is
published by hand from the market-hub-opinion repo, as every article is. Nothing here publishes.

What is kept with an article is what its review needs: the account it came from (its id, to list
it and to remove it with the account; its email, to answer its author; how it signs in, because
the address of an account with a password of ours is not verified) and the name its author wants
it signed with. The author can take it back, and deleting the account removes it. The text of an
article never goes to a log.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import smtplib
import ssl
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
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
MAILBOX = re.compile(r"[^@\s<>,;:\"]+@[^@\s<>,;:\"]+\.[^@\s<>,;:\"]+")
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
    """One line of text: a title cannot carry a line break into the subject of a message."""
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
    local: bool  # a developer's machine: nobody is waiting for the message

    def put(self, doc: dict) -> None: ...
    def by(self, user_id: str) -> list[dict]: ...
    def delete(self, user_id: str, id_: str) -> bool: ...
    def where(self, doc: dict) -> str: ...


class MemorySubmissions:
    local = True

    def __init__(self):
        self.kept: dict[tuple[str, str], dict] = {}

    def put(self, doc: dict) -> None:
        self.kept[(doc["user_id"], doc["id"])] = dict(doc)

    def by(self, user_id: str) -> list[dict]:
        return [dict(d) for (owner, _), d in self.kept.items() if owner == user_id]

    def delete(self, user_id: str, id_: str) -> bool:
        return self.kept.pop((user_id, id_), None) is not None

    def where(self, doc: dict) -> str:
        return f"memory:submissions/{doc['user_id']}/{doc['id']}.json"


class FileSubmissions:
    """For local development only: data/submissions/<account>/<id>.json."""

    local = True

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

    def where(self, doc: dict) -> str:
        return str(self._path(doc["user_id"], doc["id"]))


class BucketSubmissions:
    """A Cloud Storage bucket: submissions/<account>/<id>.json, one object per article."""

    local = False

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

    def where(self, doc: dict) -> str:
        return f"gs://{self.name}/{self._path(doc['user_id'], doc['id'])}"


class NoSubmissions:
    """A deployed service that was given no bucket: it takes no articles, and keeps none on a
    disk that is gone with the instance."""

    local = False
    closed = True

    def put(self, doc: dict) -> None:
        raise RuntimeError("no bucket for readers' articles")

    def by(self, user_id: str) -> list[dict]:
        return []

    def delete(self, user_id: str, id_: str) -> bool:
        return False

    def where(self, doc: dict) -> str:
        return ""


def default_submissions() -> SubmissionStore:
    if SUBMISSIONS_BUCKET:
        return BucketSubmissions()
    # Files are for a developer's machine. Where the data lives in Firestore, the service is deployed.
    return NoSubmissions() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileSubmissions()


# --- Telling the owner ----------------------------------------------------------------------------


class Mailer(Protocol):
    def send(self, subject: str, text: str, reply_to: str | None = None) -> None: ...


class SmtpMailer:
    """A message to the owner through a mail server that takes a user and a password: the owner's
    own mailbox (Gmail with an app password) or any provider's relay."""

    def __init__(self, host: str, port: int, user: str, password: str, sender: str, to: str):
        self.host, self.port, self.user, self.password, self.sender, self.to = host, port, user, password, sender, to

    def send(self, subject: str, text: str, reply_to: str | None = None) -> None:
        message = EmailMessage()
        message["Subject"], message["From"], message["To"] = subject, self.sender, self.to
        if reply_to:
            message["Reply-To"] = reply_to
        message.set_content(text)
        secure = ssl.create_default_context()
        if self.port == 465:
            server = smtplib.SMTP_SSL(self.host, self.port, timeout=15, context=secure)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=15)
        with server:
            if self.port != 465:
                server.starttls(context=secure)
            server.login(self.user, self.password)
            server.send_message(message)


def default_mailer() -> Mailer | None:
    """The owner's mailbox, when the environment names one: SMTP_USER and SMTP_PASSWORD, and who
    reads the articles (MARKETHUB_REVIEW_EMAIL; else the first of MARKETHUB_ADMINS)."""
    env = lambda name, default="": os.environ.get(name, default).strip()  # noqa: E731
    user, password = env("SMTP_USER"), env("SMTP_PASSWORD")
    to = env("MARKETHUB_REVIEW_EMAIL") or env("MARKETHUB_ADMINS").split(",")[0].strip()
    if not (user and password and to):
        return None
    return SmtpMailer(env("SMTP_HOST", "smtp.gmail.com"), int(env("SMTP_PORT", "587") or 587), user, password,
                      env("MARKETHUB_MAIL_FROM") or user, to)


def _account(doc: dict) -> str:
    how = "Google, a verified address" if doc.get("provider") == "google" else "an account with a password: the address is NOT verified"
    return f"{doc.get('account_name', '')} <{doc.get('email', '')}> ({how})"


def review_message(doc: dict, where: str) -> tuple[str, str]:
    """What the owner gets: the article whole, who sent it and where it is kept."""
    sources = "\n".join(f"- {s['title']} | {s['url']}" for s in doc["sources"])
    text = "\n".join([
        "A reader sent an article to Opinion for review. It is NOT published.",
        "",
        f"Title:     {doc['title']}",
        f"Signed as: {doc['byline']}",
        f"Account:   {_account(doc)}",
        f"Sent:      {doc['received_utc']}",
        f"Words:     {doc['words']}",
        f"Tickers:   {', '.join(doc['tickers']) or 'none'}",
        f"Id:        {doc['id']}",
        f"Kept at:   {where}",
        "",
        "--- Summary ---",
        doc["dek"],
        "",
        "--- Text ---",
        doc["body"],
        "",
        "--- Sources ---",
        sources,
        "",
        "To publish it, or to turn it down, go through the market-hub-opinion repo (its README says how).",
    ])
    return f"[Market Hub] Article for review: {doc['title']}", text


def gone_message(doc: dict, why: str) -> tuple[str, str]:
    return (f"[Market Hub] Article withdrawn: {doc['title']}",
            f"The article \"{doc['title']}\" (id {doc['id']}, sent {doc['received_utc']}, signed as {doc['byline']}) is no longer kept: {why}.\n"
            "If it was not published yet, there is nothing left to review.")


# --- The desk -------------------------------------------------------------------------------------


class Submissions:
    def __init__(self, store: SubmissionStore, mailer: Mailer | None = None, kept_per_user: int = SUBMISSIONS_KEPT_PER_USER):
        self.store, self.mailer, self.kept_per_user = store, mailer, kept_per_user

    @property
    def open(self) -> bool:
        """Articles are taken only where they can be kept and the owner will hear of them."""
        return not getattr(self.store, "closed", False) and (bool(self.mailer) or self.store.local)

    def _tell(self, message: tuple[str, str], reply_to: str | None = None) -> bool:
        if not self.mailer:
            return False
        try:
            self.mailer.send(*message, reply_to=reply_to)
        except Exception as exc:  # the article is kept all the same: the owner finds it in the bucket
            log.error("submission mail failed: %s", type(exc).__name__)
            return False
        return True

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
        """Keep an article that ``clean`` passed, and tell the owner."""
        self.room(user)
        email = str(user.get("email") or "")
        doc = {**article, "id": secrets.token_urlsafe(9), "user_id": user["id"], "email": email, "account_name": _line(user.get("name"))[:120],
               "provider": user.get("provider", "google"), "received_utc": _now(), "status": IN_REVIEW, "slug": None}
        self.store.put(doc)
        # Answering goes to the author only where Google vouches for the address.
        verified = doc["provider"] == "google" and MAILBOX.fullmatch(email)
        told = self._tell(review_message(doc, self.store.where(doc)), reply_to=email if verified else None)
        log.info("article received words=%s mailed=%s", doc["words"], told)
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
        doc = next((d for d in self.store.by(user_id) if d["id"] == id_), None)
        if not doc or not self.store.delete(user_id, id_):
            return False
        self._tell(gone_message(doc, "its author took it back"))
        return True

    def forget(self, user_id: str) -> int:
        """Deleting an account removes the articles it sent."""
        if not ACCOUNT.fullmatch(user_id):
            return 0
        mine = self.store.by(user_id)
        for doc in mine:
            if self.store.delete(user_id, doc["id"]):
                self._tell(gone_message(doc, "its author deleted their account"))
        return len(mine)
