"""The phone app signs in with Apple: a nonce of ours, Apple's identity token carrying it, the
app's token back. The token is checked against Apple's published keys; here a key made for the
test stands for Apple's, and no test touches the network."""

import base64
import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from google.auth import crypt, jwt

from conftest import CLIENT_ID, fake_verifier
from markethub import applesignin
from markethub.api import create_app
from markethub.applesignin import APP_AUDIENCE, ISSUER, AppleFlow, AppleKeys, shown_name

SUB = "001234.0a1b2c3d4e5f60718293a4b5c6d7e8f9.1234"
OURS = "ap_001234-0a1b2c3d4e5f60718293a4b5c6d7e8f9-1234"


def _b64(number: int) -> str:
    return base64.urlsafe_b64encode(number.to_bytes((number.bit_length() + 7) // 8, "big")).decode().rstrip("=")


class Apple:
    """Stands for Apple: a signing key, the page its public half is published on, and tokens."""

    def __init__(self, kid: str = "KEY1"):
        self.kid = kid
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
        self.signer = crypt.RSASigner.from_string(pem, key_id=kid)
        self.asked = 0
        self.down = False

    def jwks(self) -> dict:
        numbers = self.key.public_key().public_numbers()
        return {"keys": [{"kty": "RSA", "kid": self.kid, "use": "sig", "alg": "RS256", "n": _b64(numbers.n), "e": _b64(numbers.e)}]}

    def client(self) -> httpx.Client:
        def answer(request: httpx.Request) -> httpx.Response:
            self.asked += 1
            return httpx.Response(503) if self.down else httpx.Response(200, json=self.jwks())
        return httpx.Client(transport=httpx.MockTransport(answer))

    def token(self, nonce: str | None, **over) -> str:
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": APP_AUDIENCE, "sub": SUB, "iat": now, "exp": now + 600, "nonce": nonce,
                  "email": "ana@icloud.com", "email_verified": "true"} | over
        return jwt.encode(self.signer, {k: v for k, v in claims.items() if v is not None}).decode()


@pytest.fixture(scope="module")
def apple():
    return Apple()


@pytest.fixture
def service(users, market, directory, apple):
    """The service as the phone reaches it: no cookie, no Origin."""
    apple.down = False
    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=CLIENT_ID,
                     session_secret="test-secret", secure_cookies=False, insight_writer=None, stock_reader=None,
                     apple_verifier=AppleKeys(apple.client()))
    return TestClient(app)


@pytest.fixture
def phone(service):
    return service


def nonce(phone) -> str:
    r = phone.post("/api/app/auth/apple/begin")
    assert r.status_code == 200, r.text
    return r.json()["nonce"]


def enter(phone, token: str, **said):
    return phone.post("/api/app/auth/apple", json={"identity_token": token} | said)


# --- The whole way ---------------------------------------------------------------------------------


def test_the_app_signs_in_with_apple_for_a_token_and_no_cookie(phone, apple, users):
    assert phone.get("/api/config").json()["apple_sign_in"] is True
    r = enter(phone, apple.token(nonce(phone)), name="  Ana   García ")
    assert r.status_code == 200, r.text
    assert "set-cookie" not in r.headers and not phone.cookies
    said = r.json()
    assert said["user"] == {"id": OURS, "email": "ana@icloud.com", "name": "Ana García", "picture": "", "provider": "apple"}
    assert said["new"] is True and said["has_data"] is False
    assert users.get(OURS)["provider"] == "apple" and users.get(OURS)["email"] == "ana@icloud.com"
    # The token is the app's session: it reads and writes as that account, with no Origin.
    with_token = {"authorization": f"Bearer {said['token']}"}
    assert phone.get("/api/me", headers=with_token).json()["user"]["id"] == OURS
    assert phone.put("/api/portfolio", json={"positions": [], "watchlist": ["AAPL"]}, headers=with_token).status_code == 200


def test_apple_gives_the_name_once_and_it_is_kept(phone, apple):
    assert enter(phone, apple.token(nonce(phone)), name="Ana García").json()["user"]["name"] == "Ana García"
    again = enter(phone, apple.token(nonce(phone))).json()
    assert again["user"]["name"] == "Ana García" and again["new"] is False


def test_an_apple_account_with_no_name_and_a_hidden_address_is_a_member(phone, apple, users):
    said = enter(phone, apple.token(nonce(phone), email="x7k2@privaterelay.appleid.com")).json()
    assert said["user"]["name"] == "Member" and said["user"]["email"] == "x7k2@privaterelay.appleid.com"
    # An address Apple has not verified, or none at all, is not kept; the one kept before stays.
    for over in ({"email_verified": "false", "email": "other@example.com"}, {"email": None, "email_verified": None}):
        assert enter(phone, apple.token(nonce(phone), **over)).json()["user"]["email"] == "x7k2@privaterelay.appleid.com"
    assert shown_name("", "") == "Member" and shown_name("  ", "Ana") == "Ana" and len(shown_name("a" * 300, "")) == 60


def test_an_apple_account_is_deleted_and_starts_again_from_nothing(phone, apple, users):
    token = enter(phone, apple.token(nonce(phone)), name="Ana").json()["token"]
    assert phone.delete("/api/me", headers={"authorization": f"Bearer {token}"}).json() == {"deleted": True}
    assert users.get(OURS) is None
    assert enter(phone, apple.token(nonce(phone))).json()["new"] is True


def test_an_apple_account_has_no_password_here_and_does_not_moderate(phone, apple):
    token = enter(phone, apple.token(nonce(phone))).json()["token"]
    with_token = {"authorization": f"Bearer {token}"}
    assert phone.put("/api/auth/password", json={"current": "x", "new": "y" * 12}, headers=with_token).status_code == 400
    assert phone.get("/api/competitions/comments", params={"month": time.strftime("%Y-%m")}, headers=with_token).json().get("moderator") is False


# --- What is refused -------------------------------------------------------------------------------


@pytest.mark.parametrize("over, why", [
    ({"aud": "com.someone.else"}, "another app's token"), ({"aud": "host.exp.Exponent"}, "Expo Go's token"),
    ({"iss": "https://accounts.google.com"}, "another issuer"), ({"exp": int(time.time()) - 3600}, "run out"),
    ({"sub": None}, "no account"), ({"sub": "../../etc/passwd"}, "not an account's id")])
def test_a_token_that_is_not_apples_for_this_app_now_opens_nothing(phone, apple, users, over, why):
    r = enter(phone, apple.token(nonce(phone), **over))
    assert r.status_code == 401 and "token" not in r.json(), why
    assert r.json()["detail"] == "Sign in with Apple could not be verified."
    assert not users.get(OURS)


def test_a_token_takes_a_nonce_of_ours_that_is_still_in_time(phone, apple, monkeypatch):
    theirs = AppleFlow("another-secret").nonce()
    assert enter(phone, apple.token(theirs)).status_code == 401
    assert enter(phone, apple.token("made-up")).status_code == 401
    assert enter(phone, apple.token(None)).status_code == 401
    ours = nonce(phone)
    monkeypatch.setattr(applesignin, "NONCE_SECONDS", -1)
    assert enter(phone, apple.token(ours)).status_code == 401


def test_a_token_signed_by_somebody_else_opens_nothing(phone, apple):
    impostor = Apple(kid=apple.kid)  # the same key id, another key
    assert enter(phone, impostor.token(nonce(phone))).status_code == 401
    stranger = Apple(kid="UNKNOWN")
    assert enter(phone, stranger.token(nonce(phone))).status_code == 401
    assert enter(phone, "not-a-token").status_code == 401
    # A token that names no signature at all ("alg": "none") is not read either.
    header, claims, _ = apple.token(nonce(phone)).split(".")
    none = base64.urlsafe_b64encode(b'{"alg":"none","kid":"KEY1"}').decode().rstrip("=")
    assert enter(phone, f"{none}.{claims}.").status_code == 401


# --- Apple's keys ----------------------------------------------------------------------------------


def test_apples_keys_are_read_once_and_kept(apple):
    keys = AppleKeys(apple.client())
    before = apple.asked
    token = apple.token("n")
    assert keys(token)["sub"] == SUB and keys(token)["sub"] == SUB
    assert apple.asked == before + 1
    # An unknown key id has them read again, but not at every token.
    stranger = Apple(kid="UNKNOWN")
    for _ in range(3):
        with pytest.raises(ValueError):
            keys(stranger.token("n"))
    assert apple.asked == before + 1


def test_when_apples_keys_cannot_be_read_nobody_signs_in_and_the_ones_kept_still_check(apple):
    apple.down = True
    try:
        cold = AppleKeys(apple.client())
        with pytest.raises(ValueError):
            cold(apple.token("n"))
    finally:
        apple.down = False
    warm = AppleKeys(apple.client())
    assert warm(apple.token("n"))["sub"] == SUB
    apple.down = True
    try:
        warm._read -= applesignin.KEYS_SECONDS + 1  # a day later, with Apple not answering
        assert warm(apple.token("n"))["sub"] == SUB
    finally:
        apple.down = False
