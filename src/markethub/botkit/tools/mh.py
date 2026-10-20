#!/usr/bin/env python3
"""Talk to Market Hub about your bot: check it, backtest it, send it in, see how it is doing.

    python tools/mh.py check     [bot.json]
    python tools/mh.py backtest  [bot.json] [--years 1|2|3]
    python tools/mh.py submit    [bot.json] [--handle "your name"]
    python tools/mh.py status
    python tools/mh.py spec

Reads MARKETHUB_URL and MARKETHUB_BOT_KEY from the .env file next to this folder (or from the
environment). Standard library only: any Python 3.9 or later runs it. Prints the answer as JSON.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def settings() -> tuple[str, str]:
    values = {}
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip('"').strip("'")
    url = os.environ.get("MARKETHUB_URL") or values.get("MARKETHUB_URL") or "https://themarkethub.app"
    key = os.environ.get("MARKETHUB_BOT_KEY") or values.get("MARKETHUB_BOT_KEY") or ""
    return url.rstrip("/"), key


def ask(method: str, path: str, body: dict | None = None, key: str = "") -> int:
    url, stored = settings()
    key = key or stored
    if path != "/api/bot/spec" and not key:
        print(json.dumps({"error": "No key: put MARKETHUB_BOT_KEY in .env (create it on the Bot competition page of My Hub)."}))
        return 2
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url + path, data=data, method=method, headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            print(json.dumps(json.loads(resp.read() or b"{}"), indent=2))
            return 0
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}")
        except ValueError:
            detail = {}
        print(json.dumps({"status": exc.code, **(detail if isinstance(detail, dict) else {"detail": detail})}, indent=2))
        return 1
    except urllib.error.URLError as exc:
        print(json.dumps({"error": f"Could not reach {url}: {exc.reason}"}))
        return 1


def bot(args: list[str]) -> dict:
    path = next((a for a in args if a.endswith(".json")), "bot.json")
    return json.loads((HERE / path if not Path(path).is_absolute() else Path(path)).read_text(encoding="utf-8"))


def option(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("check", "backtest", "submit", "status", "spec"):
        print(__doc__)
        return 2
    what, rest = argv[0], argv[1:]
    if what == "spec":
        return ask("GET", "/api/bot/spec")
    if what == "status":
        return ask("GET", "/api/bot")
    if what == "check":
        return ask("POST", "/api/bot/check", {"bot": bot(rest)})
    if what == "backtest":
        return ask("POST", "/api/bot/backtest", {"bot": bot(rest), "years": int(option(rest, "--years") or 1)})
    body = {"bot": bot(rest)}
    if option(rest, "--handle"):
        body["handle"] = option(rest, "--handle")
    return ask("PUT", "/api/bot", body)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
