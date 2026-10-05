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

# --- The tools the portal opens ------------------------------------------------------------

EARNINGS_RADAR_URL = os.environ.get("EARNINGS_RADAR_URL", "https://earningsradar.app").rstrip("/")
FUNDAMENTALS_LAB_URL = os.environ.get("FUNDAMENTALS_LAB_URL", "").rstrip("/")
