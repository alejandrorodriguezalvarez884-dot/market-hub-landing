"""The phone app's way in: a token where a browser has a cookie. It names one user, it is not a
cookie, and a write that carries it needs no Origin, because no cookie answers for it."""

import time

import pytest
from fastapi.testclient import TestClient

from conftest import ARTICLE, CLIENT_ID, fake_verifier, sign_in
from markethub.accounts import MemoryLogins
from markethub.api import create_app
from markethub.community import MemoryCommunity
from markethub.tokens import AppTokens, bearer
from test_accounts import EMAIL, FAST, PASSWORD, register

PORTFOLIO = {"positions": [{"ticker": "AAPL", "shares": 3, "avg_cost": 150}], "watchlist": ["KO"]}


@pytest.fixture
def phone(client):
    """The app: the same service, asked with no cookie and no Origin."""
    return TestClient(client.app)


def app_sign_in(phone, email=EMAIL, password=PASSWORD):
    return phone.post("/api/app/auth/password", json={"email": email, "password": password})


def as_(token):
    return {"authorization": f"Bearer {token}"}


@pytest.fixture
def token(client, phone):
    """The token of an account made on the site (making one takes its captcha)."""
    assert register(client).status_code == 200
    r = app_sign_in(phone)
    assert r.status_code == 200, r.text
    return r.json()["token"]


# --- The token -------------------------------------------------------------------------------------


def test_a_token_says_who_signed_in_and_nothing_else_reads_as_one():
    tokens = AppTokens("a-secret", 60)
    user = {"id": "mh_1", "email": "ana@example.test", "name": "Ana", "picture": "", "provider": "password", "extra": "dropped"}
    token = tokens.issue(user)
    assert tokens.read(token) == {k: v for k, v in user.items() if k != "extra"}
    assert "ana@example.test" not in token and PASSWORD not in token  # encoded, though not secret
    for bad in (None, "", "nonsense", token[:-2], token + "x", AppTokens("another-secret", 60).issue(user)):
        assert tokens.read(bad) is None


def test_a_token_runs_out(monkeypatch):
    tokens = AppTokens("a-secret", 60)
    token = tokens.issue({"id": "mh_1"})
    assert tokens.read(token)
    later = time.time() + 61
    monkeypatch.setattr(time, "time", lambda: later)
    assert tokens.read(token) is None


@pytest.mark.parametrize("header, found", [("Bearer abc", "abc"), ("bearer  abc ", "abc"), ("Bearer", None), ("Bearer ", None),
                                           ("Basic abc", None), ("abc", None), ("", None), (None, None)])
def test_only_a_bearer_header_carries_a_token(header, found):
    assert bearer(header) == found


# --- Signing in ------------------------------------------------------------------------------------


def test_the_app_signs_in_for_a_token_and_no_cookie(client, phone, users):
    made = register(client).json()["user"]
    r = app_sign_in(phone)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"] == made and body["new"] is False and body["has_data"] is False
    assert "set-cookie" not in r.headers and not phone.cookies
    assert phone.get("/api/me").status_code == 401  # nothing but the token says who it is
    me = phone.get("/api/me", headers=as_(body["token"]))
    assert me.status_code == 200 and me.json()["user"] == made
    assert "set-cookie" not in me.headers


def test_a_wrong_password_gets_no_token_and_the_same_words(client, phone):
    register(client)
    wrong = app_sign_in(phone, password="not the password at all")
    unknown = app_sign_in(phone, email="nobody@example.test")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() and "token" not in wrong.json()


def test_the_app_cannot_sign_in_with_a_password_where_passwords_are_off(users, market, directory, monkeypatch):
    monkeypatch.setenv("MARKETHUB_PASSWORD_LOGIN", "0")
    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=CLIENT_ID, session_secret="s",
                     secure_cookies=False, community_store=MemoryCommunity(), insight_writer=None, logins=MemoryLogins(), password_cost=FAST)
    assert app_sign_in(TestClient(app)).status_code == 404


# --- Asking with it --------------------------------------------------------------------------------


def test_the_app_writes_with_its_token_and_no_origin(phone, token, users):
    r = phone.put("/api/portfolio", json=PORTFOLIO, headers=as_(token))
    assert r.status_code == 200, r.text
    saved = phone.get("/api/portfolio", headers=as_(token)).json()
    assert saved["positions"][0]["ticker"] == "AAPL" and saved["watchlist"] == ["KO"]
    d = phone.get("/api/dashboard", headers=as_(token))
    assert d.status_code == 200 and d.json()["totals"]["positions"] == 1


def test_a_write_with_no_token_or_a_bad_one_still_needs_the_origin(client, phone, token):
    for headers in ({}, as_("nonsense"), as_(token[:-2]), {"authorization": "Bearer"}, {"authorization": f"Basic {token}"}):
        assert phone.put("/api/portfolio", json=PORTFOLIO, headers=headers).status_code == 403
    # With the site's Origin a bad token passes the check, and then it is nobody's.
    assert client.put("/api/portfolio", json=PORTFOLIO, headers=as_("nonsense")).status_code == 401
    assert phone.get("/api/portfolio", headers=as_(token)).json()["positions"] == []


def test_a_token_never_borrows_a_browsers_session(client, phone, token):
    """A request that carries a token is the token's user or nobody: the cookie is not looked at."""
    sign_in(client, "77")  # the browser is now somebody else, by cookie
    client.put("/api/portfolio", json={"positions": [], "watchlist": ["MSFT"]})
    assert client.get("/api/me", headers=as_(token)).json()["user"]["email"] == EMAIL
    assert client.get("/api/portfolio", headers=as_(token)).json()["watchlist"] == []
    assert client.get("/api/me", headers=as_("nonsense")).status_code == 401
    assert client.get("/api/me").json()["user"]["id"] == "77"


def test_a_cookie_is_not_a_token_and_a_token_is_not_a_cookie(client, phone, token):
    sign_in(client, "77")
    cookie = client.cookies["mh_session"]
    assert phone.get("/api/me", headers=as_(cookie)).status_code == 401
    phone.cookies.set("mh_session", token)
    assert phone.get("/api/me").status_code == 401


def test_signing_in_as_the_app_from_a_foreign_page_leaves_no_session(client, phone):
    """The routes under /api/app/ pass no Origin check: they set no cookie, so there is nothing
    for a foreign page to plant in a browser."""
    register(client)
    client.post("/api/auth/logout")
    r = client.post("/api/app/auth/password", json={"email": EMAIL, "password": PASSWORD}, headers={"origin": "https://evil.example"})
    assert r.status_code == 200 and "set-cookie" not in r.headers
    assert client.get("/api/me").status_code == 401


def test_a_token_is_renewed_for_one_that_names_the_same_user(phone, token, monkeypatch):
    assert phone.post("/api/app/auth/renew").status_code == 401
    assert phone.post("/api/app/auth/renew", headers=as_("nonsense")).status_code == 401
    later = time.time() + 86400
    monkeypatch.setattr(time, "time", lambda: later)
    r = phone.post("/api/app/auth/renew", headers=as_(token))
    assert r.status_code == 200 and r.json()["token"] != token
    assert phone.get("/api/me", headers=as_(r.json()["token"])).json()["user"] == r.json()["user"]


def test_the_account_is_deleted_from_the_app(phone, token, users, logins):
    phone.put("/api/portfolio", json=PORTFOLIO, headers=as_(token))
    user_id = phone.get("/api/me", headers=as_(token)).json()["user"]["id"]
    assert phone.delete("/api/me", headers=as_(token)).json() == {"deleted": True}
    assert users.get(user_id) is None
    assert app_sign_in(phone).status_code == 401  # its password went with it


def test_the_app_changes_its_password(phone, token):
    new = "another long enough phrase"
    r = phone.put("/api/auth/password", json={"current": PASSWORD, "new": new}, headers=as_(token))
    assert r.status_code == 200, r.text
    assert app_sign_in(phone).status_code == 401 and app_sign_in(phone, password=new).status_code == 200


def test_a_signed_in_app_reads_a_thread_as_its_user(phone, token):
    r = phone.get("/api/public/opinion/comments", params={"slug": ARTICLE["slug"]}, headers=as_(token))
    assert r.status_code == 200 and r.json()["signed_in"] is True
    assert phone.get("/api/public/opinion/comments", params={"slug": ARTICLE["slug"]}).json()["signed_in"] is False
