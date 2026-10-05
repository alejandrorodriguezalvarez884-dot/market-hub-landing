import pytest

from conftest import ORIGIN, sign_in
from markethub.users import InvalidPortfolio, clean


def test_signed_out_user_sees_nothing(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/portfolio").status_code == 401
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/config").json()["google_client_id"].endswith("googleusercontent.com")


@pytest.mark.parametrize("token", ["bad", "unverified", "other-aud"])
def test_bad_google_tokens_are_refused(client, token):
    r = client.post("/api/auth/google", json={"credential": token})
    assert r.status_code == 401
    assert client.get("/api/me").status_code == 401


def test_sign_in_creates_the_user_and_a_session(client, users):
    body = sign_in(client)
    assert body["new"] is True and body["has_data"] is False
    assert users.get("1001")["email"] == "user1001@gmail.com"
    assert client.get("/api/me").json()["user"]["id"] == "1001"
    again = sign_in(client)
    assert again["new"] is False


def test_portfolio_round_trip_and_validation(client):
    sign_in(client)
    r = client.put("/api/portfolio", json={
        "positions": [{"ticker": "aapl", "shares": 10, "avg_cost": 150}, {"ticker": "AAPL", "shares": 10, "avg_cost": 250},
                      {"ticker": "msft", "shares": 2, "avg_cost": ""}],
        "watchlist": ["nvda", "AAPL", "brk.b"],
    })
    assert r.status_code == 200, r.text
    saved = client.get("/api/portfolio").json()
    aapl = next(p for p in saved["positions"] if p["ticker"] == "AAPL")
    assert aapl["shares"] == 20 and aapl["avg_cost"] == pytest.approx(200)
    assert saved["watchlist"] == ["NVDA", "BRK-B"]  # AAPL is already held
    assert client.get("/api/me").json()["has_data"] is True
    bad = client.put("/api/portfolio", json={"positions": [{"ticker": "ZZZZ", "shares": 1}], "watchlist": []})
    assert bad.status_code == 400 and "ZZZZ" in bad.json()["detail"]
    neg = client.put("/api/portfolio", json={"positions": [{"ticker": "AAPL", "shares": -1}], "watchlist": []})
    assert neg.status_code == 400


def test_users_only_see_their_own_data(client):
    sign_in(client, "1")
    client.put("/api/portfolio", json={"positions": [{"ticker": "AAPL", "shares": 1, "avg_cost": 1}], "watchlist": []})
    client.post("/api/auth/logout")
    sign_in(client, "2")
    assert client.get("/api/portfolio").json()["positions"] == []


def test_writes_from_another_site_are_refused(client):
    sign_in(client)
    r = client.put("/api/portfolio", json={"positions": [], "watchlist": ["AAPL"]}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    r = client.put("/api/portfolio", json={"positions": [], "watchlist": ["AAPL"]}, headers={"origin": ""})
    assert r.status_code == 403
    assert client.get("/api/portfolio").json()["watchlist"] == []


def test_logout_and_delete_account(client, users):
    sign_in(client)
    client.put("/api/portfolio", json={"positions": [], "watchlist": ["KO"]})
    assert client.delete("/api/me").json() == {"deleted": True}
    assert users.get("1001") is None
    assert client.get("/api/me").status_code == 401


def test_session_cookie_is_http_only_and_lax(client):
    r = client.post("/api/auth/google", json={"credential": "ok:7"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert "ok:7" not in cookie  # the Google token is not kept


def test_search_by_ticker_and_name(client):
    assert client.get("/api/search", params={"q": "apple"}).json()["companies"][0]["ticker"] == "AAPL"
    assert client.get("/api/search", params={"q": "MSFT"}).json()["companies"][0]["ticker"] == "MSFT"
    assert client.get("/api/search", params={"q": "spy"}).json()["companies"][0]["ticker"] == "SPY"  # added funds


def test_clean_limits():
    with pytest.raises(InvalidPortfolio):
        clean([{"ticker": "AAPL", "shares": 1}] * 51, [])
    with pytest.raises(InvalidPortfolio):
        clean([], ["not a ticker!"])


def _domain_client(users, market, directory, base_url):
    from fastapi.testclient import TestClient

    from conftest import CLIENT_ID, fake_verifier
    from markethub.api import create_app

    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=CLIENT_ID,
                     session_secret="test-secret", secure_cookies=False, cookie_domain="themarkethub.app")
    c = TestClient(app, base_url=base_url)
    c.headers.update({"origin": base_url})
    return c


def test_session_cookie_is_shared_with_the_tools_on_the_parent_domain(users, market, directory):
    c = _domain_client(users, market, directory, "http://themarkethub.app")
    r = c.post("/api/auth/google", json={"credential": "ok:7"})
    cookie = r.headers["set-cookie"].lower()
    assert "domain=themarkethub.app" in cookie and "httponly" in cookie
    assert c.get("/api/config").json()["domain"] == "themarkethub.app"


def test_other_hosts_keep_a_host_only_cookie(users, market, directory):
    # The *.run.app address: a cookie for a foreign domain would be dropped by the browser.
    c = _domain_client(users, market, directory, "http://market-hub-abc.a.run.app")
    r = c.post("/api/auth/google", json={"credential": "ok:7"})
    assert "domain=" not in r.headers["set-cookie"].lower()
    assert c.get("/api/me").status_code == 200
