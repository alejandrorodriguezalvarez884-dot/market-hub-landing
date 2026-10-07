"""The phone app signs in with Google through the phone's own browser.

An app cannot show Google's button as a page does, and Google does not sign anybody in inside an
app's embedded page. So the app hands the phone's browser to us, and we hand it back:

    1. The app makes a secret, keeps it, and opens the browser at
       /api/app/auth/google/start?redirect=<its own address>&challenge=<the SHA-256 of the secret>.
    2. We send the browser on to Google, asking for an ID token for the site's own client, posted
       to /api/app/auth/google/callback.
    3. The callback checks the ID token as /api/auth/google does, and sends the browser to the
       app's address with a code that lasts two minutes.
    4. The app posts the code and its secret to /api/app/auth/google/finish and gets its token.

Nothing is kept on the server between the steps: what one step has to tell the next travels
signed (the state through Google, the code through the app's address). The code says which
account and which challenge, never an email; it is worth nothing without the secret, which only
the app that started has, and it is only ever sent to an address of the app (``AppRedirects``).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import re
import secrets
from urllib.parse import urlencode

from itsdangerous import BadData, URLSafeTimedSerializer

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
# The app's own address, where a build of the app is installed. Others are added by the service's
# settings (MARKETHUB_APP_REDIRECTS), for the app while it is run from a developer's machine.
APP_REDIRECT = "markethub://auth"
# The SHA-256 of the app's secret, in URL-safe base64 without padding (RFC 7636, "S256").
CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}")
STATE_SECONDS = 600  # from opening the browser to coming back from Google
CODE_SECONDS = 120  # from coming back to the app asking for its token


def challenge_of(secret: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()).decode().rstrip("=")


class AppRedirects:
    """The addresses a code may be sent to. Each is written whole; a ``*`` stands for letters
    and digits only, so it never reaches past a dot or a slash into somebody else's address."""

    def __init__(self, extra: str = ""):
        written = [APP_REDIRECT, *(p.strip() for p in extra.split(",") if p.strip())]
        self._patterns = [re.compile(re.escape(p).replace(r"\*", "[A-Za-z0-9]+")) for p in written]

    def allowed(self, address: str) -> bool:
        return any(p.fullmatch(address) for p in self._patterns)


class GoogleFlow:
    def __init__(self, secret: str):
        self._state = URLSafeTimedSerializer(secret, salt="markethub.app-google-state")
        self._code = URLSafeTimedSerializer(secret, salt="markethub.app-google-code")

    def begin(self, redirect: str, challenge: str) -> tuple[str, str]:
        """(state, nonce) for one sign-in: the state comes back from Google with the ID token,
        and the ID token must carry the nonce."""
        nonce = secrets.token_urlsafe(16)
        return self._state.dumps({"r": redirect, "c": challenge, "n": nonce}), nonce

    def came_back(self, state: str) -> dict | None:
        return _read(self._state, state, STATE_SECONDS, ("r", "c", "n"))

    def code(self, user_id: str, challenge: str, new: bool) -> str:
        return self._code.dumps({"i": user_id, "c": challenge, "n": bool(new)})

    def redeem(self, code: str, secret: str) -> dict | None:
        """{"i": the account, "n": whether it is new} when the code is ours, in time, and was
        made for whoever holds ``secret``."""
        found = _read(self._code, code, CODE_SECONDS, ("i", "c"))
        if not found or not hmac.compare_digest(challenge_of(secret), str(found["c"])):
            return None
        return found


def _read(signer: URLSafeTimedSerializer, value: str, seconds: int, fields: tuple[str, ...]) -> dict | None:
    try:
        found = signer.loads(value or "", max_age=seconds)
    except BadData:
        return None
    return found if isinstance(found, dict) and all(found.get(f) for f in fields) else None


def google_address(client_id: str, callback: str, state: str, nonce: str) -> str:
    """Where the browser goes to pick a Google account. An ID token is asked for, not a code:
    it needs no client secret, and it is checked like the one the site's own button gets."""
    return f"{GOOGLE_AUTH}?" + urlencode({
        "client_id": client_id, "redirect_uri": callback, "response_type": "id_token", "response_mode": "form_post",
        "scope": "openid email profile", "nonce": nonce, "state": state, "prompt": "select_account"})


def back_to_app(redirect: str, **said: str) -> str:
    return f"{redirect}{'&' if '?' in redirect else '?'}{urlencode(said)}"


def leaving_page(address: str | None, words: str) -> str:
    """The page the browser shows for a moment on its way back to the app. It goes there by
    itself; the button is for a browser that will not open an app without being asked."""
    go = ""
    if address:
        target = json.dumps(address).replace("<", "\\u003c")
        go = (f'<p><a class="b" href="{html.escape(address, quote=True)}">Return to Market Hub</a></p>'
              f"<script>location.replace({target})</script>")
    return ("<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<meta name=robots content=noindex><title>Market Hub</title>"
            "<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0c0d;color:#c9c7c1;"
            "font:16px/1.5 system-ui,sans-serif;text-align:center}main{padding:24px;max-width:22rem}"
            ".b{display:inline-block;margin-top:8px;padding:10px 18px;border-radius:3px;background:#f2f0ea;color:#0b0c0d;"
            "text-decoration:none;font-weight:500}</style>"
            f"<main><p>{html.escape(words)}</p>{go}</main></html>")
