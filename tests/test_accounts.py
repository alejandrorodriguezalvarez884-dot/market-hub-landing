"""The second way in: an email and a password kept by us. What is kept is never the password, an
address proves nothing, and wrong passwords are counted."""

import json

import pytest

from conftest import ARTICLE, sign_in
from markethub import accounts
from markethub.accounts import Accounts, MemoryLogins, Refused, TooMany, Wrong

FAST = (10, 8, 1)  # scrypt at a cost a test can afford
EMAIL, PASSWORD = "ana@example.test", "a long enough test phrase"


def desk():
    return Accounts(MemoryLogins(), FAST)


def register(client, email=EMAIL, password=PASSWORD, name="Ana Test", captcha="human"):
    return client.post("/api/auth/register", json={"email": email, "password": password, "name": name, "captcha": captcha})


def enter(client, email=EMAIL, password=PASSWORD):
    return client.post("/api/auth/password", json={"email": email, "password": password})


# --- What is kept ----------------------------------------------------------------------------------


def test_a_password_is_kept_as_a_salted_hash_that_says_its_cost():
    one, two = accounts.hash_password(PASSWORD, FAST), accounts.hash_password(PASSWORD, FAST)
    assert one != two and PASSWORD not in one and one.startswith("scrypt$10$8$1$")
    assert accounts.check_password(PASSWORD, one) and accounts.check_password(PASSWORD, two)
    assert not accounts.check_password(PASSWORD + " ", one) and not accounts.check_password("", one)
    # What is not a hash of ours checks nothing, and asks for no work.
    for stored in ("", "plain", "scrypt$30$8$1$abcd$abcd", "md5$1$1$1$abcd$abcd", "scrypt$x$8$1$a$b"):
        assert not accounts.check_password(PASSWORD, stored)
    assert accounts.COST == (15, 8, 3) and accounts.made_at(accounts.hash_password("x" * 12, FAST)) == FAST


def test_an_account_has_an_id_of_its_own_and_its_address_is_one_whatever_its_case():
    d = desk()
    user = d.register("  Ana@Example.Test ", PASSWORD, "  Ana   Test ")
    assert user["id"].startswith("mh_") and "@" not in user["id"] and user["provider"] == "password"
    assert user["email"] == "Ana@Example.Test" and user["name"] == "Ana Test" and user["picture"] == ""
    assert d.sign_in("ana@example.test", PASSWORD)["id"] == user["id"] == d.sign_in("ANA@EXAMPLE.TEST", PASSWORD)["id"]
    with pytest.raises(Refused, match="already"):
        d.register("ANA@example.test", PASSWORD, "Someone Else")
    kept = json.dumps(d.store.docs)
    assert PASSWORD not in kept and "scrypt$" in kept


@pytest.mark.parametrize("email", ["", "ana", "ana@", "@example.test", "ana@example", "ana example@x.test", "a@b\n.test","x" * 250 + "@example.test"])
def test_what_is_not_an_address(email):
    with pytest.raises(Refused, match="email"):
        desk().register(email, PASSWORD, "Ana")


@pytest.mark.parametrize("password", ["short", "123456789", "1234567890", "password123", "aaaaaaaaaaaa", "ANA@example.test", "x" * 201])
def test_passwords_that_are_refused(password):
    with pytest.raises(Refused, match="password|Pick"):
        desk().register("ana@example.test", password, "Ana")


def test_a_name_is_needed_and_kept_clean():
    with pytest.raises(Refused, match="name"):
        desk().register(EMAIL, PASSWORD, "   ")
    with pytest.raises(Refused, match="name"):
        desk().register(EMAIL, PASSWORD, "x" * 61)
    assert desk().register(EMAIL, PASSWORD, "Ana\x00\x07 <b>Test</b>")["name"] == "Ana <b>Test</b>"  # shown as text, never as markup


def test_wrong_is_wrong_whoever_asks_and_too_many_wait():
    d = desk()
    d.register(EMAIL, PASSWORD, "Ana")
    with pytest.raises(Wrong):
        d.sign_in(EMAIL, "not the password")
    with pytest.raises(Wrong):
        d.sign_in("nobody@example.test", PASSWORD)  # no account: the same answer
    d.sign_in(EMAIL, PASSWORD)  # a right one clears the count
    for _ in range(accounts.ATTEMPTS):
        with pytest.raises(Wrong):
            d.sign_in(EMAIL, "guess")
    with pytest.raises(TooMany):
        d.sign_in(EMAIL, PASSWORD)  # even the right one waits now
    d._wrong.clear()
    assert d.sign_in(EMAIL, PASSWORD)


def test_a_hash_made_at_an_older_cost_is_remade_on_the_next_sign_in():
    store = MemoryLogins()
    Accounts(store, (10, 8, 1)).register(EMAIL, PASSWORD, "Ana")
    newer = Accounts(store, (11, 8, 1))
    assert newer.sign_in(EMAIL, PASSWORD) and accounts.made_at(store.get(accounts.email_key(EMAIL))["password"]) == (11, 8, 1)
    assert newer.sign_in(EMAIL, PASSWORD)


def test_changing_a_password_takes_the_current_one():
    d = desk()
    d.register(EMAIL, PASSWORD, "Ana")
    with pytest.raises(Wrong):
        d.change_password(EMAIL, "not it", "another long enough phrase")
    with pytest.raises(Refused):
        d.change_password(EMAIL, PASSWORD, "short")
    with pytest.raises(Refused, match="already"):
        d.change_password(EMAIL, PASSWORD, PASSWORD)
    d.change_password(EMAIL, PASSWORD, "another long enough phrase")
    with pytest.raises(Wrong):
        d.sign_in(EMAIL, PASSWORD)
    assert d.sign_in(EMAIL, "another long enough phrase")


# --- Through the API -------------------------------------------------------------------------------


def test_registering_opens_a_session_like_any_other(client, users, logins):
    assert client.get("/api/config").json()["password_login"] is True
    made = register(client)
    assert made.status_code == 200 and made.json()["new"] is True and made.json()["has_data"] is False
    me = client.get("/api/me").json()["user"]
    assert me == made.json()["user"] and me["provider"] == "password" and me["email"] == EMAIL and me["name"] == "Ana Test"
    assert users.get(me["id"])["email"] == EMAIL and "password" not in users.get(me["id"])
    cookie = made.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and PASSWORD not in made.text
    # The account works like one from Google: a portfolio, its dashboard.
    client.put("/api/portfolio", json={"positions": [{"ticker": "AAPL", "shares": 2, "avg_cost": 100}], "watchlist": []})
    assert client.get("/api/dashboard").json()["totals"]["value"] == pytest.approx(400)
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401
    back = enter(client).json()
    assert back["new"] is False and back["has_data"] is True and back["user"]["id"] == me["id"]
    assert PASSWORD not in json.dumps(logins.docs)


def test_what_the_api_refuses(client):
    assert register(client, password="short").status_code == 400
    assert register(client, email="not an address").status_code == 400
    assert client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD, "captcha": "human"}).status_code == 422  # no name
    assert register(client).status_code == 200
    assert register(client).status_code == 400  # the address is taken
    client.post("/api/auth/logout")
    wrong, nobody = enter(client, password="not the password"), enter(client, email="nobody@example.test")
    assert wrong.status_code == nobody.status_code == 401 and wrong.json() == nobody.json()  # which of the two is not said
    assert client.get("/api/me").status_code == 401
    forged = client.post("/api/auth/password", json={"email": EMAIL, "password": PASSWORD}, headers={"origin": "https://evil.example"})
    assert forged.status_code == 403


def test_wrong_passwords_and_new_accounts_are_counted(client):
    register(client)
    client.post("/api/auth/logout")
    for _ in range(accounts.ATTEMPTS):
        assert enter(client, password="a wrong guess").status_code == 401
    assert enter(client).status_code == 429  # this address waits
    assert enter(client, email="other@example.test").status_code == 401  # another is still answered
    made = [register(client, email=f"user{i}@example.test").status_code for i in range(6)]
    assert made == [200, 200, 200, 200, 429, 429]  # five an hour from one place, and one was made above


def test_an_address_proves_nothing_so_it_grants_nothing(client, opinion):
    # Anyone can register the owner's address: it must not make them the owner.
    register(client, email="owner@gmail.com")
    thread = client.get("/api/public/opinion/comments", params={"slug": ARTICLE["slug"]}).json()
    assert thread["signed_in"] is True and thread["moderator"] is False
    assert opinion.can_moderate({"id": "g1", "email": "owner@gmail.com", "provider": "google"}) is True
    assert opinion.can_moderate({"id": "g1", "email": "owner@gmail.com"}) is True  # a session from before there were two ways in
    # And it is another account than the Google one with the same address.
    mine = client.get("/api/me").json()["user"]["id"]
    client.post("/api/auth/logout")
    assert sign_in(client)["user"]["id"] != mine


def test_changing_the_password_and_deleting_the_account(client, logins, users):
    user = register(client).json()["user"]
    assert client.put("/api/auth/password", json={"current": "not it", "new": "another long enough phrase"}).status_code == 401
    assert client.put("/api/auth/password", json={"current": PASSWORD, "new": "short"}).status_code == 400
    assert client.put("/api/auth/password", json={"current": PASSWORD, "new": "another long enough phrase"}).json() == {"changed": True}
    client.post("/api/auth/logout")
    assert enter(client).status_code == 401 and enter(client, password="another long enough phrase").status_code == 200
    assert client.delete("/api/me").json() == {"deleted": True}
    assert users.get(user["id"]) is None and logins.docs == {}
    assert enter(client, password="another long enough phrase").status_code == 401
    assert register(client).status_code == 200  # the address is free again
    # A Google account has no password to change, and deleting it touches no one's password.
    client.post("/api/auth/logout")
    sign_in(client)
    assert client.put("/api/auth/password", json={"current": "x", "new": "another long enough phrase"}).status_code == 400
    client.delete("/api/me")
    assert len(logins.docs) == 1


def test_making_an_account_takes_a_captcha_and_it_is_checked_first(client, captcha, logins):
    cfg = client.get("/api/config").json()
    assert cfg["registration"] == "captcha" and cfg["turnstile_site_key"] == "test-site-key"
    # No token, or one Cloudflare does not vouch for: nothing is made, and nothing is said of the rest.
    for token in ("", "a robot"):
        refused = register(client, password="short", captcha=token)
        assert refused.status_code == 400 and "person" in refused.json()["detail"] and "password" not in refused.json()["detail"]
    assert client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD, "name": "Ana"}).status_code == 400
    assert logins.docs == {} and client.get("/api/me").status_code == 401
    assert register(client).status_code == 200
    # It was asked with the token and the address the request came from; signing in asks for none.
    assert captcha.asked[-1] == ("human", "testclient")
    asked = len(captcha.asked)
    client.post("/api/auth/logout")
    assert enter(client).status_code == 200 and len(captcha.asked) == asked


def app_with(users, market, directory, **kw):
    from fastapi.testclient import TestClient

    from conftest import CLIENT_ID, ORIGIN, fake_verifier
    from markethub.api import create_app
    from markethub.community import MemoryCommunity

    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=CLIENT_ID, session_secret="s",
                     secure_cookies=False, community_store=MemoryCommunity(), insight_writer=None, logins=MemoryLogins(), password_cost=FAST, **kw)
    c = TestClient(app)
    c.headers.update({"origin": ORIGIN})
    return c


def test_with_no_captcha_no_accounts_are_made_unless_the_machine_says_so(users, market, directory, monkeypatch):
    monkeypatch.delenv("MARKETHUB_OPEN_REGISTRATION", raising=False)
    closed = app_with(users, market, directory, captcha=None)
    cfg = closed.get("/api/config").json()
    assert cfg["registration"] == "closed" and cfg["turnstile_site_key"] is None and cfg["password_login"] is True
    assert register(closed).status_code == 403 and enter(closed).status_code == 401  # signing in is still answered
    monkeypatch.setenv("MARKETHUB_OPEN_REGISTRATION", "1")
    opened = app_with(users, market, directory, captcha=None)
    assert opened.get("/api/config").json()["registration"] == "open" and register(opened, captcha="").status_code == 200


def test_what_cloudflare_is_asked_and_what_counts_as_a_pass():
    import httpx

    from markethub.captcha import Turnstile

    seen = []

    def cloudflare(request: httpx.Request) -> httpx.Response:
        form = dict(pair.split("=") for pair in request.content.decode().split("&"))
        seen.append(form)
        if form["response"] == "down":
            raise httpx.ConnectError("no route")
        if form["response"] == "garbled":
            return httpx.Response(200, text="<html>")
        if form["response"] == "elsewhere":
            return httpx.Response(200, json={"success": True, "action": "login"})
        return httpx.Response(200, json={"success": form["response"] == "good", "action": "register", "error-codes": ["invalid-input-response"]})

    t = Turnstile("site", "the-secret", httpx.Client(transport=httpx.MockTransport(cloudflare)))
    assert t.passes("good", "203.0.113.7") is True
    assert seen[-1] == {"secret": "the-secret", "response": "good", "remoteip": "203.0.113.7"}
    assert t.passes("bad") is False and "remoteip" not in seen[-1]
    # A check that cannot be made is a check that failed; so is a token made for something else.
    assert t.passes("down") is False and t.passes("garbled") is False and t.passes("elsewhere") is False
    asked = len(seen)
    assert t.passes("") is False and t.passes("x" * 3000) is False and len(seen) == asked  # not worth asking


def test_it_can_be_turned_off(users, market, directory, monkeypatch):
    from fastapi.testclient import TestClient

    from conftest import CLIENT_ID, ORIGIN, fake_verifier
    from markethub.api import create_app
    from markethub.community import MemoryCommunity

    monkeypatch.setenv("MARKETHUB_PASSWORD_LOGIN", "0")
    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=CLIENT_ID, session_secret="s",
                     secure_cookies=False, community_store=MemoryCommunity(), insight_writer=None, logins=MemoryLogins(), password_cost=FAST)
    c = TestClient(app)
    c.headers.update({"origin": ORIGIN})
    assert c.get("/api/config").json()["password_login"] is False
    assert c.get("/api/config").json()["registration"] == "closed"
    assert register(c).status_code == 403 and enter(c).status_code == 404
