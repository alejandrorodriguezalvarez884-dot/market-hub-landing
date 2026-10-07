"""The portal's service: the site and the API, from one origin.

    GET    /api/health
    GET    /api/config              Google client id and the tools' addresses (public)
    POST   /api/auth/google         {credential}: Google ID token -> session cookie
    POST   /api/auth/logout
    GET    /api/me                  the signed-in user, or 401
    DELETE /api/me                  delete the account and everything saved
    GET    /api/portfolio           positions and watchlist
    PUT    /api/portfolio           replace them
    POST   /api/auth/register       {email, password, name, captcha}: an account of ours, and its session
    POST   /api/auth/password       {email, password}: sign in to one
    PUT    /api/auth/password       {current, new}: change its password
    GET    /api/insights            the sentences that read the portfolio back, by the model when it answers
    GET    /api/sharing             whether the portfolio is shared, and under what name
    PUT    /api/sharing             {enabled, handle}: share it, rename it or stop
    GET    /api/community           the shared portfolios and where the user's stands
    GET    /api/dashboard           positions valued at today's prices, favourites, history
    GET    /api/search?q=           companies by ticker or name
    GET    /api/public/overview     markets: indices, rates, commodities, currencies, sectors, movers
                                    (?detail=1 adds 1-month, YTD and 1-year returns)
    GET    /api/public/chart        ?symbol=&range=  price bars for the charts
    GET    /api/public/quote        ?t=  a stock's figures and its own news
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

Market figures come from FMP when there is a key (live.py), else from sample.py; the overview
names any part that is sample data in "sample_sections". The news comes from news.py.

Everything else is the static site, when MARKETHUB_STATIC_DIR points at its build.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import accounts as accounts_
from . import dashboard
from .accounts import Accounts, LoginStore, default_logins
from .captcha import default_captcha, open_without
from .community import PERIODS as BOARD_PERIODS
from .community import Community, CommunityStore, default_community
from .community import Refused as SharingRefused
from .holdings import SampleData, sample_only
from .insights import default_writer
from .live import default_markets
from .news import default_news
from .opinion import Opinion, Refused, default_opinion
from .auth import InvalidToken, Verifier, google_verifier, verify
from .config import (PASSWORD_TRIES_PER_IP_PER_HOUR, REGISTRATIONS_PER_IP_PER_HOUR,
                     COMMENTS_PER_USER_PER_HOUR, COOKIE_DOMAIN, EARNINGS_RADAR_URL, FUNDAMENTALS_LAB_URL, GOOGLE_CLIENT_ID, PER_IP_PER_HOUR,
                     SECURE_COOKIES, SESSION_DAYS, SESSION_SECRET)
from .market import Directory, Fmp, MarketUnavailable
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


def create_app(users: UserStore | None = None, market: Fmp | None = None, directory: Directory | None = None,
               verifier: Verifier = google_verifier, client_id: str | None = None,
               session_secret: str | None = None, secure_cookies: bool | None = None,
               static_dir: str | None = None, cookie_domain: str | None = COOKIE_DOMAIN, markets=None,
               news=None, opinion: Opinion | None = None, community_store: CommunityStore | None = None,
               insight_writer="default", logins: LoginStore | None = None,
               password_cost: tuple[int, int, int] = accounts_.COST, captcha="default") -> FastAPI:
    """App factory. Tests pass their own pieces, so they need no network and no Google."""
    logging.basicConfig(level=logging.INFO)
    # httpx logs every request URL at INFO, and FMP takes the key in the query string: keep the
    # key out of the logs.
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    app = FastAPI(title="Market Hub", docs_url=None, redoc_url=None, openapi_url=None)
    users = users or default_users()
    market = market or Fmp()
    directory = directory or Directory()
    markets = markets or default_markets(market)
    news = news or default_news(markets, directory)
    opinion = opinion or Opinion(default_opinion())
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

    community = Community(community_store or default_community(), value=lambda positions: figures(mix(positions)),
                          sample_value=lambda positions: dashboard.build(mix(positions), stand_in, stand_in, sample=True))
    client_id = GOOGLE_CLIENT_ID if client_id is None else client_id
    secret = session_secret or SESSION_SECRET
    if not secret:
        log.warning("SESSION_SECRET is not set: using a random one, sessions end on restart")
        secret = secrets.token_urlsafe(32)
    secure = SECURE_COOKIES if secure_cookies is None else secure_cookies
    limiter = RateLimiter(PER_IP_PER_HOUR)
    commenting = RateLimiter(COMMENTS_PER_USER_PER_HOUR)
    # Checking a password is slow on purpose, and an account costs nothing to ask for: both are
    # counted per address they come from.
    signing = RateLimiter(PASSWORD_TRIES_PER_IP_PER_HOUR)
    registering = RateLimiter(REGISTRATIONS_PER_IP_PER_HOUR)

    origins = [o.strip() for o in os.environ.get("MARKETHUB_ALLOWED_ORIGINS", "").split(",") if o.strip()]

    @app.middleware("http")
    async def same_origin_writes(request: Request, call_next):
        """Writes must come from this site. With the session cookie set to SameSite=Lax this
        closes cross-site request forgery: a foreign page can neither send the cookie on a POST
        nor pass this check."""
        if request.method in UNSAFE and request.url.path.startswith("/api/"):
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
                           allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["content-type"])

    def current_user(request: Request) -> dict:
        user = request.session.get("user")
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
            # Whether an account can be made here, and the key of the captcha's widget if it takes one.
            "registration": registration,
            "turnstile_site_key": human.site_key if registration == "captcha" else None,
            "tools": {
                "earnings_radar": EARNINGS_RADAR_URL or None,
                "fundamentals_lab": FUNDAMENTALS_LAB_URL or None,
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
        doc = users.get(g.id)
        new = doc is None
        if new:
            doc = empty(g.id)
        # Profile fields are refreshed on every sign-in; they are only shown back to the user.
        users.put(g.id, touch(doc, email=g.email, name=g.name, picture=g.picture))
        request.session.clear()
        request.session["user"] = {"id": g.id, "email": g.email, "name": g.name, "picture": g.picture, "provider": "google"}
        log.info("sign-in ok new=%s", new)
        return {"user": request.session["user"], "new": new,
                "has_data": bool(doc.get("positions") or doc.get("watchlist"))}

    def enter(request: Request, user: dict, new: bool) -> dict:
        """Open the session of an account of ours, and keep its profile with its document."""
        doc = users.get(user["id"]) or empty(user["id"])
        users.put(user["id"], touch(doc, email=user["email"], name=user["name"], picture="", provider="password"))
        request.session.clear()
        request.session["user"] = user
        return {"user": user, "new": new, "has_data": bool(doc.get("positions") or doc.get("watchlist"))}

    def by_password(request: Request, limiter: RateLimiter, sorry: str) -> None:
        if not password_login:
            raise HTTPException(404, "Signing in with a password is not on.")
        if not limiter.allow(_client_address(request)):
            raise HTTPException(429, sorry)

    @app.post("/api/auth/register")
    def register(request: Request, email: str = Body(embed=True, max_length=300), password: str = Body(embed=True, max_length=1000),
                 name: str = Body(embed=True, max_length=200), captcha: str = Body("", embed=True, max_length=4096)) -> dict:
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
        return enter(request, user, new=True)

    @app.post("/api/auth/password")
    def sign_in_password(request: Request, email: str = Body(embed=True, max_length=300), password: str = Body(embed=True, max_length=1000)) -> dict:
        by_password(request, signing, "Too many attempts from this address. Try again later.")
        try:
            user = accounts.sign_in(email, password)
        except accounts_.Wrong:
            # The same words whether the address is unknown or the password is not its own.
            raise HTTPException(401, "That email and password do not match an account.") from None
        except accounts_.TooMany:
            raise HTTPException(429, "Too many wrong passwords for that email. Wait a few minutes and try again.") from None
        log.info("password sign-in ok")
        return enter(request, user, new=False)

    @app.put("/api/auth/password")
    def change_password(request: Request, current: str = Body(embed=True, max_length=1000), new: str = Body(embed=True, max_length=1000)) -> dict:
        user = current_user(request)
        if user.get("provider") != "password":
            raise HTTPException(400, "This account signs in with Google: it has no password here.")
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

    @app.get("/api/me")
    def me(request: Request) -> dict:
        user = current_user(request)
        doc = load(user)
        return {"user": user, "has_data": bool(doc.get("positions") or doc.get("watchlist"))}

    @app.delete("/api/me")
    def delete_me(request: Request) -> dict:
        user = current_user(request)
        opinion.forget(user["id"])  # the comments go with the account
        community.stop(user["id"])  # and so does the shared portfolio
        accounts.forget(user)  # and its password, if it had one of ours
        users.delete(user["id"])
        request.session.clear()
        log.info("account deleted")
        return {"deleted": True}

    @app.get("/api/portfolio")
    def portfolio(request: Request) -> dict:
        doc = load(current_user(request))
        return {"positions": doc.get("positions", []), "watchlist": doc.get("watchlist", []),
                "updated_utc": doc.get("updated_utc")}

    @app.put("/api/portfolio")
    def save_portfolio(request: Request, positions: list = Body(default=[]), watchlist: list = Body(default=[])) -> dict:
        user = current_user(request)
        try:
            pos, watch = clean(positions, watchlist, known=directory.known)
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

    @app.get("/api/search")
    def search(request: Request, q: str = Query(min_length=1, max_length=60)) -> dict:
        try:
            found = directory.search(q)
        except MarketUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        return {"companies": [{"ticker": c.ticker, "name": c.name} for c in found]}

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

    @app.get("/api/public/opinion/comments")
    def public_comments(request: Request, slug: str = Query(max_length=100)) -> dict:
        """Anyone reads the thread. A signed-in reader is told which comments are theirs."""
        user = request.session.get("user")
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

    static_dir = static_dir or os.environ.get("MARKETHUB_STATIC_DIR", "")
    if static_dir and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="site")
    return app
