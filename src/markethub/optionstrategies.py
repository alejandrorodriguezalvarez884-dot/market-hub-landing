"""The option strategies a user keeps in Options Lab (``market-hub-options``).

That service writes them: one document per user, under the same account id as the user's own
document, in the collection ``option_strategies`` of this same database. The portal only reads
them, for the account page to list and download, and deletes them with the account.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Protocol

from .config import DATA_DIR, FIRESTORE_DATABASE, OPTION_STRATEGIES_COLLECTION


class OptionStrategies(Protocol):
    def get(self, user_id: str) -> list[dict]: ...
    def forget(self, user_id: str) -> None: ...


class MemoryOptionStrategies:
    def __init__(self):
        self.docs: dict[str, dict] = {}

    def get(self, user_id: str) -> list[dict]:
        return json.loads(json.dumps(self.docs.get(user_id, {}).get("strategies", [])))

    def forget(self, user_id: str) -> None:
        self.docs.pop(user_id, None)


class FileOptionStrategies:
    """For local development only: one JSON file per user under data/option_strategies (empty
    unless put there by hand: Options Lab keeps its own folder when it runs without Firestore)."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root or DATA_DIR / "option_strategies")

    def _path(self, user_id: str) -> Path:
        return self.root / f"{re.sub(r'[^A-Za-z0-9_-]', '_', user_id)}.json"

    def get(self, user_id: str) -> list[dict]:
        path = self._path(user_id)
        return json.loads(path.read_text()).get("strategies", []) if path.exists() else []

    def forget(self, user_id: str) -> None:
        self._path(user_id).unlink(missing_ok=True)


class FirestoreOptionStrategies:
    def __init__(self, collection: str = OPTION_STRATEGIES_COLLECTION, database: str = FIRESTORE_DATABASE):
        from google.cloud import firestore

        self.collection = firestore.Client(database=database).collection(collection)

    def get(self, user_id: str) -> list[dict]:
        snap = self.collection.document(user_id).get()
        return (snap.to_dict() or {}).get("strategies", []) if snap.exists else []

    def forget(self, user_id: str) -> None:
        self.collection.document(user_id).delete()


def default_option_strategies() -> OptionStrategies:
    return FirestoreOptionStrategies() if os.environ.get("MARKETHUB_FIRESTORE") == "1" else FileOptionStrategies()
