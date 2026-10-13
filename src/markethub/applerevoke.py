"""Telling Apple that an account is gone.

Somebody who signed in with Apple and deletes their account here still has the app listed, on
their iPhone, among the apps that use their Apple account. Apple asks apps to take that down too
("revoke the user's tokens"). Nothing is kept for it: at the moment of deleting, the app has the
phone ask its owner once more (Face ID) and posts what Apple hands it,

    POST /api/app/auth/apple/revoke   {identity_token, authorization_code}

The identity token is checked as at sign-in (applesignin.py) and must be of the very account
that is signed in; the code, good for five minutes and once, is traded with Apple for a token,
and that token is revoked there and then. Neither is stored or logged.

Apple takes these two calls only from whoever holds the developer's key for Sign in with Apple
(a .p8 file, with its key id and the team's id): they are signed with it. The key lives in
Secret Manager and reaches the service as APPLE_PRIVATE_KEY; without it, or without
APPLE_KEY_ID and APPLE_TEAM_ID, the route answers that there is nothing to do here and the
account is deleted all the same.
"""

from __future__ import annotations

import base64
import json
import os
import time

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from .applesignin import APP_AUDIENCE, ISSUER

TOKEN = "https://appleid.apple.com/auth/token"
REVOKE = "https://appleid.apple.com/auth/revoke"
SECRET_SECONDS = 300  # how long each signed request is good for; Apple allows up to six months


class NotRevoked(Exception):
    """Apple did not take the code, or did not answer."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


class AppleRevoker:
    def __init__(self, team_id: str, key_id: str, private_key: str, client: httpx.Client | None = None, client_id: str = APP_AUDIENCE):
        self.team_id, self.key_id, self.client_id = team_id, key_id, client_id
        self._key = serialization.load_pem_private_key(private_key.replace("\\n", "\n").encode(), password=None)
        if not isinstance(self._key, ec.EllipticCurvePrivateKey):
            raise ValueError("the Sign in with Apple key is not an elliptic-curve key")
        self.client = client or httpx.Client(timeout=10)

    def client_secret(self) -> str:
        """What stands for a password with Apple: a short-lived JWT signed with the developer's key."""
        now = int(time.time())
        head = _b64(json.dumps({"alg": "ES256", "kid": self.key_id}, separators=(",", ":")).encode())
        body = _b64(json.dumps({"iss": self.team_id, "iat": now, "exp": now + SECRET_SECONDS, "aud": ISSUER, "sub": self.client_id},
                               separators=(",", ":")).encode())
        r, s = decode_dss_signature(self._key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
        return f"{head}.{body}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"

    def _post(self, address: str, **fields: str) -> httpx.Response:
        try:
            return self.client.post(address, data={"client_id": self.client_id, "client_secret": self.client_secret(), **fields})
        except httpx.HTTPError:
            raise NotRevoked("Apple did not answer") from None

    def revoke(self, authorization_code: str) -> None:
        """Trade the code the phone was just given for a token, and have Apple revoke it."""
        answer = self._post(TOKEN, code=authorization_code, grant_type="authorization_code")
        try:
            tokens = answer.json() if answer.status_code == 200 else {}
        except ValueError:
            tokens = {}
        token, hint = (tokens.get("refresh_token"), "refresh_token") if tokens.get("refresh_token") else (tokens.get("access_token"), "access_token")
        if not token:
            raise NotRevoked("Apple did not take the code")
        if self._post(REVOKE, token=str(token), token_type_hint=hint).status_code != 200:
            raise NotRevoked("Apple did not revoke the token")


def default_revoker() -> AppleRevoker | None:
    team, key_id, key = (os.environ.get(n, "").strip() for n in ("APPLE_TEAM_ID", "APPLE_KEY_ID", "APPLE_PRIVATE_KEY"))
    if not (team and key_id and key):
        return None
    return AppleRevoker(team, key_id, key)
