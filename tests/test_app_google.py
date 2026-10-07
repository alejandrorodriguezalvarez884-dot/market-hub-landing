"""The phone app signs in with Google through the phone's browser: start, Google, back with a
code, the code for a token. The code only goes to an address of the app, and is only good for
the app that began."""

import re
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from conftest import CLIENT_ID, fake_verifier, sign_in
from markethub.api import create_app
from markethub.appsignin import APP_REDIRECT, AppRedirects, GoogleFlow, challenge_of, leaving_page

SECRET = "s" * 43  # what the app keeps; its SHA-256 is the challenge
EXPO = "exp://ab12cd-ana-8081.exp.direct/--/auth"


@pytest.fixture
def service(users, market, directory):
    """Makes the service as the phone reaches it: no cookie, no Origin, redirects left unfollowed."""
    def make(allowed: str = "", client_id: str = CLIENT_ID) -> TestClient:
        app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=client_id,
                         session_secret="test-secret", secure_cookies=False, insight_writer=None, stock_reader=None, app_redirects=allowed)
        return TestClient(app, follow_redirects=False)
    return make


@pytest.fixture
def phone(service):
    return service("exp://*-ana-8081.exp.direct/--/auth")


def start(phone, redirect=APP_REDIRECT, secret=SECRET):
    return phone.get("/api/app/auth/google/start", params={"redirect": redirect, "challenge": challenge_of(secret)})


def at_google(response):
    """What the browser was sent to Google with."""
    assert response.status_code == 302, response.text
    where = urlsplit(response.headers["location"])
    return where, {k: v[0] for k, v in parse_qs(where.query).items()}


def come_back(phone, asked, sub="2001", **over):
    """Google posting the ID token of the account the user picked."""
    form = {"state": asked["state"], "id_token": f"ok:{sub}:{asked['nonce']}"} | over
    return phone.post("/api/app/auth/google/callback", data={k: v for k, v in form.items() if v is not None})


def sent_to(response):
    """The address the page takes the browser to, and what it says there."""
    found = re.search(r'href="([^"]+)"', response.text)
    assert found, response.text
    where = found.group(1).replace("&amp;", "&")
    return where.split("?")[0], {k: v[0] for k, v in parse_qs(where.split("?", 1)[1]).items()}


def finish(phone, code, secret=SECRET):
    return phone.post("/api/app/auth/google/finish", json={"code": code, "verifier": secret})


# --- Where a code may go -----------------------------------------------------------------------------


def test_only_the_apps_own_addresses_are_ways_back():
    only = AppRedirects()
    assert only.allowed("markethub://auth")
    for other in ("markethub://auth/x", "markethub://authx", "https://evil.example/auth", "exp://192.168.0.2:8081/--/auth", "", "markethub://auth?x=1"):
        assert not only.allowed(other)
    dev = AppRedirects(" exp://*-ana-8081.exp.direct/--/auth , ")
    assert dev.allowed("markethub://auth") and dev.allowed(EXPO)
    # The star is letters and digits: it does not reach into another name, host or path.
    for other in ("exp://ab12cd-eve-8081.exp.direct/--/auth", "exp://evil.example/x-ana-8081.exp.direct/--/auth",
                  "exp://a.b-ana-8081.exp.direct/--/auth", "exp://-ana-8081.exp.direct/--/auth", "exp://ab-ana-8081xexpxdirect/--/auth",
                  "exp://ab12cd-ana-8081.exp.direct/--/auth/more"):
        assert not dev.allowed(other)


def test_start_sends_the_browser_to_google_for_an_id_token(phone):
    where, asked = at_google(start(phone))
    assert f"{where.scheme}://{where.netloc}{where.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    assert asked["client_id"] == CLIENT_ID and asked["response_type"] == "id_token" and asked["response_mode"] == "form_post"
    assert asked["redirect_uri"] == "http://testserver/api/app/auth/google/callback"
    assert asked["scope"] == "openid email profile" and len(asked["nonce"]) >= 16
    assert SECRET not in where.query and "set-cookie" not in start(phone).headers
    # Behind the domain, the way back from Google is the domain's, over https.
    _, there = at_google(phone.get("/api/app/auth/google/start", params={"redirect": APP_REDIRECT, "challenge": challenge_of(SECRET)},
                                   headers={"x-forwarded-host": "themarkethub.app"}))
    assert there["redirect_uri"] == "https://themarkethub.app/api/app/auth/google/callback"


@pytest.mark.parametrize("redirect, challenge", [
    ("https://evil.example/auth", challenge_of(SECRET)), ("exp://ab12cd-eve-8081.exp.direct/--/auth", challenge_of(SECRET)),
    ("javascript:alert(1)", challenge_of(SECRET)), (APP_REDIRECT, "short"), (APP_REDIRECT, challenge_of(SECRET) + "="), (APP_REDIRECT, "!" * 43)])
def test_start_refuses_a_way_back_that_is_not_the_app_or_a_challenge_that_is_not_one(phone, redirect, challenge):
    r = phone.get("/api/app/auth/google/start", params={"redirect": redirect, "challenge": challenge})
    assert r.status_code == 400 and "location" not in r.headers


# --- The whole way ---------------------------------------------------------------------------------


@pytest.mark.parametrize("redirect", [APP_REDIRECT, EXPO])
def test_the_app_signs_in_with_google(phone, users, redirect):
    _, asked = at_google(start(phone, redirect))
    back = come_back(phone, asked)
    assert back.status_code == 200 and "set-cookie" not in back.headers and not phone.cookies
    where, said = sent_to(back)
    assert where == redirect and set(said) == {"code"}
    assert "user2001@gmail.com" not in back.text  # the code says which account, not whose
    assert "location.replace(" in back.text  # the page goes back to the app by itself
    done = finish(phone, said["code"])
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["user"] == {"id": "2001", "email": "user2001@gmail.com", "name": "Ana", "picture": "https://example.com/a.png", "provider": "google"}
    assert body["new"] is True and body["has_data"] is False and users.get("2001")["email"] == "user2001@gmail.com"
    me = phone.get("/api/me", headers={"authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200 and me.json()["user"] == body["user"]
    assert phone.get("/api/me").status_code == 401  # nothing but the token says who it is


def test_it_is_the_same_account_as_on_the_site(client, phone):
    """Signed in on the site with Google, then in the app: one document, by Google's own id.
    (The two services here share the users' store.)"""
    sign_in(client, "2001")
    client.put("/api/portfolio", json={"positions": [], "watchlist": ["KO"]})
    _, asked = at_google(start(phone))
    body = finish(phone, sent_to(come_back(phone, asked))[1]["code"]).json()
    assert body["new"] is False and body["has_data"] is True
    assert phone.get("/api/portfolio", headers={"authorization": f"Bearer {body['token']}"}).json()["watchlist"] == ["KO"]


# --- What does not get in --------------------------------------------------------------------------


def test_a_code_is_no_good_without_the_secret_it_began_with(phone):
    _, asked = at_google(start(phone))
    code = sent_to(come_back(phone, asked))[1]["code"]
    for secret in ("t" * 43, "", SECRET + "x", challenge_of(SECRET)):
        assert finish(phone, code, secret).status_code == 401
    assert finish(phone, code + "x").status_code == 401 and finish(phone, "nonsense").status_code == 401
    assert finish(phone, code).status_code == 200


def test_a_code_runs_out(phone, monkeypatch):
    _, asked = at_google(start(phone))
    code = sent_to(come_back(phone, asked))[1]["code"]
    later = time.time() + 121
    monkeypatch.setattr(time, "time", lambda: later)
    assert finish(phone, code).status_code == 401


def test_the_id_token_must_be_of_this_sign_in(phone, users):
    """An ID token Google gave for another sign-in (another nonce, or none) is not taken."""
    _, asked = at_google(start(phone))
    for token in ("ok:2001", "ok:2001:another-nonce", "bad", "unverified", "other-aud"):
        where, said = sent_to(come_back(phone, asked, id_token=token))
        assert where == APP_REDIRECT and said == {"error": "refused"}
    assert users.get("2001") is None


def test_saying_no_to_google_comes_back_with_no_code(phone):
    _, asked = at_google(start(phone))
    where, said = sent_to(come_back(phone, asked, id_token=None, error="access_denied"))
    assert where == APP_REDIRECT and said == {"error": "cancelled"}


def test_a_state_that_is_not_ours_goes_nowhere(phone, monkeypatch):
    _, asked = at_google(start(phone))
    other = GoogleFlow("another-secret").begin("https://evil.example/auth", challenge_of(SECRET))[0]
    for state in ("", "nonsense", asked["state"] + "x", other):
        r = phone.post("/api/app/auth/google/callback", data={"state": state, "id_token": f"ok:2001:{asked['nonce']}"})
        assert r.status_code == 400 and "href" not in r.text and "location" not in r.text
    later = time.time() + 601
    monkeypatch.setattr(time, "time", lambda: later)
    assert come_back(phone, asked).status_code == 400


def test_a_state_of_ours_for_an_address_no_longer_allowed_goes_nowhere(service):
    """The allowed addresses are a setting: taking one out stops codes going there at once."""
    _, asked = at_google(start(service("exp://*-ana-8081.exp.direct/--/auth"), EXPO))
    assert come_back(service(""), asked).status_code == 400


def test_the_account_must_still_be_there_when_the_code_is_used(phone, users):
    _, asked = at_google(start(phone))
    code = sent_to(come_back(phone, asked))[1]["code"]
    users.delete("2001")
    assert finish(phone, code).status_code == 401


def test_the_page_on_the_way_back_cannot_be_broken_out_of():
    page = leaving_page('markethub://auth?code="></a><script>alert(1)</script>', "<b>words</b>")
    assert "<script>alert(1)</script>" not in page and "<b>words</b>" not in page
    assert leaving_page(None, "No way back.").count("<script>") == 0


def test_with_no_google_client_the_app_cannot_start(service):
    assert start(service(client_id="")).status_code == 404
