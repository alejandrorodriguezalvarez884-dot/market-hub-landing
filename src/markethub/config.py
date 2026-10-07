"""Constants of the portal. Secrets come from the environment (or .env locally), never from here."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.environ.get("MARKETHUB_DATA_DIR", ROOT / "data"))

# --- Sign-in -------------------------------------------------------------------------------

# The OAuth client of the site ("Web application" in Google Auth Platform). Public by design: it
# goes to the browser. The ID token Google returns is checked against it.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
# Signs the session cookie. Required in production; a missing one in development gets a random
# value, which logs everybody out on each restart.
SESSION_SECRET = os.environ.get("SESSION_SECRET", "").strip()
SESSION_DAYS = 30
# The parent domain the session cookie is shared on, so the analysis tools on its subdomains
# (radar.<domain>, fundamentals.<domain>) see the same sign-in. Empty: the cookie stays on the
# host that set it. It is only applied to requests that arrive through that domain.
COOKIE_DOMAIN = os.environ.get("MARKETHUB_COOKIE_DOMAIN", "").strip().lstrip(".") or None
# Cookies marked Secure (HTTPS only). Off only for http://localhost.
SECURE_COOKIES = os.environ.get("MARKETHUB_INSECURE_COOKIES", "") != "1"

# --- User data -----------------------------------------------------------------------------

MAX_POSITIONS = 50
MAX_WATCHLIST = 50
FIRESTORE_COLLECTION = "users"
# A database of its own (europe-west1), not the project's "(default)" one, which other apps use.
FIRESTORE_DATABASE = os.environ.get("MARKETHUB_FIRESTORE_DATABASE", "market-hub").strip()

# --- Market data ---------------------------------------------------------------------------

FMP_BASE = "https://financialmodelingprep.com/stable"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
BENCHMARK = "SPY"
QUOTE_TTL_SECONDS = 120
HISTORY_TTL_SECONDS = 6 * 3600
PROFILE_TTL_SECONDS = 7 * 86400
HISTORY_DAYS = 400
# A call the data plan refuses (HTTP 402) is not asked again for this long.
REFUSED_TTL_SECONDS = 6 * 3600
# After the provider says the quota is used up (HTTP 429), nothing is asked for this long.
QUOTA_PAUSE_SECONDS = 15 * 60

# Requests per address per hour on the endpoints that call the data provider.
PER_IP_PER_HOUR = 240
# Sign-ins with a password, right or wrong, that one address can try in an hour, and the accounts
# it can make. Each wrong password for one email is also counted on its own (accounts.py).
PASSWORD_TRIES_PER_IP_PER_HOUR = 30
REGISTRATIONS_PER_IP_PER_HOUR = 5
# Comments a signed-in reader can leave in an hour.
COMMENTS_PER_USER_PER_HOUR = 20

# --- News ----------------------------------------------------------------------------------

# Nothing runs on a timer: a visit that finds the news older than this asks for a refresh.
NEWS_TTL_SECONDS = float(os.environ.get("NEWS_TTL_SECONDS", "900"))
# A refresh that started less than this ago is taken to be still running (on another instance).
NEWS_LOCK_SECONDS = 180
# A refresh stops starting new documents after this long: it runs inside one request. What is
# left is read on the next refresh.
NEWS_BUDGET_SECONDS = 30
NEWS_FRONT_ITEMS = 200  # items kept on the front page; every item also stays in the archive
NEWS_PRESS_ITEMS = 40
NEWS_FIRST_RUN_HOURS = 72  # how far back the first refresh looks
NEWS_MAX_AGE_DAYS = 7  # agencies list months of releases: older ones are not news
# Company filings are followed for the largest companies of the SEC's list, which is ordered by
# market value.
NEWS_UNIVERSE = int(os.environ.get("NEWS_UNIVERSE", "500"))
SEC_CURRENT_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_CURRENT_PAGES = 8  # of 100 filings each
FED_FEED = "https://www.federalreserve.gov/feeds/press_all.xml"
BLS_FEEDS = [f"https://www.bls.gov/feed/{name}.rss" for name in ("empsit", "cpi", "ppi", "jolts")]
BEA_FEED = "https://apps.bea.gov/rss/rss.xml"
# Headlines from the press: "Name|feed URL" pairs separated by commas. Only the headline, the
# publisher's name and the link are kept, never the text. Set it empty to turn them off.
NEWS_PRESS_FEEDS = os.environ.get("NEWS_PRESS_FEEDS", ",".join((
    "CNBC|https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "CNBC|https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "CNBC|https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "CNBC|https://www.cnbc.com/id/10001147/device/rss/rss.html",
)))
# The model that writes an item from an official document, with the owner's ANTHROPIC_API_KEY.
# Without a key the items keep the title the code writes. Spend has no cap here: the owner
# limits it with the credit on the API account.
NEWS_MODEL = os.environ.get("NEWS_MODEL", "claude-haiku-4-5")
NEWS_DOC_CHARS = 16000  # of a document, what the model reads: the narrative comes first
# USD per million tokens (input, output), to log what each item cost.
MODEL_PRICES = {"claude-haiku-4-5": (1.00, 5.00), "claude-sonnet-5-5": (2.00, 10.00)}

# --- My Hub ------------------------------------------------------------------------------------

# The model that reads a portfolio back to its owner in a few sentences (insights.py), with the
# same key as the news. A portfolio that has not changed is read once a day; one that changes, at
# most this many times a day per user. Without a key the page keeps the sentences the code writes.
INSIGHTS_MODEL = os.environ.get("INSIGHTS_MODEL", "claude-haiku-4-5")
INSIGHTS_PER_USER_PER_DAY = int(os.environ.get("INSIGHTS_PER_USER_PER_DAY", "6"))
# The watchlist page (watch.py). The model that reads one stock's figures back, with the same key.
# A stock is read once a day for everybody. Spend has no cap here either (the owner's choice, like
# the news): the two variables set one, on the stocks a user can have read in a day and on those
# of the service as a whole. Without a key the page keeps the sentences the code writes.
WATCH_MODEL = os.environ.get("WATCH_MODEL", "claude-sonnet-5-5")
WATCH_READS_PER_USER_PER_DAY = int(os.environ.get("WATCH_READS_PER_USER_PER_DAY") or 0) or None
WATCH_READS_PER_DAY = int(os.environ.get("WATCH_READS_PER_DAY") or 0) or None
# Requests per address per hour on the watchlist's endpoints: a wall of charts asks for many at once.
WATCH_PER_IP_PER_HOUR = 1500
# Portfolios their owners chose to share, shown on the community board.
COMMUNITY_MEMBERS = 300
# A shared portfolio's figures are worked out again when they are older than this...
COMMUNITY_STALE_SECONDS = 6 * 3600
# ...and at most this many of them on one visit to the board.
COMMUNITY_REFRESH_PER_VISIT = 4

# The monthly competition (competitions.py): a portfolio of single stocks, sent in before the month
# starts. How many stocks it takes and how much of the whole each one can be, in percent.
COMPETITION_PICKS_MIN = 3
COMPETITION_PICKS_MAX = 10
COMPETITION_WEIGHT_MIN = 5
COMPETITION_WEIGHT_MAX = 50
COMPETITION_ENTRANTS = 500  # entries a month takes
# The standings are worked out from daily closes and kept in memory this long.
COMPETITION_CACHE_SECONDS = 300
# A month that ended is settled once every stock has its last close; after this many days it is
# settled with the closes there are (a stock that stopped trading keeps its last one).
COMPETITION_SETTLE_DAYS = 5

# --- The tools the portal opens ------------------------------------------------------------

EARNINGS_RADAR_URL = os.environ.get("EARNINGS_RADAR_URL", "https://earningsradar.app").rstrip("/")
FUNDAMENTALS_LAB_URL = os.environ.get("FUNDAMENTALS_LAB_URL", "").rstrip("/")
