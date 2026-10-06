"""Sign in with an email and a password, kept by us.

The other way in besides Google. Someone registers with an email address, a name and a password,
and gets an account of their own: an id made here (never the email), under which their document
lives like anybody else's.

What is kept of a password is never the password: a salted scrypt hash, with the cost it was made
at, so the cost can be raised later and old hashes still be checked. Hashing is slow on purpose,
which is also why attempts are counted: a wrong password costs the server as much as a right one.

Two things this does not do, and what follows from each:

- It sends no email, so **an address is not verified**: whoever registers with it first has it.
  Nothing may therefore be granted on the strength of a password account's email (the owner's
  rights, say: see ``Opinion.can_moderate``), and an account here is a different account from a
  Google one with the same address.
- For the same reason **there is no "forgot my password"**. The sign-in page says so before a
  password is chosen. Changing it takes the current one.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .config import DATA_DIR, FIRESTORE_DATABASE

# An address as people write them; whether it exists is not something we can know.
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~\-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)+")
EMAIL_MAX = 254
NAME_MAX = 60
PASSWORD_MIN, PASSWORD_MAX = 10, 200
# scrypt's cost as (log2 N, r, p): 32 MB and about a quarter of a second, OWASP's third setting.
COST = (15, 8, 3)
COST_CEILING = 17  # a stored hash asking for more than this is not ours
# Wrong passwords for one address before it has to wait, and for how long they count.
ATTEMPTS, ATTEMPTS_WINDOW = 8, 15 * 60
# The passwords of ten characters or more that head every list of leaked ones.
COMMON = {"1234567890", "0123456789", "12345678910", "123456789a", "1q2w3e4r5t", "qwertyuiop", "qwerty12345", "qwerty123456", "password12",
          "password123", "password1234", "passw0rd123", "iloveyou12", "iloveyou123", "1234512345", "1234554321", "0987654321", "9876543210",
          "abcdefghij", "abc1234567", "letmein123", "welcome123", "admin12345", "administrator", "changeme123", "markethub123", "1qaz2wsx3edc"}


class Refused(ValueError):
    """What was sent cannot be taken, with the reason to tell the person."""


class Wrong(Exception):
    """The address or the password is not right. Which of the two is never said."""


class TooMany(Exception):
    """Too many wrong passwords for this address: it has to wait."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clean_email(raw) -> str:
    email = str(raw or "").strip()
    if len(email) > EMAIL_MAX or not EMAIL.fullmatch(email):
        raise Refused("That does not look like an email address.")
    return email


def email_key(email: str) -> str:
    """Where an address is kept: one way of writing it for all its spellings, and no address in
    a document's name."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def clean_name(raw) -> str:
    name = " ".join("".join(c for c in str(raw or "") if c.isprintable()).split())
    if not 1 <= len(name) <= NAME_MAX:
        raise Refused(f"Tell us a name to call you by, of up to {NAME_MAX} characters.")
    return name


def check_strength(password, email: str = "") -> str:
    password = str(password or "")
    if len(password) < PASSWORD_MIN:
        raise Refused(f"The password needs at least {PASSWORD_MIN} characters.")
    if len(password) > PASSWORD_MAX:
        raise Refused(f"The password can have up to {PASSWORD_MAX} characters.")
    low = password.lower()
    if low in COMMON or len(set(password)) < 4:
        raise Refused("That password is one of the first anyone would try. Pick another.")
    if email and (low == email.lower() or low == email.lower().split("@")[0]):
        raise Refused("The password cannot be your email address.")
    return password


# --- Hashing -----------------------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _scrypt(password: str, salt: bytes, cost: tuple[int, int, int]) -> bytes:
    log_n, r, p = cost
    return hashlib.scrypt(password.encode(), salt=salt, n=2 ** log_n, r=r, p=p, dklen=32, maxmem=2 ** (log_n + 8) * r + 2 ** 20)


def hash_password(password: str, cost: tuple[int, int, int] = COST) -> str:
    """"scrypt$<log2 N>$<r>$<p>$<salt>$<hash>": everything needed to check it again."""
    salt = secrets.token_bytes(16)
    return "$".join(["scrypt", *map(str, cost), _b64(salt), _b64(_scrypt(password, salt, cost))])


def check_password(password: str, stored: str) -> bool:
    try:
        scheme, log_n, r, p, salt, digest = stored.split("$")
        cost = (int(log_n), int(r), int(p))
        if scheme != "scrypt" or not 10 <= cost[0] <= COST_CEILING or not 1 <= cost[1] <= 16 or not 1 <= cost[2] <= 8:
            return False
        return hmac.compare_digest(_scrypt(password, _unb64(salt), cost), _unb64(digest))
    except (ValueError, TypeError):
        return False


def made_at(stored: str) -> tuple[int, int, int] | None:
    try:
        _, log_n, r, p, _, _ = stored.split("$")
        return int(log_n), int(r), int(p)
    except ValueError:
        return None


# --- Stores ------------------------------------------------------------------------------------


class LoginStore(Protocol):
    def get(self, key: str) -> dict | None: ...
    def put(self, key: str, doc: dict) -> None: ...
    def add(self, key: str, doc: dict) -> bool: ...
    def delete(self, key: str) -> None: ...


class MemoryLogins:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        doc = self.docs.get(key)
        return dict(doc) if doc else None

    def put(self, key: str, doc: dict) -> None:
        self.docs[key] = dict(doc)

    def add(self, key: str, doc: dict) -> bool:
        """Keep ``doc`` unless the address is taken. True if it was kept."""
        with self._lock:
            if key in self.docs:
                return False
            self.docs[key] = dict(doc)
            return True

    def delete(self, key: str) -> None:
        self.docs.pop(key, None)


class FileLogins:
    """For local development only: one JSON file per address under data/logins."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "logins")
        self._lock = threading.Lock()

    def _path(self, key: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{64}", key):
            raise ValueError("bad key")
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def put(self, key: str, doc: dict) -> None:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            self._path(key).write_text(json.dumps(doc), encoding="utf-8")

    def add(self, key: str, doc: dict) -> bool:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            try:
                with self._path(key).open("x", encoding="utf-8") as f:
                    f.write(json.dumps(doc))
            except FileExistsError:
                return False
            return True

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class FirestoreLogins:
    def __init__(self, database: str = FIRESTORE_DATABASE):
        from google.api_core.exceptions import AlreadyExists
        from google.cloud import firestore

        self.collection = firestore.Client(database=database).collection("logins")
        self.taken = AlreadyExists

    def get(self, key: str) -> dict | None:
        snap = self.collection.document(key).get()
        return snap.to_dict() if snap.exists else None

    def put(self, key: str, doc: dict) -> None:
        self.collection.document(key).set(doc)

    def add(self, key: str, doc: dict) -> bool:
        # create() fails if the document is there: two people registering one address at the same
        # moment cannot both get it.
        try:
            self.collection.document(key).create(doc)
        except self.taken:
            return False
        return True

    def delete(self, key: str) -> None:
        self.collection.document(key).delete()


def default_logins() -> LoginStore:
    return FirestoreLogins() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileLogins()


# --- The desk ----------------------------------------------------------------------------------


class Accounts:
    def __init__(self, store: LoginStore, cost: tuple[int, int, int] = COST):
        self.store, self.cost = store, cost
        # Checked when the address is not known, so that answer takes as long as the other.
        self._nobody = hash_password(secrets.token_urlsafe(16), cost)
        self._wrong: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    @staticmethod
    def _user(doc: dict) -> dict:
        """The account as the session carries it. ``provider`` says the address is not verified."""
        return {"id": doc["user_id"], "email": doc["email"], "name": doc["name"], "picture": "", "provider": "password"}

    def register(self, email, password, name) -> dict:
        email = clean_email(email)
        name = clean_name(name)
        password = check_strength(password, email)
        doc = {"user_id": "mh_" + secrets.token_urlsafe(15), "email": email, "name": name, "password": hash_password(password, self.cost),
               "created_utc": _now(), "changed_utc": _now()}
        if not self.store.add(email_key(email), doc):
            raise Refused("There is already an account with that email. Sign in instead.")
        return self._user(doc)

    def _waiting(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tries = self._wrong[key]
            while tries and now - tries[0] > ATTEMPTS_WINDOW:
                tries.popleft()
            if not tries:
                self._wrong.pop(key, None)
            return len(tries) >= ATTEMPTS

    def sign_in(self, email, password) -> dict:
        key = email_key(str(email or ""))
        if self._waiting(key):
            raise TooMany
        doc = self.store.get(key)
        right = check_password(str(password or "")[:PASSWORD_MAX], doc["password"] if doc else self._nobody)
        if not doc or not right:
            with self._lock:
                self._wrong[key].append(time.monotonic())
            raise Wrong
        with self._lock:
            self._wrong.pop(key, None)
        if made_at(doc["password"]) != self.cost:  # made at an older cost: it is remade now that we have the password
            doc["password"] = hash_password(str(password), self.cost)
            self.store.put(key, doc)
        return self._user(doc)

    def change_password(self, email: str, current, new) -> None:
        key = email_key(email)
        if self._waiting(key):
            raise TooMany
        doc = self.store.get(key)
        if not doc or not check_password(str(current or "")[:PASSWORD_MAX], doc["password"]):
            with self._lock:
                self._wrong[key].append(time.monotonic())
            raise Wrong
        new = check_strength(new, doc["email"])
        if new == str(current):
            raise Refused("That is the password you already have.")
        self.store.put(key, {**doc, "password": hash_password(new, self.cost), "changed_utc": _now()})

    def forget(self, user: dict) -> None:
        """Deleting an account takes its way in with it. Only the account's own: the address of a
        Google account names nothing here."""
        if user.get("provider") != "password":
            return
        key = email_key(user.get("email", ""))
        doc = self.store.get(key)
        if doc and doc.get("user_id") == user.get("id"):
            self.store.delete(key)
