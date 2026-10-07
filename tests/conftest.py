"""Fakes for Google, the data provider and the SEC list: no test touches the network."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from markethub.accounts import MemoryLogins
from markethub.api import create_app
from markethub.community import MemoryCommunity
from markethub.competitions import MemoryCompetitions
from markethub.market import Company, Directory
from markethub.opinion import MemoryOpinion, Opinion
from markethub.users import MemoryUsers

CLIENT_ID = "test-client.apps.googleusercontent.com"
ORIGIN = "http://testserver"


def bars(seed: int, days: int = 420, start: float = 100.0) -> list[dict]:
    out, d, price = [], date.today() - timedelta(days=days), start
    for i in range(days):
        d += timedelta(days=1)
        if d.weekday() >= 5:
            continue
        price *= 1 + 0.0005 * (seed % 3) + 0.01 * math.sin(i / 7 + seed)
        out.append({"date": d.isoformat(), "close": round(price, 4)})
    return out


class FakeFmp:
    def __init__(self, prices: dict[str, float] | None = None):
        self.prices = prices or {"AAPL": 200.0, "MSFT": 400.0, "NVDA": 120.0, "SPY": 550.0, "KO": 60.0}
        self.calls = 0

    def quotes(self, tickers):
        self.calls += 1
        return {t: {"ticker": t, "name": f"{t} Inc.", "price": self.prices[t], "change": self.prices[t] * 0.01,
                    "change_pct": 1.0 if t != "MSFT" else -2.0, "year_high": self.prices[t] * 1.1,
                    "year_low": self.prices[t] * 0.7} for t in tickers if t in self.prices}

    def history(self, ticker):
        return bars(sum(map(ord, ticker)))

    def profile(self, ticker):
        return {"sector": {"AAPL": "Technology", "MSFT": "Technology", "KO": "Consumer Defensive"}.get(ticker, "Other"),
                "name": ticker, "is_etf": ticker == "SPY"}


def google_claims(sub="1001", email="ana@gmail.com", **over):
    claims = {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": sub, "email": email,
              "email_verified": True, "name": "Ana", "picture": "https://example.com/a.png"}
    claims.update(over)
    return claims


def fake_verifier(token: str, client_id: str) -> dict:
    """Tokens look like 'ok:<sub>' or 'bad'; anything else fails as google-auth would."""
    if token.startswith("ok:"):
        return google_claims(sub=token[3:], email=f"user{token[3:]}@gmail.com")
    if token == "unverified":
        return google_claims(email_verified=False)
    if token == "other-aud":
        return google_claims(aud="someone-else")
    raise ValueError("Could not verify token")


@pytest.fixture(autouse=True)
def sample_news(monkeypatch):
    """An app built without a news desk gets the sample one: no test reads the news sources."""
    monkeypatch.setenv("MARKETHUB_SAMPLE_NEWS", "1")


@pytest.fixture
def users():
    return MemoryUsers()


@pytest.fixture
def directory():
    names = {"AAPL": "Apple Inc.", "MSFT": "MICROSOFT CORP", "NVDA": "NVIDIA CORP", "KO": "COCA COLA CO",
             "BRK-B": "BERKSHIRE HATHAWAY INC"}
    return Directory(loader=lambda: [Company(t, n) for t, n in names.items()])


@pytest.fixture
def market():
    return FakeFmp()


ARTICLE = {"slug": "a-quiet-jobs-report", "title": "A quiet jobs report", "dek": "What 29,000 jobs say.", "kind": "Analysis",
           "tags": ["Macro"], "tickers": [], "published_utc": "2026-10-06T08:00:00+00:00", "minutes": 4,
           "body": "First paragraph.\n\n## A heading\n\nSecond paragraph.", "sources": [{"title": "BLS", "url": "https://www.bls.gov/"}]}


@pytest.fixture
def opinion():
    return Opinion(MemoryOpinion([ARTICLE]), admins={"owner@gmail.com"})


@pytest.fixture
def logins():
    return MemoryLogins()


@pytest.fixture
def shared():
    return MemoryCommunity()


@pytest.fixture
def entries():
    return MemoryCompetitions()


class FakeCaptcha:
    """Stands for Cloudflare: the token "human" passes, once asked with the address it came from."""

    site_key = "test-site-key"

    def __init__(self):
        self.asked = []

    def passes(self, token, address=""):
        self.asked.append((token, address))
        return token == "human"


@pytest.fixture
def captcha():
    return FakeCaptcha()


class FakeWriter:
    """Stands for the model: it answers with one sentence, and counts how often it was asked."""

    def __init__(self):
        self.seen = []

    def read(self, user_id, doc, d):
        self.seen.append((user_id, d))
        return {"headline": "Written by the model.", "items": [{"kind": "risk", "text": "A sentence."}], "written": True}


@pytest.fixture
def writer():
    return FakeWriter()


class FakeReader:
    """Stands for the model that reads one stock: it answers about its trend, and keeps what it was sent."""

    def __init__(self):
        self.seen = []

    def read(self, user_id, figures):
        self.seen.append((user_id, figures))
        return {"headline": f"{figures['ticker']}, read by the model.", "points": [{"aspect": "trend", "text": "A sentence."}],
                "contrast": "", "written": True}


@pytest.fixture
def reader():
    return FakeReader()


@pytest.fixture
def client(users, market, directory, opinion, shared, writer, logins, captcha, entries, reader):
    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier,
                     client_id=CLIENT_ID, session_secret="test-secret", secure_cookies=False, opinion=opinion,
                     community_store=shared, insight_writer=writer, logins=logins, password_cost=(10, 8, 1), captcha=captcha,
                     competition_store=entries, stock_reader=reader)
    c = TestClient(app)
    c.headers.update({"origin": ORIGIN})
    return c


def sign_in(client, sub="1001"):
    r = client.post("/api/auth/google", json={"credential": f"ok:{sub}"})
    assert r.status_code == 200, r.text
    return r.json()
