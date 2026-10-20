"""The portal's service: the site and the API, from one origin.

    GET    /api/health
    GET    /api/config              Google client id and the tools' addresses (public)
    POST   /api/auth/google         {credential}: Google ID token -> session cookie
    POST   /api/auth/logout
    GET    /api/me                  the signed-in user, or 401
    DELETE /api/me                  delete the account and everything saved
    GET    /api/me/option-strategies   the strategies the user keeps in Options Lab
    GET    /api/portfolio           positions and watchlist
    PUT    /api/portfolio           replace them
    POST   /api/auth/register       {email, password, name, captcha}: an account of ours, and its session
    POST   /api/auth/password       {email, password}: sign in to one
    PUT    /api/auth/password       {current, new}: change its password
    POST   /api/app/auth/password   {email, password}: the phone app signs in, and gets a token
    POST   /api/app/auth/renew      the app's token, for a new one that lasts from today
    GET    /api/app/auth/google/start     ?redirect=&challenge=  the app's browser, sent on to Google
    POST   /api/app/auth/google/callback  where Google posts the ID token; back to the app with a code
    POST   /api/app/auth/google/finish    {code, verifier}: the app's token (appsignin.py)
    POST   /api/app/auth/apple/begin      the nonce of one sign-in with Apple
    POST   /api/app/auth/apple            {identity_token, name}: Apple's token -> the app's token (applesignin.py)
    POST   /api/app/auth/apple/revoke     {identity_token, authorization_code}: before deleting an Apple
                                    account, have Apple forget the app for it (applerevoke.py)
    GET    /api/app/web/enter       ?to=  the app's own page, on its way to a tool: the app's token for
                                    the session cookie the tools ask for (appweb.py)
    GET    /api/insights            the sentences that read the portfolio back, by the model when it answers
    GET    /api/watchlist           the stocks the user follows and holds, each read from its prices
    GET    /api/watchlist/stock     ?t=  any one stock, read the same way
    GET    /api/watchlist/bars      ?t=  its daily bars, for its chart
    GET    /api/watchlist/read      ?t=  what analysts estimate for it, and its figures in sentences
    GET    /api/sharing             whether the portfolio is shared, and under what name
    PUT    /api/sharing             {enabled, handle}: share it, rename it or stop
    GET    /api/community           the shared portfolios and where the user's stands
    GET    /api/competitions        the monthly competition: this month's standings, the entry for the
                                    next one, the months that ended and everybody's record
    PUT    /api/competitions/entry  {handle, picks}: send in or change the entry for next month
    DELETE /api/competitions/entry  take it back
    GET    /api/competitions/comments ?month=  the month's discussion (signed in)
    POST   /api/competitions/comments {month, text, parent_id}: comment or answer
    GET    /api/competitions/mine   the user's own entries
    GET    /api/bots                the bot competition: the board, the user's bot and key, and
                                    whether the bots are behind the last close
    POST   /api/bots/refresh        move the bots on to the last close, if they are behind
    POST   /api/bots/kit            a new key, and the kit with it in its .env (a zip)
    POST   /api/bots/key            a new key, shown once      DELETE /api/bots/key  take it back
    DELETE /api/bots/mine           withdraw the user's bot
    GET    /api/bots/mine           what is kept of the user's bot and key (the account page)
    The routes of the user's agent, with the bot key (Authorization: Bearer mhb_...), never the cookie:
    GET    /api/bot/spec            what a bot can be (no key needed)
    POST   /api/bot/check           {bot}: whether it is a bot, and its rules in words
    POST   /api/bot/backtest        {bot, years}: what it would have done, for its owner
    PUT    /api/bot                 {bot, handle?}: send it in, in place of the one there was
    GET    /api/bot                 the user's bot: returns, rank, holdings, rules
    GET    /api/dashboard           positions valued at today's prices, favourites, history
    GET    /api/search?q=           companies by ticker or name, and US funds (ETFs, mutual funds)
    GET    /api/public/overview     markets: indices, rates, commodities, currencies, sectors, movers
                                    (?detail=1 adds 1-month, YTD and 1-year returns)
    GET    /api/public/chart        ?symbol=&range=  price bars for the charts
    GET    /api/public/quote        ?t=  a stock's figures and its own news
    GET    /api/public/quote/more   ?t=  the rest of its page: its past against the S&P 500, and
                                    what the provider says of the company or the fund
    GET    /api/public/news         ?category=&ticker=  the news, and whether it is stale
    GET    /api/public/news/item    ?id=  one item, with its article
    POST   /api/public/news/refresh read the news sources, if the news is stale
    GET    /api/news/mine           the news about the user's own stocks
    GET    /api/public/opinion      the opinion articles, as cards
    GET    /api/public/opinion/item ?slug=  one article
    GET    /api/public/opinion/cover ?slug=&v=  its picture (JPEG)
    GET    /api/public/opinion/comments ?slug=  the thread under it (anyone reads it)
    POST   /api/opinion/comments    {slug, text, parent_id}: comment or answer (signed in)
    GET    /api/opinion/mine        the user's own comments
    DELETE /api/opinion/comments/{id}   take one's own comment down
    POST   /api/comments/{id}/report    say a comment should not be there (any thread, signed in)
    GET    /api/blocks              the members the user has blocked
    POST   /api/blocks              {comment_id}: stop seeing what its author writes
    DELETE /api/blocks/{key}        unblock one
    GET    /api/moderation/reports  the reported comments (the owner)
    POST   /api/moderation/reports/{id}/keep   a reported comment stays (the owner)
    GET    /api/opinion/submissions the articles the user sent in for review, and the form's measures
    POST   /api/opinion/submissions {title, dek, body, sources, tickers, byline, agree}: send one in.
                                    It is kept for the owner to review; nothing is published
    DELETE /api/opinion/submissions/{id}   take one back
    GET    /api/public/instagram    what the account last posted on Instagram, as cards
    GET    /api/public/instagram/cover ?id=&v=  a post's cover (JPEG)
    GET    /api/public/x            what the account last posted on X, as cards

Market figures come from FMP when there is a key (live.py), else from sample.py; the overview
names any part that is sample data in "sample_sections". The news comes from news.py.

A browser is known by its session cookie. The phone app has none: it sends the token it was
handed at /api/app/auth/... as "Authorization: Bearer <token>" (tokens.py), and every route above
that asks who is signed in answers it the same.

For search engines (seo.py): GET /robots.txt and GET /sitemap.xml, the portal's own pages and the
opinion articles. The news items, the quotes and My Hub say noindex in their own HTML.

Everything else is the static site, when MARKETHUB_STATIC_DIR points at its build. Its two pages
that are not handed out as built are /opinion/article/?slug=, which carries the article itself
(its title, dek and cover in the head, its text in the body) for the sites a link is shared on
and for search engines, and /opinion/, which carries the list of articles (previews.py).
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import threading
import time
from urllib.parse import parse_qs
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import accounts as accounts_
from . import dashboard
from .accounts import Accounts, LoginStore, default_logins
from .captcha import app_page, default_captcha, open_without
from .community import PERIODS as BOARD_PERIODS
from .community import Community, CommunityStore, default_community
from .community import Refused as SharingRefused
from . import bots as bots_
from .bots import BotStore, Bots, default_bots
from . import competitions as competitions_
from .competitions import CompetitionStore, Competitions, default_competitions
from .holdings import BENCHMARK, SampleData, sample_only
from . import sample as sample_data
from .insights import default_writer
from .instagram import Posts, default_posts
from .xposts import XPosts, default_x
from .watch import Watch, default_reader
from .live import default_markets
from .news import default_news
from .opinion import MEMBERS_ONLY, Opinion, Refused, default_opinion
from .optionstrategies import OptionStrategies, default_option_strategies
from . import previews, seo
from . import submissions as submissions_
from .submissions import Submissions, default_submissions
from . import applesignin
from .applerevoke import AppleRevoker, NotRevoked, default_revoker
from .appweb import ToolPages, entering_page
from .appsignin import CHALLENGE, AppRedirects, GoogleFlow, back_to_app, google_address, leaving_page
from .auth import InvalidToken, Verifier, google_verifier, verify
from .config import (APP_REDIRECTS, BOT_BACKTESTS_PER_USER_PER_HOUR, BOT_SUBMISSIONS_PER_USER_PER_DAY, PASSWORD_TRIES_PER_IP_PER_HOUR, REGISTRATIONS_PER_IP_PER_HOUR,
                     COMMENTS_PER_USER_PER_HOUR, COMMUNITY_MEMBERS, COOKIE_DOMAIN, EARNINGS_RADAR_URL, FUNDAMENTALS_LAB_URL, GOOGLE_CLIENT_ID, OPTIONS_LAB_URL, PEER_MAP_URL, PER_IP_PER_HOUR, PLAYGROUND_URL,
                     SECURE_COOKIES, SESSION_DAYS, SESSION_SECRET, SITE_URL, SUBMISSIONS_PER_USER_PER_DAY, WATCH_PER_IP_PER_HOUR)
from .market import EXTRA, Directory, Fmp, MarketUnavailable
from .tokens import AppTokens, bearer
from .yahoo import Yahoo, daily_bars, default_market
from .users import InvalidPortfolio, UserStore, clean, default_users, empty, touch

log = logging.getLogger("markethub.api")

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


class RateLimiter:
    def __init__(self, limit: int, window: float = 3600.0):
        self.limit, self.window = limit, window
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, who: str) -> bool:
        now = time.monotonic()
        with self._lock:
            calls = self._calls[who]
            while calls and now - calls[0] > self.window:
                calls.popleft()
            if len(calls) >= self.limit:
                return False
            calls.append(now)
            return True


def _client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


class HostScopedCookieDomain:
    """Keeps the session cookie's Domain attribute only for requests that arrive through that
    domain. On any other host (the *.run.app address, localhost) a browser would drop a cookie
    for a foreign domain, and sign-in would silently fail there."""

    def __init__(self, app, domain: str):
        self.app, self.domain = app, domain
        self.attr = f"; domain={domain}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        host = dict(scope["headers"]).get(b"host", b"").decode().split(":")[0].lower()
        if host == self.domain or host.endswith("." + self.domain):
            return await self.app(scope, receive, send)

        async def strip(message):
            if message["type"] == "http.response.start":
                message["headers"] = [(k, v.replace(self.attr, b"") if k.lower() == b"set-cookie" else v)
                                      for k, v in message["headers"]]
            await send(message)

        return await self.app(scope, receive, strip)


def merge_found(companies: list[dict], funds: list[dict], query: str, limit: int = 8) -> list[dict]:
    """The search's answers: the exact ticker first, then up to five companies, then the funds the
    provider found, then the other companies, each ticker once."""
    exact = query.strip().upper().replace(".", "-")
    seen: set[str] = set()
    out: list[dict] = []
    first = [x for x in companies + funds if x["ticker"] == exact]
    for x in first + companies[:5] + funds + companies[5:]:
        if x["ticker"] not in seen and len(out) < limit:
            seen.add(x["ticker"])
            out.append(x)
    return out


def create_app(users: UserStore | None = None, market: Fmp | None = None, directory: Directory | None = None,
               verifier: Verifier = google_verifier, client_id: str | None = None,
               session_secret: str | None = None, secure_cookies: bool | None = None,
               static_dir: str | None = None, cookie_domain: str | None = COOKIE_DOMAIN, markets=None,
               news=None, opinion: Opinion | None = None, community_store: CommunityStore | None = None,
               insight_writer="default", logins: LoginStore | None = None,
               password_cost: tuple[int, int, int] = accounts_.COST, captcha="default",
               competition_store: CompetitionStore | None = None, clock=None, stock_reader="default",
               app_redirects: str | None = None, submissions: Submissions | None = None,
               apple_verifier: applesignin.Verifier | None = None, apple_revoker: AppleRevoker | None | str = "default",
               posts: Posts | None = None, x_posts: XPosts | None = None,
               option_strategies: OptionStrategies | None = None, bot_store: BotStore | None = None, bot_closes=None) -> FastAPI:
    """App factory. Tests pass their own pieces, so they need no network and no Google."""
    logging.basicConfig(level=logging.INFO)
    # httpx logs every request URL at INFO, and FMP takes the key in the query string: keep the
    # key out of the logs. yfinance prints what Yahoo answers when it has no such symbol.
    for noisy in ("httpx", "httpcore", "yfinance"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    app = FastAPI(title="Market Hub", docs_url=None, redoc_url=None, openapi_url=None)
    users = users or default_users()
    market = market or default_market()
    directory = directory or Directory()
    markets = markets or default_markets(market)
    news = news or default_news(markets, directory)
    opinion = opinion or Opinion(default_opinion())
    posts = posts or Posts(default_posts())
    x_posts = x_posts or XPosts(default_x())
    # The articles readers send in: kept for the owner to review, never published from here.
    submissions = submissions or Submissions(default_submissions())
    # What users keep in Options Lab: written there, read and deleted here with the account.
    option_strategies = option_strategies or default_option_strategies()
    # The accounts with a password of ours. MARKETHUB_PASSWORD_LOGIN=0 leaves Google as the only way in.
    accounts = Accounts(logins or default_logins(), password_cost)
    password_login = os.environ.get("MARKETHUB_PASSWORD_LOGIN", "1").strip() != "0"
    # Making an account takes a captcha. With none configured no accounts are made, unless the
    # environment says they may be made without one (a developer's machine).
    human = default_captcha() if captcha == "default" else captcha
    registration = "closed" if not password_login else "captcha" if human else "open" if open_without() else "closed"
    writer = default_writer() if insight_writer == "default" else insight_writer
    # What answers for the provider when it does not: sample figures, said to be so.
    stand_in = SampleData(lambda ticker: company_name(ticker))
    only_sample = sample_only()

    def figures(doc: dict) -> dict:
        return dashboard.build(doc, market, stand_in, sample=only_sample)

    def mix(positions: list[dict]) -> dict:
        return {"positions": positions, "watchlist": []}

    # The watchlist page: each stock read from its prices, and by the model when there is one.
    watch = Watch(market, stand_in, reader=default_reader() if stock_reader == "default" else stock_reader, sample=only_sample,
                  name_of=lambda ticker: company_name(ticker))
    community_store = community_store or default_community()
    community = Community(community_store, value=lambda positions: figures(mix(positions)),
                          sample_value=lambda positions: dashboard.build(mix(positions), stand_in, stand_in, sample=True))
    # The monthly competition. A name played under cannot be one somebody else shares a portfolio under.
    competitions = Competitions(
        competition_store or default_competitions(), market, stand_in, known=directory.known, name_of=lambda ticker: company_name(ticker),
        taken=lambda key, user_id: any(m.get("handle_key") == key and m.get("user_id") != user_id for m in community_store.all(COMMUNITY_MEMBERS)),
        shared_name=lambda user_id: community.status(user_id)["handle"], sample=only_sample, now=clock)

    # The bot competition: rules run on paper on the closes of the largest companies.
    funds = {c.ticker for c in EXTRA}

    def largest_companies(n: int) -> list[str]:
        if only_sample:
            return [s.symbol for s in sample_data.STOCKS if s.kind == "stock"][:n]
        return [c.ticker for c in directory.largest(n + 40).values() if c.ticker not in funds][:n]

    def closes_of(tickers: set[str]) -> dict[str, list[tuple[str, float]]]:
        if bot_closes:
            return bot_closes(tickers)
        if only_sample:
            return {t: [(b["time"], b["close"]) for b in stand_in.bars(t)] for t in tickers}
        yahoo = next((s for s in [market, *getattr(market, "sources", [])] if isinstance(s, Yahoo)), None)
        if yahoo:
            got = yahoo.closes(sorted(tickers))
        else:
            def one(t: str) -> list[tuple[str, float]]:
                try:
                    return [(b["time"], b["close"]) for b in daily_bars(market, t)]
                except MarketUnavailable:
                    return []

            with ThreadPoolExecutor(max_workers=8) as pool:
                got = dict(zip(sorted(tickers), pool.map(one, sorted(tickers))))
        if not got.get(BENCHMARK):
            raise MarketUnavailable("The market data provider is not answering for now.")
        return got

    bots = Bots(bot_store or default_bots(), closes_of, largest_companies,
                taken=lambda key, user_id: any(m.get("handle_key") == key and m.get("user_id") != user_id for m in community_store.all(COMMUNITY_MEMBERS)),
                member_name=competitions.name, sample=only_sample, now=clock)
    client_id = GOOGLE_CLIENT_ID if client_id is None else client_id
    secret = session_secret or SESSION_SECRET
    if not secret:
        log.warning("SESSION_SECRET is not set: using a random one, sessions end on restart")
        secret = secrets.token_urlsafe(32)
    secure = SECURE_COOKIES if secure_cookies is None else secure_cookies
    limiter = RateLimiter(PER_IP_PER_HOUR)
    commenting = RateLimiter(COMMENTS_PER_USER_PER_HOUR)
    submitting = RateLimiter(SUBMISSIONS_PER_USER_PER_DAY, window=86400.0)
    backtesting = RateLimiter(BOT_BACKTESTS_PER_USER_PER_HOUR)
    sending_bots = RateLimiter(BOT_SUBMISSIONS_PER_USER_PER_DAY, window=86400.0)
    watching = RateLimiter(WATCH_PER_IP_PER_HOUR)
    # Checking a password is slow on purpose, and an account costs nothing to ask for: both are
    # counted per address they come from.
    signing = RateLimiter(PASSWORD_TRIES_PER_IP_PER_HOUR)
    registering = RateLimiter(REGISTRATIONS_PER_IP_PER_HOUR)
    tokens = AppTokens(secret, SESSION_DAYS * 86400)
    google_flow = GoogleFlow(secret)
    redirects = AppRedirects(APP_REDIRECTS if app_redirects is None else app_redirects)
    # Sign in with Apple takes no key of ours: Apple's own, published, check its tokens.
    apple_flow = applesignin.AppleFlow(secret)
    apple_checks = apple_verifier or applesignin.AppleKeys()
    # Has Apple forget the app for an account that is being deleted. None without the developer's key.
    revoker = default_revoker() if apple_revoker == "default" else apple_revoker
    # The tools the app may open inside itself, signed in (appweb.py).
    tool_pages = ToolPages([EARNINGS_RADAR_URL, FUNDAMENTALS_LAB_URL, PEER_MAP_URL, PLAYGROUND_URL, OPTIONS_LAB_URL])

    def app_token(request: Request) -> str | None:
        return bearer(request.headers.get("authorization"))

    def from_app(request: Request) -> bool:
        """The phone app sends no Origin, and its requests need none. What the Origin check stops
        is a foreign page using the cookie a browser sends by itself: the routes under /api/app/
        neither read that cookie nor set one, and a request that carries a good token is answered
        for the token's user alone (signed_in)."""
        return request.url.path.startswith("/api/app/") or tokens.read(app_token(request)) is not None or agent_route(request)

    def agent_route(request: Request) -> bool:
        """The routes of a member's agent: they take the bot key and never read the cookie."""
        return request.url.path == "/api/bot" or request.url.path.startswith("/api/bot/")

    origins = [o.strip() for o in os.environ.get("MARKETHUB_ALLOWED_ORIGINS", "").split(",") if o.strip()]

    @app.middleware("http")
    async def same_origin_writes(request: Request, call_next):
        """Writes must come from this site. With the session cookie set to SameSite=Lax this
        closes cross-site request forgery: a foreign page can neither send the cookie on a POST
        nor pass this check. The phone app's writes carry its token instead (from_app)."""
        if request.method in UNSAFE and request.url.path.startswith("/api/") and not from_app(request):
            origin = request.headers.get("origin")
            own = f"{request.url.scheme}://{request.url.netloc}"
            forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
            allowed = {own, f"https://{forwarded_host}", *origins}
            if origin not in allowed:
                return JSONResponse({"detail": "Cross-site request refused."}, status_code=403)
        response = await call_next(request)
        # Nothing of the API is kept by a browser, but what says itself that it can be (a picture).
        if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response

    # Added after the middleware above, so it runs first and the session is ready for it.
    app.add_middleware(SessionMiddleware, secret_key=secret, session_cookie="mh_session",
                       max_age=SESSION_DAYS * 86400, same_site="lax", https_only=secure, domain=cookie_domain)
    if cookie_domain:
        app.add_middleware(HostScopedCookieDomain, domain=cookie_domain)
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True,
                           allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["content-type", "authorization"])

    def signed_in(request: Request) -> dict | None:
        """Who is asking, or None. A request that carries a token is the token's user or nobody:
        the cookie is not looked at, so a token never borrows a browser's session."""
        token = app_token(request)
        return tokens.read(token) if token else request.session.get("user")

    def current_user(request: Request) -> dict:
        user = signed_in(request)
        if not user:
            raise HTTPException(401, "Sign in first.")
        return user

    def load(user: dict) -> dict:
        doc = users.get(user["id"])
        if doc is None:
            doc = empty(user["id"])
        return doc

    def allow(request: Request) -> None:
        if not limiter.allow(_client_address(request)):
            raise HTTPException(429, "Too many requests from this address. Try again later.")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/config")
    def config() -> dict:
        return {
            "google_client_id": client_id,
            "domain": cookie_domain,
            "password_login": password_login,
            # The phone app shows Apple's button only where its token is taken.
            "apple_sign_in": True,
            # Whether deleting an Apple account takes one more confirmation on the phone, to tell Apple.
            "apple_revocation": revoker is not None,
            # Whether an account can be made here, and the key of the captcha's widget if it takes one.
            "registration": registration,
            "turnstile_site_key": human.site_key if registration == "captcha" else None,
            # Whether a signed-in reader can send an article in for review here.
            "submissions": submissions.open,
            "tools": {
                "earnings_radar": EARNINGS_RADAR_URL or None,
                "fundamentals_lab": FUNDAMENTALS_LAB_URL or None,
                "peer_map": PEER_MAP_URL or None,
                "playground": PLAYGROUND_URL or None,
                "options_lab": OPTIONS_LAB_URL or None,
            },
        }

    @app.post("/api/auth/google")
    def sign_in(request: Request, credential: str = Body(embed=True, max_length=4096)) -> dict:
        allow(request)
        try:
            g = verify(credential, client_id, verifier)
        except InvalidToken as exc:
            log.info("sign-in refused: %s", exc)
            raise HTTPException(401, "Google sign-in could not be verified.") from None
        said = google_welcome(g)
        request.session.clear()
        request.session["user"] = said["user"]
        log.info("sign-in ok new=%s", said["new"])
        return said

    def google_welcome(g) -> dict:
        """Keep the profile Google gave with the user's document, and say what the account has."""
        doc = users.get(g.id)
        new = doc is None
        if new:
            doc = empty(g.id)
        # Profile fields are refreshed on every sign-in; they are only shown back to the user.
        users.put(g.id, touch(doc, email=g.email, name=g.name, picture=g.picture))
        return {"user": {"id": g.id, "email": g.email, "name": g.name, "picture": g.picture, "provider": "google"}, "new": new,
                "has_data": bool(doc.get("positions") or doc.get("watchlist"))}

    def welcome(user: dict, new: bool) -> dict:
        """Keep the profile of an account of ours with its document, and say what it has."""
        doc = users.get(user["id"]) or empty(user["id"])
        users.put(user["id"], touch(doc, email=user["email"], name=user["name"], picture="", provider="password"))
        return {"user": user, "new": new, "has_data": bool(doc.get("positions") or doc.get("watchlist"))}

    def enter(request: Request, user: dict, new: bool) -> dict:
        """Open the session of an account of ours."""
        said = welcome(user, new)
        request.session.clear()
        request.session["user"] = user
        return said

    def checked(email: str, password: str) -> dict:
        try:
            return accounts.sign_in(email, password)
        except accounts_.Wrong:
            # The same words whether the address is unknown or the password is not its own.
            raise HTTPException(401, "That email and password do not match an account.") from None
        except accounts_.TooMany:
            raise HTTPException(429, "Too many wrong passwords for that email. Wait a few minutes and try again.") from None

    def by_password(request: Request, limiter: RateLimiter, sorry: str) -> None:
        if not password_login:
            raise HTTPException(404, "Signing in with a password is not on.")
        if not limiter.allow(_client_address(request)):
            raise HTTPException(429, sorry)

    def made(request: Request, email: str, password: str, name: str, captcha: str) -> dict:
        """A new account of ours, for the site or for the app: the same door and the same checks."""
        if registration == "closed":
            raise HTTPException(403, "New accounts cannot be made here right now.")
        by_password(request, registering, "Too many accounts were made from this address. Try again later.")
        # Before anything else is looked at: no captcha, no answer about the email or the password.
        if registration == "captcha" and not human.passes(captcha, _client_address(request)):
            raise HTTPException(400, "We could not check that you are a person. Try the check again.")
        try:
            user = accounts.register(email, password, name)
        except accounts_.Refused as exc:
            raise HTTPException(400, str(exc)) from None
        log.info("account made")
        return user

    @app.post("/api/auth/register")
    def register(request: Request, email: str = Body(embed=True, max_length=300), password: str = Body(embed=True, max_length=1000),
                 name: str = Body(embed=True, max_length=200), captcha: str = Body("", embed=True, max_length=4096)) -> dict:
        return enter(request, made(request, email, password, name, captcha), new=True)

    @app.post("/api/app/auth/register")
    def app_register(request: Request, email: str = Body(embed=True, max_length=300), password: str = Body(embed=True, max_length=1000),
                     name: str = Body(embed=True, max_length=200), captcha: str = Body("", embed=True, max_length=4096)) -> dict:
        """An account made from the phone app: the captcha is asked for all the same (the app shows
        its widget on the page below), and a token comes back where the site gets a cookie."""
        user = made(request, email, password, name, captcha)
        return welcome(user, new=True) | {"token": tokens.issue(user)}

    @app.get("/api/app/captcha")
    def app_captcha(request: Request) -> Response:
        """The captcha's widget on a page of this site, for the app to show inside itself: the
        widget only runs on a page of the domain its key was made for."""
        allow(request)
        if registration != "captcha":
            raise HTTPException(404, "No check is asked for here.")
        return HTMLResponse(app_page(human.site_key))

    @app.post("/api/auth/password")
    def sign_in_password(request: Request, email: str = Body(embed=True, max_length=300), password: str = Body(embed=True, max_length=1000)) -> dict:
        by_password(request, signing, "Too many attempts from this address. Try again later.")
        user = checked(email, password)
        log.info("password sign-in ok")
        return enter(request, user, new=False)

    @app.post("/api/app/auth/password")
    def app_sign_in_password(request: Request, email: str = Body(embed=True, max_length=300), password: str = Body(embed=True, max_length=1000)) -> dict:
        """The phone app's way in: the same check and the same limits, and a token where the site
        gets a cookie. No cookie is read or set here."""
        by_password(request, signing, "Too many attempts from this address. Try again later.")
        user = checked(email, password)
        log.info("password sign-in ok (app)")
        return welcome(user, new=False) | {"token": tokens.issue(user)}

    @app.post("/api/app/auth/renew")
    def app_renew(request: Request) -> dict:
        """A token that lasts from today, for an app that is opened before its own runs out."""
        allow(request)
        user = tokens.read(app_token(request))
        if not user:
            raise HTTPException(401, "Sign in first.")
        return {"user": user, "token": tokens.issue(user)}

    @app.put("/api/auth/password")
    def change_password(request: Request, current: str = Body(embed=True, max_length=1000), new: str = Body(embed=True, max_length=1000)) -> dict:
        user = current_user(request)
        if user.get("provider") != "password":
            raise HTTPException(400, "This account signs in with Google or with Apple: it has no password here.")
        by_password(request, signing, "Too many attempts from this address. Try again later.")
        try:
            accounts.change_password(user["email"], current, new)
        except accounts_.Wrong:
            raise HTTPException(401, "That is not your current password.") from None
        except accounts_.TooMany:
            raise HTTPException(429, "Too many wrong passwords. Wait a few minutes and try again.") from None
        except accounts_.Refused as exc:
            raise HTTPException(400, str(exc)) from None
        log.info("password changed")
        return {"changed": True}

    @app.post("/api/auth/logout")
    def sign_out(request: Request) -> dict:
        request.session.clear()
        return {"ok": True}

    def public_address(request: Request) -> str:
        """This service as a browser reaches it: Google sends the ID token back there."""
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        local = host.split(":")[0] in ("localhost", "127.0.0.1", "testserver")
        return f"{'http' if local else 'https'}://{host}"

    @app.get("/api/app/auth/google/start")
    def app_google_start(request: Request, redirect: str = Query(max_length=300), challenge: str = Query(max_length=64)) -> Response:
        """The app's browser, on its way to Google. Only an address of the app is taken as the
        way back, and only with the challenge that will tie the code to the app that asked."""
        allow(request)
        if not client_id:
            raise HTTPException(404, "Signing in with Google is not on.")
        if not redirects.allowed(redirect) or not CHALLENGE.fullmatch(challenge):
            raise HTTPException(400, "This is not the Market Hub app asking.")
        state, nonce = google_flow.begin(redirect, challenge)
        return RedirectResponse(google_address(client_id, f"{public_address(request)}/api/app/auth/google/callback", state, nonce), 302)

    @app.post("/api/app/auth/google/callback")
    async def app_google_callback(request: Request) -> Response:
        """Google posts here what the user did. The ID token is checked as the site's is, and
        must carry the nonce of the sign-in the state belongs to. No cookie is read or set."""
        allow(request)
        form = parse_qs((await request.body())[:16384].decode("utf-8", "replace"))
        field = lambda name: (form.get(name) or [""])[0]  # noqa: E731
        began = google_flow.came_back(field("state"))
        if not began or not redirects.allowed(began["r"]):
            return HTMLResponse(leaving_page(None, "This sign-in took too long. Go back to the app and try again."), 400)

        def leave(words: str, **said: str) -> Response:
            return HTMLResponse(leaving_page(back_to_app(began["r"], **said), words))

        if not field("id_token"):  # the user said no to Google, or Google said no
            return leave("Sign-in was not completed. Returning to Market Hub…", error="cancelled")
        seen: dict = {}

        def checking(token: str, audience: str) -> dict:
            seen.update(verifier(token, audience))
            return seen

        try:
            g = verify(field("id_token"), client_id, checking)
            if not secrets.compare_digest(str(seen.get("nonce") or ""), began["n"]):
                raise InvalidToken("wrong nonce")
        except InvalidToken as exc:
            log.info("sign-in refused (app): %s", exc)
            return leave("Google sign-in could not be verified. Returning to Market Hub…", error="refused")
        said = google_welcome(g)
        log.info("sign-in ok (app) new=%s", said["new"])
        return leave("Signed in. Returning to Market Hub…", code=google_flow.code(g.id, began["c"], said["new"]))

    @app.post("/api/app/auth/google/finish")
    def app_google_finish(request: Request, code: str = Body(embed=True, max_length=2048), verifier_: str = Body(embed=True, alias="verifier", max_length=200)) -> dict:
        """The code for the app's token: only for whoever holds the secret the sign-in began with."""
        allow(request)
        found = google_flow.redeem(code, verifier_)
        doc = users.get(found["i"]) if found else None
        if not doc:
            raise HTTPException(401, "That sign-in could not be completed. Try again.")
        user = {"id": found["i"], "email": doc.get("email", ""), "name": doc.get("name", ""), "picture": doc.get("picture", ""), "provider": "google"}
        return {"user": user, "new": bool(found.get("n")), "has_data": bool(doc.get("positions") or doc.get("watchlist")),
                "token": tokens.issue(user)}

    @app.post("/api/app/auth/apple/begin")
    def app_apple_begin(request: Request) -> dict:
        """The nonce the app hands to the phone's sign-in with Apple, to come back inside the token."""
        allow(request)
        return {"nonce": apple_flow.nonce()}

    @app.post("/api/app/auth/apple")
    def app_apple(request: Request, identity_token: str = Body(embed=True, max_length=8192), name: str = Body("", embed=True, max_length=200)) -> dict:
        """Apple's identity token for the app's token. The name is what the phone gave the app the
        first time; nothing else the app says is believed, only the token. No cookie is read or set."""
        allow(request)
        try:
            a = applesignin.verify(identity_token, apple_flow, apple_checks)
        except InvalidToken as exc:
            log.info("sign-in refused (app, apple): %s", exc)
            raise HTTPException(401, "Sign in with Apple could not be verified.") from None
        doc = users.get(a.id)
        new = doc is None
        if new:
            doc = empty(a.id)
        user = {"id": a.id, "email": a.email or doc.get("email", ""), "name": applesignin.shown_name(name, doc.get("name", "")),
                "picture": "", "provider": "apple"}
        users.put(a.id, touch(doc, email=user["email"], name=user["name"], picture="", provider="apple"))
        log.info("sign-in ok (app, apple) new=%s", new)
        return {"user": user, "new": new, "has_data": bool(doc.get("positions") or doc.get("watchlist")), "token": tokens.issue(user)}

    @app.post("/api/app/auth/apple/revoke")
    def app_apple_revoke(request: Request, identity_token: str = Body(embed=True, max_length=8192),
                         authorization_code: str = Body(embed=True, max_length=2048)) -> dict:
        """Before an Apple account is deleted: its owner has just confirmed on the phone, and Apple
        is told to forget the app for it. Only for the account that is signed in. Nothing is kept."""
        allow(request)
        user = current_user(request)
        if user.get("provider") != "apple":
            raise HTTPException(400, "This account does not sign in with Apple.")
        if revoker is None:
            raise HTTPException(404, "There is nothing to tell Apple here.")
        try:
            a = applesignin.verify(identity_token, apple_flow, apple_checks)
        except InvalidToken as exc:
            log.info("apple revoke refused: %s", exc)
            raise HTTPException(401, "Sign in with Apple could not be verified.") from None
        if not secrets.compare_digest(a.id, str(user["id"])):
            log.info("apple revoke refused: another account")
            raise HTTPException(401, "That is not the Apple account you are signed in with.")
        try:
            revoker.revoke(authorization_code)
        except NotRevoked as exc:
            log.info("apple revoke failed: %s", exc)
            raise HTTPException(502, "Apple could not be told. Your account can still be deleted.") from None
        log.info("apple revoke ok")
        return {"revoked": True}

    @app.get("/api/app/web/enter")
    def app_web_enter(request: Request, to: str = Query(max_length=600)) -> Response:
        """The page the app opens inside itself, on its way to a tool. The only route under
        /api/app/ that sets the session cookie, and only for a request with a good token."""
        allow(request)
        user = tokens.read(app_token(request))
        if not user:
            return HTMLResponse(entering_page(None, "Sign in to the app again to open this."), 401)
        if not tool_pages.allowed(to):
            return HTMLResponse(entering_page(None, "This is not one of Market Hub's tools."), 400)
        request.session.clear()
        request.session["user"] = user
        log.info("tool opened in the app")
        return HTMLResponse(entering_page(to, "Opening…"))

    @app.get("/api/me")
    def me(request: Request) -> dict:
        user = current_user(request)
        doc = load(user)
        # "moderator" is the owner: the account page then shows the comments readers reported.
        return {"user": user, "has_data": bool(doc.get("positions") or doc.get("watchlist")), "moderator": opinion.can_moderate(user)}

    @app.delete("/api/me")
    def delete_me(request: Request) -> dict:
        user = current_user(request)
        opinion.forget(user["id"])  # the comments go with the account
        submissions.forget(user["id"])  # and the articles sent in for review
        community.stop(user["id"])  # and so does the shared portfolio
        competitions.forget(user["id"])  # and the entries to the competition
        bots.forget(user["id"])  # and the bot, with its key
        option_strategies.forget(user["id"])  # and the strategies kept in Options Lab
        accounts.forget(user)  # and its password, if it had one of ours
        users.delete(user["id"])
        request.session.clear()
        log.info("account deleted")
        return {"deleted": True}

    @app.get("/api/me/option-strategies")
    def my_option_strategies(request: Request) -> dict:
        return {"strategies": option_strategies.get(current_user(request)["id"])}

    @app.get("/api/portfolio")
    def portfolio(request: Request) -> dict:
        doc = load(current_user(request))
        return {"positions": doc.get("positions", []), "watchlist": doc.get("watchlist", []),
                "updated_utc": doc.get("updated_utc")}

    @app.put("/api/portfolio")
    def save_portfolio(request: Request, positions: list = Body(default=[]), watchlist: list = Body(default=[])) -> dict:
        user = current_user(request)
        try:
            pos, watch = clean(positions, watchlist, known=known)
        except InvalidPortfolio as exc:
            raise HTTPException(400, str(exc)) from None
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        doc = touch(load(user), positions=pos, watchlist=watch)
        if doc.get("shared"):
            # What is shared follows what is held; with nothing held, nothing is shared.
            try:
                community.refresh(user["id"], figures(doc))
            except MarketUnavailable:
                pass
            doc["shared"] = bool(pos)
        users.put(user["id"], doc)
        return {"positions": pos, "watchlist": watch, "updated_utc": doc["updated_utc"]}

    @app.get("/api/dashboard")
    def dash(request: Request) -> dict:
        user = current_user(request)
        allow(request)
        doc = load(user)
        try:
            d = figures(doc)
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        if doc.get("shared"):
            community.refresh(user["id"], d)
        return d

    @app.get("/api/insights")
    def insights(request: Request) -> dict:
        """The portfolio read back in a few sentences: the model's when it answers, the code's
        otherwise. What the model is sent is in insights.facts: no amounts, nothing of the user."""
        user = current_user(request)
        allow(request)
        doc = load(user)
        try:
            d = figures(doc)
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        return (writer.read(user["id"], doc, d) if writer else None) or d["insights"]

    def watched(request: Request, t: str | None = None) -> tuple[dict, str | None]:
        """The signed-in user and, where one is asked for, a ticker the directory knows."""
        user = current_user(request)
        if not watching.allow(_client_address(request)):
            raise HTTPException(429, "Too many requests from this address. Try again later.")
        if t is None:
            return user, None
        t = symbol(t).replace(".", "-")
        try:
            if not known(t):
                raise HTTPException(404, "No such stock.")
        except MarketUnavailable:
            pass  # the list of companies is not there to check against: the provider will say
        return user, t

    @app.get("/api/watchlist")
    def watchlist(request: Request) -> dict:
        user, _ = watched(request)
        return watch.board(load(user))

    @app.get("/api/watchlist/stock")
    def watch_stock(request: Request, t: str = Query(max_length=12)) -> dict:
        _, ticker = watched(request, t)
        found = watch.stock(ticker)
        if not found:
            raise HTTPException(404, "No prices for that stock right now.")
        return found

    @app.get("/api/watchlist/bars")
    def watch_bars(request: Request, t: str = Query(max_length=12)) -> dict:
        _, ticker = watched(request, t)
        found = watch.bars(ticker)
        if not found:
            raise HTTPException(404, "No prices for that stock right now.")
        return found

    @app.get("/api/watchlist/read")
    def watch_read(request: Request, t: str = Query(max_length=12)) -> dict:
        """What the model is sent is in watch.facts: one ticker and its market figures, nothing of the user."""
        user, ticker = watched(request, t)
        found = watch.read(user["id"], ticker)
        if not found:
            raise HTTPException(404, "No prices for that stock right now.")
        return found

    @app.get("/api/sharing")
    def sharing(request: Request) -> dict:
        return community.status(current_user(request)["id"])

    @app.put("/api/sharing")
    def set_sharing(request: Request, enabled: bool = Body(embed=True), handle: str = Body("", embed=True, max_length=40)) -> dict:
        user = current_user(request)
        allow(request)
        doc = load(user)
        if not enabled:
            users.put(user["id"], touch(doc, shared=False))
            return community.stop(user["id"])
        try:
            status = community.share(user["id"], handle, figures(doc))
        except SharingRefused as exc:
            raise HTTPException(400, str(exc)) from None
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        users.put(user["id"], touch(doc, shared=True))
        log.info("portfolio shared")
        return status

    @app.get("/api/community")
    def board(request: Request) -> dict:
        user = current_user(request)
        allow(request)
        try:
            d = figures(load(user))
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        periods = d["performance"]["periods"]
        return {**community.board(user["id"], d),
                "periods": [{"key": p["key"], "label": p["label"]} for p in periods if p["key"] in BOARD_PERIODS],
                "indices": [{"ticker": i["ticker"], "name": i["name"], "performance": {p["key"]: p["indices"].get(i["ticker"]) for p in periods}}
                            for i in d["performance"]["indices"]]}

    @app.get("/api/competitions")
    def competition(request: Request) -> dict:
        user = current_user(request)
        allow(request)
        return competitions.overview(user["id"])

    @app.put("/api/competitions/entry")
    def enter_competition(request: Request, handle: str = Body(embed=True, max_length=40), picks: list = Body(embed=True)) -> dict:
        user = current_user(request)
        allow(request)
        try:
            entry = competitions.enter(user["id"], handle, picks)
        except competitions_.Refused as exc:
            raise HTTPException(400, str(exc)) from None
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        log.info("competition entry saved")
        return entry

    @app.delete("/api/competitions/entry")
    def leave_competition(request: Request) -> dict:
        competitions.withdraw(current_user(request)["id"])
        return {"withdrawn": True}

    @app.get("/api/competitions/mine")
    def my_entries(request: Request) -> dict:
        """What the account page shows as kept: the user's own entries."""
        return {"entries": competitions.mine(current_user(request)["id"])}

    # --- The bot competition, from the page ---

    def refused(exc: bots_.Refused) -> JSONResponse:
        return JSONResponse({"detail": str(exc), "problems": exc.problems}, status_code=400)

    @app.get("/api/bots")
    def bot_board(request: Request) -> dict:
        user = current_user(request)
        allow(request)
        return bots.overview(user["id"])

    @app.post("/api/bots/refresh")
    def refresh_bots(request: Request) -> dict:
        """A visit that finds the bots behind the last close asks for this: not more often than
        the competition allows, and not while another refresh runs."""
        current_user(request)
        allow(request)
        return bots.refresh()

    @app.post("/api/bots/kit")
    def bot_kit(request: Request) -> Response:
        user = current_user(request)
        allow(request)
        key = bots.issue_key(user["id"])
        log.info("bot kit downloaded with a new key")
        return Response(bots_.kit(str(request.base_url).rstrip("/"), key), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="markethub-bot.zip"'})

    @app.post("/api/bots/key")
    def new_bot_key(request: Request) -> dict:
        user = current_user(request)
        allow(request)
        log.info("bot key issued")
        return {"key": bots.issue_key(user["id"]), "status": bots.key_status(user["id"])}

    @app.delete("/api/bots/key")
    def drop_bot_key(request: Request) -> dict:
        bots.revoke_key(current_user(request)["id"])
        return {"revoked": True}

    @app.delete("/api/bots/mine")
    def withdraw_bot(request: Request) -> dict:
        bots.withdraw(current_user(request)["id"])
        log.info("bot withdrawn")
        return {"withdrawn": True}

    @app.get("/api/bots/mine")
    def kept_bot(request: Request) -> dict:
        """What the account page shows as kept: the user's bot and whether they have a key."""
        return bots.kept(current_user(request)["id"])

    # --- The bot competition, from the member's agent ---

    def agent(request: Request) -> str:
        """The member a bot key belongs to. The cookie is never looked at here."""
        allow(request)
        user_id = bots.who(bearer(request.headers.get("authorization")))
        if not user_id:
            raise HTTPException(401, "No key, or not a good one: make one on the Bot competition page of My Hub and put it in .env.")
        return user_id

    @app.get("/api/bot/spec")
    def bot_spec(request: Request) -> dict:
        allow(request)
        return bots_.spec()

    @app.post("/api/bot/check")
    def check_bot(request: Request, bot: dict = Body(embed=True)):
        agent(request)
        try:
            return bots.check(bot)
        except bots_.Refused as exc:
            return refused(exc)
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None

    @app.post("/api/bot/backtest")
    def backtest_bot(request: Request, bot: dict = Body(embed=True), years: int = Body(1, embed=True)):
        user_id = agent(request)
        if not backtesting.allow(user_id):
            raise HTTPException(429, f"That is {BOT_BACKTESTS_PER_USER_PER_HOUR} backtests in an hour. Try again later.")
        try:
            return bots.backtest(bot, years)
        except bots_.Refused as exc:
            return refused(exc)
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None

    @app.put("/api/bot")
    def submit_bot(request: Request, bot: dict = Body(embed=True), handle: str | None = Body(None, embed=True, max_length=40)):
        user_id = agent(request)
        if not sending_bots.allow(user_id):
            raise HTTPException(429, f"That is {BOT_SUBMISSIONS_PER_USER_PER_DAY} bots sent in a day. Try again tomorrow.")
        try:
            mine = bots.submit(user_id, bot, handle)
        except bots_.Refused as exc:
            return refused(exc)
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        log.info("bot sent in")
        return mine

    @app.get("/api/bot")
    def my_bot(request: Request) -> dict:
        user_id = agent(request)
        return {"bot": bots.mine(user_id), "name": bots.overview(user_id)["name"]}

    def month_thread(month: str, writing: bool = False) -> str:
        """The discussion of a month: any month up to the one entries are open for is read, and
        the one being played and the one about to be are written in."""
        running, open_ = competitions.months()
        if not competitions_.MONTH.fullmatch(month) or month > open_ or (writing and month < running):
            raise HTTPException(404, "No such month.")
        return competitions_.thread(month)

    @app.get("/api/competitions/comments")
    def competition_comments(request: Request, month: str = Query(max_length=7)) -> dict:
        """Members only, like the standings they hang from."""
        user = current_user(request)
        return {"comments": opinion.comments(month_thread(month), user), "signed_in": True, "moderator": opinion.can_moderate(user)}

    @app.post("/api/competitions/comments")
    def competition_comment(request: Request, month: str = Body(max_length=7), text: str = Body(max_length=8000),
                            parent_id: str | None = Body(None, max_length=40)) -> dict:
        user = current_user(request)
        if not commenting.allow(user["id"]):
            raise HTTPException(429, "That is a lot of comments in an hour. Try again later.")
        try:
            # Shown with the name the member plays under, when they have one.
            return opinion.post(user, month_thread(month, writing=True), text, parent_id, name=competitions.name(user["id"]) or None)
        except Refused as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/search")
    def search(request: Request, q: str = Query(min_length=1, max_length=60)) -> dict:
        try:
            found = [{"ticker": c.ticker, "name": c.name} for c in directory.search(q)]
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        # Funds are not in the SEC's list of companies: the provider's own search finds them.
        funds = market.find_funds(q) if len(q.strip()) >= 2 and hasattr(market, "find_funds") else []
        return {"companies": merge_found(found, funds, q)}

    def known(ticker: str) -> bool:
        """Whether a ticker can go in a portfolio or a watchlist: a company in the SEC's list, or
        a fund the provider knows."""
        return directory.known(ticker) or bool(market.profile(ticker).get("is_etf"))

    def symbol(value: str) -> str:
        value = value.strip().upper()
        if not SYMBOL.match(value):
            raise HTTPException(400, "Not a ticker.")
        return value

    def company_name(ticker: str) -> str | None:
        try:
            found = directory.get(ticker)
        except MarketUnavailable:
            return None
        if not found:
            return None
        # The SEC writes names in capitals ("COCA COLA CO"); headlines read better without.
        return found.name.title() if found.name.isupper() else found.name

    @app.get("/api/public/overview")
    def public_overview(detail: bool = Query(False)) -> dict:
        return markets.overview(detail=detail)

    @app.get("/api/public/chart")
    def public_chart(symbol_: str = Query(alias="symbol", max_length=12), range_: str = Query("1Y", alias="range", max_length=4)) -> dict:
        t = symbol(symbol_)
        try:
            return markets.chart(t, range_, name=company_name(t))
        except MarketUnavailable:
            raise HTTPException(503, "Prices for this range are not available right now.") from None

    @app.get("/api/public/quote")
    def public_quote(t: str = Query(max_length=12)) -> dict:
        t = symbol(t)
        try:
            q = markets.quote(t, name=company_name(t))
        except MarketUnavailable:
            raise HTTPException(404, "No quote for that ticker right now.") from None
        # The company's own items from the news desk; sample headlines are not shown on a quote.
        q["news"] = [] if news.sample else news.news(tickers={t}, limit=5)["items"]
        return q

    @app.get("/api/public/quote/more")
    def public_quote_more(t: str = Query(max_length=12)) -> dict:
        return markets.more(symbol(t))

    @app.get("/api/public/news")
    def public_news(category: str | None = Query(None, max_length=30), ticker: str | None = Query(None, max_length=12),
                    limit: int = Query(20, ge=1, le=200)) -> dict:  # up to the whole front (NEWS_FRONT_ITEMS)
        t = symbol(ticker) if ticker else None
        return news.news(category=category, tickers={t} if t else None, limit=limit, name=company_name(t) if t else None)

    @app.get("/api/public/news/item")
    def public_news_item(id_: str = Query(alias="id", max_length=80)) -> dict:
        """One item with its article. The page links to the source from there."""
        found = news.item(id_)
        if not found:
            raise HTTPException(404, "No such news item.")
        return found

    @app.post("/api/public/news/refresh")
    def refresh_news(request: Request) -> dict:
        """Asked by a page that was told the news is stale. The desk decides whether to read the
        sources: not when the news is fresh, and not while another refresh runs."""
        allow(request)
        return news.refresh()

    @app.get("/api/news/mine")
    def my_news(request: Request) -> dict:
        """The news about the companies the user holds or follows."""
        doc = load(current_user(request))
        tickers = {p["ticker"] for p in doc.get("positions", [])} | set(doc.get("watchlist", []))
        if not tickers:
            return news.news(limit=1) | {"items": []}
        return news.news(tickers=tickers, limit=20)

    @app.get("/api/public/opinion")
    def public_opinion(limit: int = Query(50, ge=1, le=100)) -> dict:
        return {"articles": opinion.articles(limit)}

    @app.get("/api/public/opinion/item")
    def public_opinion_item(slug: str = Query(max_length=100)) -> dict:
        found = opinion.article(slug)
        if not found:
            raise HTTPException(404, "No such article.")
        return found

    @app.get("/api/public/opinion/cover")
    def public_opinion_cover(slug: str = Query(max_length=100), v: str = Query("", max_length=40)) -> Response:
        found = opinion.cover(slug, v)
        if not found:
            raise HTTPException(404, "No such picture.")
        # A version names one picture for good; without it, the address may show another tomorrow.
        keep = "public, max-age=31536000, immutable" if v else "public, max-age=300"
        return Response(found, media_type="image/jpeg", headers={"Cache-Control": keep})

    @app.get("/api/public/instagram")
    def public_instagram(limit: int = Query(12, ge=1, le=24)) -> dict:
        return posts.latest(limit)

    @app.get("/api/public/x")
    def public_x(limit: int = Query(12, ge=1, le=24)) -> dict:
        return x_posts.latest(limit)

    @app.get("/api/public/instagram/cover")
    def public_instagram_cover(id: str = Query(max_length=40), v: str = Query("", max_length=40)) -> Response:
        found = posts.cover(id, v)
        if not found:
            raise HTTPException(404, "No such picture.")
        keep = "public, max-age=31536000, immutable" if v else "public, max-age=300"
        return Response(found, media_type="image/jpeg", headers={"Cache-Control": keep})

    @app.get("/api/public/opinion/comments")
    def public_comments(request: Request, slug: str = Query(max_length=100)) -> dict:
        """Anyone reads the thread. A signed-in reader is told which comments are theirs."""
        user = signed_in(request)
        if slug.startswith(MEMBERS_ONLY):  # a thread of the community is not a public one
            raise HTTPException(404, "No such article.")
        return {"comments": opinion.comments(slug, user), "signed_in": bool(user), "moderator": opinion.can_moderate(user)}

    @app.post("/api/opinion/comments")
    def comment(request: Request, slug: str = Body(max_length=100), text: str = Body(max_length=8000),
                parent_id: str | None = Body(None, max_length=40)) -> dict:
        user = current_user(request)
        if not commenting.allow(user["id"]):
            raise HTTPException(429, "That is a lot of comments in an hour. Try again later.")
        try:
            return opinion.add(user, slug, text, parent_id)
        except Refused as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/opinion/mine")
    def my_comments(request: Request) -> dict:
        """What the account page shows as kept: the user's own comments."""
        return {"comments": opinion.mine(current_user(request)["id"])}

    @app.delete("/api/opinion/comments/{comment_id}")
    def remove_comment(request: Request, comment_id: str) -> dict:
        user = current_user(request)
        try:
            return {"deleted": opinion.remove(user, comment_id)}
        except PermissionError:
            raise HTTPException(403, "That comment is not yours.") from None

    @app.post("/api/comments/{comment_id}/report")
    def report_comment(request: Request, comment_id: str) -> dict:
        """Any comment of any thread the reader can see. Who reported what is never told to anybody."""
        user = current_user(request)
        if not commenting.allow(user["id"]):
            raise HTTPException(429, "That is a lot in an hour. Try again later.")
        try:
            return {"reported": opinion.report(user, comment_id)}
        except Refused as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/blocks")
    def my_blocks(request: Request) -> dict:
        return {"blocked": opinion.blocked(current_user(request)["id"])}

    @app.post("/api/blocks")
    def block_author(request: Request, comment_id: str = Body(embed=True, max_length=40)) -> dict:
        """The author of a comment, named by the comment: nobody is ever handed an account's id."""
        user = current_user(request)
        try:
            return {"blocked": opinion.block(user, comment_id)}
        except Refused as exc:
            raise HTTPException(400, str(exc)) from None

    @app.delete("/api/blocks/{key}")
    def unblock_author(request: Request, key: str) -> dict:
        return {"unblocked": opinion.unblock(current_user(request)["id"], key)}

    @app.get("/api/moderation/reports")
    def reported_comments(request: Request) -> dict:
        try:
            return {"comments": opinion.reports(current_user(request))}
        except PermissionError:
            raise HTTPException(403, "Only the owner reviews reports.") from None

    @app.post("/api/moderation/reports/{comment_id}/keep")
    def keep_comment(request: Request, comment_id: str) -> dict:
        try:
            return {"kept": opinion.keep(current_user(request), comment_id)}
        except PermissionError:
            raise HTTPException(403, "Only the owner reviews reports.") from None

    @app.get("/api/opinion/submissions")
    def my_submissions(request: Request) -> dict:
        """The articles the user sent in, as they are kept, and what the form asks of one."""
        user = current_user(request)
        return {"open": submissions.open, "articles": submissions.mine(user["id"]), "limits": submissions_.LIMITS,
                "per_day": SUBMISSIONS_PER_USER_PER_DAY}

    @app.post("/api/opinion/submissions")
    def submit(request: Request, title: str = Body(max_length=400), dek: str = Body(max_length=1000), body: str = Body(max_length=40000),
               sources: list = Body(default=[], max_length=40), tickers: list = Body(default=[], max_length=40),
               byline: str = Body("", max_length=200), agree: bool = Body(False)) -> dict:
        """An article for review. It is kept for the owner to read: it is not published."""
        user = current_user(request)
        allow(request)
        if not submissions.open:
            raise HTTPException(503, "Articles cannot be sent in right now.")
        try:
            article = submissions_.clean(title, dek, body, sources, tickers, byline, agree, name=user.get("name", ""))
            submissions.room(user)
            # Counted only once it could be taken: a text that is too short costs nothing.
            if not submitting.allow(user["id"]):
                raise HTTPException(429, "That is the most articles one account can send in a day. Try again tomorrow.")
            return submissions.send(user, article)
        except submissions_.Refused as exc:
            raise HTTPException(400, str(exc)) from None
        except HTTPException:
            raise
        except Exception as exc:  # the bucket did not answer: say so, and log no text
            log.error("submission not kept: %s", type(exc).__name__)
            raise HTTPException(503, "The article could not be kept right now. Nothing was sent: try again in a moment.") from None

    @app.delete("/api/opinion/submissions/{submission_id}")
    def withdraw_submission(request: Request, submission_id: str) -> dict:
        return {"withdrawn": submissions.withdraw(current_user(request)["id"], submission_id)}

    # --- Search engines ------------------------------------------------------------------------

    @app.get("/robots.txt", include_in_schema=False)
    def robots_txt() -> Response:
        return Response(seo.robots(SITE_URL), media_type="text/plain")

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap_xml() -> Response:
        return Response(seo.sitemap(SITE_URL, opinion.articles(limit=10**6)), media_type="application/xml",
                        headers={"Cache-Control": "public, max-age=3600"})

    static_dir = static_dir or os.environ.get("MARKETHUB_STATIC_DIR", "")
    if static_dir and Path(static_dir).is_dir():
        built = Path(static_dir) / previews.PATH.strip("/") / "index.html"
        if built.is_file():
            article_page = built.read_text(encoding="utf-8")

            # An article's page leaves the server with the article in it: its title, dek and cover
            # in the head, for a shared link and for search engines, and its text in the body
            # (see previews.py). The rest of the site is the build as it is.
            # An article that is not there is a 404, so search engines do not keep an empty page;
            # one older than the list holds is read from the store (Opinion.older).
            @app.api_route(previews.PATH, methods=["GET", "HEAD"], include_in_schema=False)
            def opinion_article_page(request: Request, slug: str = "") -> HTMLResponse:
                card = opinion.card(slug) if len(slug) <= 100 else None
                whole = None
                try:
                    if card:
                        whole = opinion.kept(slug)
                    elif len(slug) <= 100:
                        card = whole = opinion.older(slug)
                except Exception as exc:  # the store did not answer
                    log.warning("article text not read for its page: %s", type(exc).__name__)
                    if not card:  # nobody can say whether it is there: ask to come back, do not say it is gone
                        return HTMLResponse(article_page, status_code=503, headers={"Retry-After": "300"})
                if not card:
                    return HTMLResponse(article_page, status_code=404)
                # Known but without its text, the page goes with its tags, and the script fetches the text.
                page = previews.article_page(article_page, card, previews.origin(article_page, str(request.base_url)), whole)
                return HTMLResponse(page, headers={"Cache-Control": "public, max-age=300"})

        built_list = Path(static_dir) / previews.LIST_PATH.strip("/") / "index.html"
        if built_list.is_file():
            list_page = built_list.read_text(encoding="utf-8")

            # The list of articles leaves the server with the articles in it, each title a link.
            @app.api_route(previews.LIST_PATH, methods=["GET", "HEAD"], include_in_schema=False)
            def opinion_list_page() -> HTMLResponse:
                return HTMLResponse(previews.list_page(list_page, opinion.articles(50)), headers={"Cache-Control": "public, max-age=300"})

        built_home = Path(static_dir) / "index.html"
        if built_home.is_file():
            home_page = built_home.read_text(encoding="utf-8")

            # The home page leaves the server with the newest opinion articles in it.
            @app.api_route(previews.HOME_PATH, methods=["GET", "HEAD"], include_in_schema=False)
            def home() -> HTMLResponse:
                return HTMLResponse(previews.home_page(home_page, opinion.articles(previews.HOME_ARTICLES)), headers={"Cache-Control": "public, max-age=300"})

        app.mount("/", StaticFiles(directory=static_dir, html=True), name="site")
    return app
