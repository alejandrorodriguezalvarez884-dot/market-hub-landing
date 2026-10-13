"""The phone app opens a tool inside itself: its token, in the header of one request, for the
session cookie the tools ask for. Only with a good token, and only on the way to a tool."""

import pytest
from fastapi.testclient import TestClient

from conftest import CLIENT_ID, fake_verifier, sign_in
from markethub.api import create_app
from markethub.appweb import ToolPages

TOOL = "https://fundamentals.themarkethub.app/stock/?t=AAPL"


@pytest.fixture
def service(users, market, directory, logins, captcha, monkeypatch):
    monkeypatch.setattr("markethub.api.FUNDAMENTALS_LAB_URL", "https://fundamentals.themarkethub.app")
    monkeypatch.setattr("markethub.api.EARNINGS_RADAR_URL", "https://radar.themarkethub.app")
    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=CLIENT_ID, session_secret="test-secret",
                     secure_cookies=False, insight_writer=None, stock_reader=None, logins=logins, password_cost=(10, 8, 1), captcha=captcha)
    return app


@pytest.fixture
def phone(service):
    """The page the app opens: no cookie of its own yet, no Origin."""
    return TestClient(service)


@pytest.fixture
def token(phone):
    made = phone.post("/api/app/auth/register", json={"email": "ana@example.com", "password": "a long enough one", "name": "Ana", "captcha": "human"})
    assert made.status_code == 200, made.text
    assert not phone.cookies
    return made.json()["token"]


def enter(phone, to=TOOL, token=None):
    return phone.get("/api/app/web/enter", params={"to": to}, headers={"authorization": f"Bearer {token}"} if token else {})


def test_the_apps_page_gets_the_session_cookie_and_goes_on_to_the_tool(phone, token):
    r = enter(phone, token=token)
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert 'location.replace("https://fundamentals.themarkethub.app/stock/?t=AAPL")' in r.text
    assert token not in r.text  # the token goes nowhere from here
    assert "mh_session" in r.headers["set-cookie"] and "httponly" in r.headers["set-cookie"].lower()
    # The cookie is the same session the site gives: the portal answers it as that account.
    who = phone.get("/api/me").json()["user"]
    assert who["email"] == "ana@example.com" and who["provider"] == "password"


def test_without_a_good_token_no_cookie_is_set(phone, token):
    for bad in (None, "nope", token[:-2] + "xx"):
        r = enter(phone, token=bad)
        assert r.status_code == 401 and "set-cookie" not in r.headers and "location.replace" not in r.text
    assert phone.get("/api/me").status_code == 401


def test_a_browsers_own_session_does_not_open_this_door(service):
    """The cookie is not what is asked for here: a page a browser is sent to carries no token."""
    browser = TestClient(service)
    browser.headers.update({"origin": "http://testserver"})
    sign_in(browser)
    r = browser.get("/api/app/web/enter", params={"to": TOOL})
    assert r.status_code == 401 and "location.replace" not in r.text


@pytest.mark.parametrize("to", [
    "https://evil.example/", "https://fundamentals.themarkethub.app.evil.example/", "https://evil.example/?x=fundamentals.themarkethub.app",
    "https://fundamentals.themarkethub.app@evil.example/", "http://fundamentals.themarkethub.app/", "//fundamentals.themarkethub.app/",
    "javascript:alert(1)", "https://themarkethub.app/account/", "https:\\\\evil.example", ""])
def test_the_page_only_goes_on_to_a_tool_the_portal_names(phone, token, to):
    r = enter(phone, to=to, token=token)
    assert r.status_code in (400, 422) and "set-cookie" not in r.headers and "location.replace" not in r.text


def test_an_address_cannot_break_out_of_the_page(phone, token):
    r = enter(phone, to='https://fundamentals.themarkethub.app/"</script><script>alert(1)</script>', token=token)
    assert r.status_code == 200 and "<script>alert(1)" not in r.text


def test_tool_pages_are_the_tools_origins_and_nothing_else():
    pages = ToolPages(["https://radar.themarkethub.app", None, "", "http://localhost:8082"])
    assert pages.allowed("https://radar.themarkethub.app/analyze/?ticker=KO") and pages.allowed("http://localhost:8082/")
    for other in ("https://radar.themarkethub.app:8443/", "http://localhost:8083/", "https://RADAR.themarkethub.app.x/", "ftp://radar.themarkethub.app/"):
        assert not pages.allowed(other)
    assert pages.allowed("https://RADAR.themarkethub.app/")
