"""Where the news comes from. Each source answers items in the portal's shape.

- Official documents: the Form 8-K filings of the largest US companies (SEC) and the releases of
  the Federal Reserve, the BLS and the BEA. Public records, each with the link to its document.
  A filing and a monetary policy release carry a way to read the document, so the model can
  write the item from it (newswriter.py); until then they keep the title the code writes.
- The press: headlines from publishers' feeds. The headline, the publisher's name and the link
  are kept, never the text, and a headline that reads as advice is left out.

The items written from the day's own figures are in news.py. Nothing here sends anything but a
request for a public page.
"""

from __future__ import annotations

import hashlib
import html
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import urlsplit

import httpx

from .config import (BEA_FEED, BLS_FEEDS, FED_FEED, NEWS_MAX_AGE_DAYS, NEWS_PRESS_FEEDS, NEWS_UNIVERSE,
                     SEC_CURRENT_PAGES, SEC_CURRENT_URL)
from .market import Company, Directory, MarketUnavailable

log = logging.getLogger("markethub.newsfeeds")

ATOM = "{http://www.w3.org/2005/Atom}"
SEC = "https://www.sec.gov"

# Words of advice. The portal describes: a headline or a written item with them is not shown.
ADVICE = re.compile(r"\b(price targets?|undervalued|overvalued|cheap|bargains?|strong buy|(buy|sell|hold) rating"
                    r"|should (you |investors )?(buy|sell|hold)|investors should|a (screaming )?buy)\b", re.I)
# The press also writes about analysts' calls and stock picks, which are advice at one remove.
PICKS = re.compile(r"\b(upgrades?|downgrades?|upgraded|downgraded|stocks? to (buy|sell|watch|own)|buy now|buy the dip"
                   r"|top picks?|best stocks?|analysts? (say|says|see|sees)|outperform|underperform|overweight"
                   r"|underweight)\b", re.I)


class SourceDown(Exception):
    """A source that did not answer, or answered something unreadable."""


class Http:
    def __init__(self, client: httpx.Client | None = None, agent: str | None = None):
        self.client = client or httpx.Client(timeout=10, follow_redirects=True)
        # The SEC asks for a contact in the User-Agent; the other sources take the same one.
        self.agent = agent or os.environ.get("SEC_USER_AGENT", "").strip() or "market-hub contact@example.com"

    def _get(self, url: str, params: dict) -> httpx.Response:
        host = urlsplit(url).netloc
        try:
            resp = self.client.get(url, params=params or None, headers={"User-Agent": self.agent})
        except httpx.HTTPError:
            raise SourceDown(f"{host} did not answer") from None
        if resp.status_code >= 400:
            raise SourceDown(f"{host} answered {resp.status_code}")
        return resp

    def get(self, url: str, **params) -> bytes:
        return self._get(url, params).content

    def text(self, url: str, **params) -> str:
        return self._get(url, params).text


# --- Small tools -------------------------------------------------------------------------------


def utc(when: datetime) -> str:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).isoformat(timespec="seconds")


def _feed_date(text: str | None) -> datetime | None:
    """A feed's date, in either of the two ways feeds write it."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        when = datetime.fromisoformat(text) if text[:4].isdigit() else parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def _key(prefix: str, text: str) -> str:
    return f"{prefix}-{hashlib.sha1(text.encode()).hexdigest()[:12]}"


def _clean(text: str | None) -> str:
    return " ".join(html.unescape(text or "").split())


def _web(url: str | None) -> str | None:
    url = (url or "").strip()
    return url if url.startswith(("https://", "http://")) else None


def _xml(data: bytes, what: str) -> ET.Element:
    try:
        return ET.fromstring(data)
    except ET.ParseError:
        raise SourceDown(f"{what}: not a feed") from None


class _Text(HTMLParser):
    BREAKS = {"p", "div", "br", "tr", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6", "title"}
    HIDDEN = {"script", "style", "head", "ix:header"}  # ix:header is a filing's machine-readable preamble

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.HIDDEN:
            self._hidden += 1
        elif tag in self.BREAKS:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.HIDDEN:
            self._hidden = max(0, self._hidden - 1)
        elif tag in self.BREAKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._hidden:
            self.parts.append(data)


def html_text(markup: str) -> str:
    """The words of a page, a paragraph per line."""
    parser = _Text()
    parser.feed(markup)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    return "\n".join(line for line in lines if line)


def _sentences(text: str, n: int = 2, limit: int = 420) -> str:
    """The first sentences of a release, for a summary that is the agency's own words."""
    # A full stop after a single capital ("U.S. Bureau") is an abbreviation, not the end.
    parts = re.split(r"(?<![A-Z]\.)(?<=[.!?])\s+(?=[A-Z])", _clean(text))
    out = " ".join(parts[:n])
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + "…"


def item(id_: str, layer: str, category: str, title: str, source: str, url: str, published: datetime, summary: str = "",
         tickers: list[str] | None = None, written_by: str = "source") -> dict:
    return {"id": id_, "layer": layer, "category": category, "title": title, "summary": summary,
            "tickers": tickers or [], "source": source, "url": url, "published_utc": utc(published),
            "written_by": written_by,
            # How the news reads (bullish, bearish or neutral) and what it touches (a sector, or
            # "Macro"): set when the item is written, None until then.
            "sentiment": None, "scope": None}


# --- SEC: Form 8-K, the filing a company makes when something material happens ---------------

# What each item of the form reports, as the end of a sentence about the company, and where it
# goes. In order of weight: a filing with several items is titled by the first one here.
ITEMS = {
    "1.03": ("reported a bankruptcy or receivership", "Companies"),
    "4.02": ("said earlier financial statements should no longer be relied on", "Companies"),
    "2.02": ("published results", "Earnings"),
    "2.01": ("completed an acquisition or a sale of assets", "Companies"),
    "5.01": ("reported a change in control", "Companies"),
    "1.05": ("reported a material cybersecurity incident", "Companies"),
    "1.01": ("entered into a material agreement", "Companies"),
    "5.02": ("reported a change among its directors or officers", "Companies"),
    "2.05": ("reported the costs of an exit or a restructuring", "Companies"),
    "2.06": ("reported a material impairment", "Companies"),
    "1.02": ("ended a material agreement", "Companies"),
    "2.03": ("took on a new financial obligation", "Companies"),
    "3.01": ("received a notice about its listing", "Companies"),
    "4.01": ("changed its auditor", "Companies"),
    "8.01": ("reported an event to its investors", "Companies"),
    "7.01": ("made a disclosure to its investors", "Companies"),
}
ROUTINE = {"7.01", "8.01"}
FORM_CHARS = 6000  # of the form itself, what is read before its press release
FORM_TITLE = re.compile(r"^8-K - (.+?) \((\d{10})\) \(Filer\)\s*$")  # amendments (8-K/A) are left out
READABLE = (".htm", ".html", ".txt")


def sec_entries(xml: bytes) -> list[dict]:
    """The original 8-Ks on one page of EDGAR's feed of current filings."""
    out = []
    for e in _xml(xml, "sec").iter(f"{ATOM}entry"):
        title = FORM_TITLE.match(e.findtext(f"{ATOM}title") or "")
        link = e.find(f"{ATOM}link")
        summary = e.findtext(f"{ATOM}summary") or ""
        accession = re.search(r"AccNo:\s*(?:</b>)?\s*(\d{10}-\d{2}-\d{6})", summary)
        when = _feed_date(e.findtext(f"{ATOM}updated"))
        url = _web(link.get("href") if link is not None else None)
        if not (title and accession and when and url):
            continue
        out.append({"cik": int(title.group(2)), "filer": title.group(1), "accession": accession.group(1),
                    "items": re.findall(r"Item (\d\.\d\d)", summary), "filed": when, "url": url})
    return out


def _tidy(name: str) -> str:
    """The SEC writes many names in capitals ("COCA COLA CO")."""
    return name.title() if name.isupper() else name


def _list(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def filing_item(entry: dict, company: Company) -> dict | None:
    """A filing as an item, titled by code from the items of the form. None when the form reports
    nothing a reader follows (exhibits only, bylaws, votes)."""
    told = [code for code in ITEMS if code in entry["items"]]
    if not told:
        return None
    phrase, category = ITEMS[told[0]]
    codes = sorted(set(entry["items"]))
    found = item(f"sec-{entry['accession']}", "official", category, f"{_tidy(company.name)} {phrase}", "SEC filing",
                 entry["url"], entry["filed"], summary=f"Form 8-K filed with the SEC (item{'s' if len(codes) > 1 else ''} {_list(codes)}).",
                 tickers=[company.ticker], written_by="code")
    # Only a filing made under the two catch-all items can turn out to be nothing (slides for a
    # conference, say). Results, deals and changes of officers are always shown.
    found["_routine"] = set(told) <= ROUTINE
    return found


def filing_documents(index_html: str) -> list[tuple[str, str]]:
    """(type, address) of each document of a filing, from its index page."""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", index_html, re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)]
        href = re.search(r'href="([^"]+)"', row)
        if len(cells) < 4 or not href:
            continue
        path = href.group(1).split("/ix?doc=")[-1]  # the inline viewer's link, down to the document
        if path.startswith("/Archives/") and path.lower().endswith(READABLE):
            out.append((cells[3].upper(), SEC + path))
    return out


def _to_read(docs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """(label, address) of what the model reads: the form, where the company says what happened,
    and its first press release or statement (EX-99.1 by convention), where the figures are."""
    def rank(kind: str) -> int:
        return 0 if kind in ("EX-99.1", "EX-99.01", "EX-99") else 1
    form = [("Form 8-K", url) for kind, url in docs if kind == "8-K"][:1]
    exhibits = sorted((d for d in docs if d[0].startswith("EX-99")), key=lambda d: rank(d[0]))
    return form + [("Exhibit 99, attached to the form", url) for _, url in exhibits[:1]]


class SecFilings:
    def __init__(self, http: Http, directory: Directory, size: int = NEWS_UNIVERSE, pages: int = SEC_CURRENT_PAGES):
        self.http, self.directory, self.size, self.pages = http, directory, size, pages

    def __call__(self, since: datetime) -> list[dict]:
        try:
            universe = self.directory.largest(self.size)
        except MarketUnavailable as exc:
            raise SourceDown(str(exc)) from None
        out = []
        for page in range(self.pages):
            entries = sec_entries(self.http.get(SEC_CURRENT_URL, action="getcurrent", type="8-K", company="", dateb="",
                                                owner="include", start=page * 100, count=100, output="atom"))
            for e in entries:
                company = universe.get(e["cik"])
                found = filing_item(e, company) if company and e["filed"] >= since else None
                if found:
                    found["_read"] = self._reader(e["url"])
                    out.append(found)
            # The feed runs from the newest filing back: stop at the first page that reaches `since`.
            if len(entries) < 100 or min(e["filed"] for e in entries) < since:
                break
        return out

    def _reader(self, index_url: str) -> Callable[[], str]:
        def read() -> str:
            parts = []
            for label, url in _to_read(filing_documents(self.http.text(index_url))):
                try:
                    text = html_text(self.http.text(url))
                except SourceDown as exc:
                    log.warning("news document not read: %s", exc)
                    continue
                if label == "Form 8-K":
                    # Past the cover page (addresses, the list of securities), from the first item on.
                    start = re.search(r"^Item\s+\d\.\d\d", text, re.M)
                    text = text[start.start() if start else 0:][:FORM_CHARS]
                parts.append(f"[{label}]\n{text}")
            if sum(map(len, parts)) < 400:  # a cover page alone says nothing
                raise SourceDown("the filing has no readable document")
            return "\n\n".join(parts)
        return read


# --- Agencies ----------------------------------------------------------------------------------

# Releases of the Federal Reserve about one bank or about banking rules, not about the economy.
FED_SKIP = {"Orders on Banking Applications", "Enforcement Actions", "Banking and Consumer Regulatory Policy"}


def _rss(xml: bytes, what: str) -> list[dict[str, str]]:
    return [{child.tag: (child.text or "") for child in entry} for entry in _xml(xml, what).iter("item")]


class Fed:
    def __init__(self, http: Http, url: str = FED_FEED):
        self.http, self.url = http, url

    def __call__(self, since: datetime) -> list[dict]:
        out = []
        for r in _rss(self.http.get(self.url), "fed"):
            when, url, title = _feed_date(r.get("pubDate")), _web(r.get("link")), _clean(r.get("title"))
            if not (when and url and title) or r.get("category", "").strip() in FED_SKIP:
                continue
            found = item(_key("fed", url), "official", "Economy", title, "Federal Reserve", url, when)
            found["_read"] = lambda url=url: html_text(self.http.text(url))
            out.append(found)
        return out


class Bls:
    """The Bureau of Labor Statistics: jobs, consumer and producer prices, job openings. Its
    feeds carry the headline and the first paragraph of each release; the article is written
    from the release itself, or from that paragraph when the release cannot be fetched."""

    def _reader(self, url: str, title: str, opening: str) -> Callable[[], str]:
        def read() -> str:
            try:
                return html_text(self.http.text(url))
            except SourceDown as exc:
                log.warning("news document not read: %s", exc)
                return f"{title}\n\n{opening}"
        return read

    def __init__(self, http: Http, urls: list[str] = BLS_FEEDS):
        self.http, self.urls = http, urls

    def __call__(self, since: datetime) -> list[dict]:
        out, down = [], 0
        for feed in self.urls:
            try:
                root = _xml(self.http.get(feed), "bls")
            except SourceDown as exc:
                log.warning("news source down: %s", exc)
                down += 1
                continue
            for e in root.iter(f"{ATOM}entry"):
                link = e.find(f"{ATOM}link")
                when, url = _feed_date(e.findtext(f"{ATOM}published")), _web(link.get("href") if link is not None else None)
                title = _clean(e.findtext(f"{ATOM}title"))
                if when and url and title:
                    opening = _clean(e.findtext(f"{ATOM}content"))
                    found = item(_key("bls", e.findtext(f"{ATOM}id") or url), "official", "Economy", title,
                                 "Bureau of Labor Statistics", url, when, summary=_sentences(opening))
                    found["_read"] = self._reader(url, title, opening)
                    out.append(found)
        if down == len(self.urls):
            raise SourceDown("bls: no feed answered")
        return out


class Bea:
    """The Bureau of Economic Analysis: GDP, personal income and spending, trade."""

    def __init__(self, http: Http, url: str = BEA_FEED):
        self.http, self.url = http, url

    def __call__(self, since: datetime) -> list[dict]:
        out = []
        for r in _rss(self.http.get(self.url), "bea"):
            when, url, title = _feed_date(r.get("pubDate")), _web(r.get("link")), _clean(r.get("title"))
            if when and url and title:
                release = html_text(r.get("description", ""))  # the feed carries the release's own text
                found = item(_key("bea", url), "official", "Economy", title, "Bureau of Economic Analysis", url, when,
                             summary=_sentences(release))
                if len(release) > 200:
                    found["_read"] = lambda title=title, release=release: f"{title}\n\n{release}"
                out.append(found)
        return out


# --- The press ---------------------------------------------------------------------------------


def press_feeds(spec: str = NEWS_PRESS_FEEDS) -> list[tuple[str, str]]:
    pairs = (p.split("|", 1) for p in spec.split(",") if "|" in p)
    return [(name.strip(), url.strip()) for name, url in pairs if name.strip() and _web(url)]


def reads_as_advice(text: str, press: bool = False) -> bool:
    return bool(ADVICE.search(text) or (press and PICKS.search(text)))


class Press:
    def __init__(self, http: Http, feeds: list[tuple[str, str]] | None = None):
        self.http, self.feeds = http, press_feeds() if feeds is None else feeds

    def __call__(self, since: datetime) -> list[dict]:
        out, seen, down = [], set(), 0
        for name, feed in self.feeds:
            try:
                rows = _rss(self.http.get(feed), name)
            except SourceDown as exc:
                log.warning("news source down: %s", exc)
                down += 1
                continue
            for r in rows:
                when, url, title = _feed_date(r.get("pubDate")), _web(r.get("link")), _clean(r.get("title"))
                if not (when and url and 15 <= len(title) <= 220) or title.lower() in seen or reads_as_advice(title, press=True):
                    continue
                seen.add(title.lower())
                out.append(item(_key("press", url), "press", "Press", title, name, url, when))
        if self.feeds and down == len(self.feeds):
            raise SourceDown("press: no feed answered")
        return out


def default_sources(directory: Directory, http: Http | None = None) -> list[Callable[[datetime], list[dict]]]:
    http = http or Http()
    return [SecFilings(http, directory), Fed(http), Bls(http), Bea(http), Press(http)]


def recent(items: list[dict], now: datetime, days: int = NEWS_MAX_AGE_DAYS) -> list[dict]:
    floor = utc(now - timedelta(days=days))
    return [i for i in items if i["published_utc"] >= floor]
