"""The phone app's session: a signed token, where a browser has the signed cookie.

The app signs in at ``/api/app/auth/...``, is handed a token, keeps it in the phone's keychain
and sends it with every request as ``Authorization: Bearer <token>``. The token says what the
cookie says (who signed in, and how) and lasts as long; it is signed with the same secret under
a salt of its own, so a cookie's value is not a token and a token is not a cookie's value.

Like the cookie, a token is not kept anywhere on the server: it cannot be taken back before it
runs out, only dropped by the app that holds it.
"""

from __future__ import annotations

from itsdangerous import BadData, URLSafeTimedSerializer

SALT = "markethub.app-token"
FIELDS = ("id", "email", "name", "picture", "provider")


def bearer(header: str | None) -> str | None:
    """The token of an ``Authorization: Bearer <token>`` header, or None when it carries none."""
    scheme, _, value = (header or "").partition(" ")
    return value.strip() or None if scheme.lower() == "bearer" else None


class AppTokens:
    def __init__(self, secret: str, max_age_seconds: int):
        self._signer = URLSafeTimedSerializer(secret, salt=SALT)
        self.max_age = max_age_seconds

    def issue(self, user: dict) -> str:
        return self._signer.dumps({k: user.get(k, "") for k in FIELDS})

    def read(self, token: str | None) -> dict | None:
        """The user a token was issued to, or None: not ours, changed, or run out."""
        if not token:
            return None
        try:
            user = self._signer.loads(token, max_age=self.max_age)
        except BadData:
            return None
        return user if isinstance(user, dict) and user.get("id") else None
