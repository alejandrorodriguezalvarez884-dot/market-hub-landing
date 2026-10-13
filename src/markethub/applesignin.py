"""Sign in with Apple, from the phone app.

On an iPhone the system itself asks the user (Face ID, or the Apple account's password) and hands
the app an identity token: a JWT signed by Apple that says which Apple account, for which app.
The app posts it once to ``/api/app/auth/apple`` and the server checks it as it checks Google's:
the signature against Apple's published keys, the issuer, the audience (the app's own
identifier), the expiry, and a nonce:

    1. The app asks for a nonce (``/api/app/auth/apple/begin``): a value signed here, good for
       ten minutes, and nothing kept on the server.
    2. It passes the nonce to the system's sign-in, and Apple writes it into the token.
    3. The token is only taken with a nonce of ours that is still in time, so a token made for
       another sign-in, or kept from an old one, opens nothing.

Apple gives the name to the app, not in the token, and only the first time: the app sends it
along, and it is only ever shown back to its owner. The email may be one of Apple's relay
addresses ("Hide My Email"). Like the address of an account with a password of ours, it gives no
right here: only an address Google has verified can moderate (opinion.py).

The account's key is Apple's ``sub``, which is the same for every sign-in of that person to this
developer's apps, under a prefix of its own so it can never be taken for another kind of account.
"""

from __future__ import annotations

import base64
import re
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from google.auth import jwt
from itsdangerous import BadData, URLSafeTimedSerializer

from .auth import InvalidToken

ISSUER = "https://appleid.apple.com"
KEYS = "https://appleid.apple.com/auth/keys"
# The app's identifier (ios.bundleIdentifier in its app.json): who Apple made the token for. A
# token made for any other app, Expo Go among them, is not taken.
APP_AUDIENCE = "app.themarkethub.hub"
ID_PREFIX = "ap_"
SUB = re.compile(r"[A-Za-z0-9._-]{1,120}")
NONCE_SECONDS = 600  # from asking for the nonce to posting the token
KEYS_SECONDS = 86400  # Apple's keys change rarely; one not known yet is looked for at once
KEYS_RETRY_SECONDS = 60  # but not more often than this, whatever a token claims


@dataclass(frozen=True)
class AppleUser:
    id: str  # ours: the prefix and Apple's stable "sub"
    email: str  # as Apple gives it: maybe a relay address, maybe none


# token -> its claims, once its signature and its expiry hold. Tests pass their own.
Verifier = Callable[[str], dict]


def _number(value: str) -> int:
    return int.from_bytes(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)), "big")


def pem_keys(jwks: dict) -> dict[str, bytes]:
    """Apple's keys as google-auth takes them: each key id with its RSA public key in PEM."""
    found = {}
    for key in jwks.get("keys") or []:
        if key.get("kty") == "RSA" and key.get("kid") and key.get("n") and key.get("e"):
            public = RSAPublicNumbers(_number(key["e"]), _number(key["n"])).public_key()
            found[str(key["kid"])] = public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return found


class AppleKeys:
    """Checks a token's signature and expiry against the keys Apple publishes. They are kept for
    a day; a token signed with a key not seen yet has them read again, once a minute at most."""

    def __init__(self, client: httpx.Client | None = None, address: str = KEYS):
        self.client, self.address = client or httpx.Client(timeout=8), address
        self._keys: dict[str, bytes] = {}
        self._read = 0.0
        self._lock = threading.Lock()

    def _current(self, kid: str) -> dict[str, bytes]:
        with self._lock:
            age = time.monotonic() - self._read
            if not self._keys or age > KEYS_SECONDS or (kid not in self._keys and age > KEYS_RETRY_SECONDS):
                try:
                    answer = self.client.get(self.address)
                    answer.raise_for_status()
                    self._keys = pem_keys(answer.json()) or self._keys
                except (httpx.HTTPError, ValueError):
                    pass  # the keys we had still check the tokens they signed
                self._read = time.monotonic()
            return self._keys

    def __call__(self, token: str) -> dict:
        header = jwt.decode_header(token)
        if header.get("alg") != "RS256":
            raise ValueError("unexpected algorithm")
        keys = self._current(str(header.get("kid") or ""))
        if not keys:
            raise ValueError("Apple's keys could not be read")
        # The audience is checked by verify().
        return dict(jwt.decode(token, certs=keys, clock_skew_in_seconds=10))


class AppleFlow:
    """The nonce of one sign-in: signed here, so nothing is kept between asking and posting."""

    def __init__(self, secret: str):
        self._nonce = URLSafeTimedSerializer(secret, salt="markethub.app-apple-nonce")

    def nonce(self) -> str:
        return self._nonce.dumps(secrets.token_urlsafe(16))

    def fresh(self, nonce: str) -> bool:
        try:
            self._nonce.loads(nonce or "", max_age=NONCE_SECONDS)
        except BadData:
            return False
        return True


def verify(token: str, flow: AppleFlow, verifier: Verifier) -> AppleUser:
    try:
        claims = verifier(token)
    except ValueError as exc:  # google-auth raises ValueError for every bad token
        raise InvalidToken("invalid token") from exc
    if claims.get("iss") != ISSUER:
        raise InvalidToken("wrong issuer")
    if claims.get("aud") != APP_AUDIENCE:
        raise InvalidToken("wrong audience")
    if not flow.fresh(str(claims.get("nonce") or "")):
        raise InvalidToken("wrong nonce")
    sub = str(claims.get("sub") or "")
    if not SUB.fullmatch(sub):
        raise InvalidToken("no subject")
    # Apple writes "true" as a word in some tokens. An address it has not verified is not kept.
    verified = str(claims.get("email_verified")).lower() == "true"
    return AppleUser(id=ID_PREFIX + sub.replace(".", "-"), email=str(claims.get("email") or "") if verified else "")


def shown_name(given: str, kept: str) -> str:
    """The name of the account: what the app was given the first time, else the one kept. An
    Apple account may give none, and its address may be a relay's: then it is just a member."""
    given = " ".join(str(given or "").split())[:60]
    return given or kept or "Member"
