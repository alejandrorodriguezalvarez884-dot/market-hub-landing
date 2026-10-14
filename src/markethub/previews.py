"""What a link to an opinion article shows where it is shared (X, LinkedIn, WhatsApp, Slack...).

The article page is one static page that loads the article in the browser, so a site that reads
a link's Open Graph and Twitter Card tags, and runs no script, saw only the generic ones. The
service hands that page out with the article's own: its title, its dek, its cover and its
address. What is said comes from the article's card, which the list of articles already holds in
memory, so a crawler costs no read of the store. An unknown slug gets the page as it was built.
"""

from __future__ import annotations

import re
from html import escape
from urllib.parse import quote, urlsplit

SITE_NAME = "Market Hub"
PATH = "/opinion/article/"

# The tags the build writes for every page, which an article replaces with its own.
_GENERIC = re.compile(
    r'<title>[^<]*</title>'
    r'|<meta name="description" content="[^"]*"\s*/?>'
    r'|<meta property="og:[a-z_:]+" content="[^"]*"\s*/?>'
    r'|<meta name="twitter:[a-z_:]+" content="[^"]*"\s*/?>'
    r'|<link rel="canonical" href="[^"]*"\s*/?>')
_CANONICAL = re.compile(r'<link rel="canonical" href="([^"]*)"')
_CHARSET = re.compile(r'<meta charset="[^"]*"\s*/?>', re.IGNORECASE)


def origin(page: str, fallback: str) -> str:
    """The public address of the site, as the build names it in its canonical link; without one,
    the address the request came to."""
    found = _CANONICAL.search(page)
    parts = urlsplit(found.group(1) if found else fallback)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else fallback.rstrip("/")


def article_page(page: str, card: dict, site: str) -> str:
    """``page`` (the built article page) with the tags of the article ``card`` instead of the
    generic ones. ``site`` is the public address, as https://themarkethub.app."""
    slug = quote(card["slug"], safe="")
    address = f"{site}{PATH}?slug={slug}"
    dek = card.get("dek") or ""
    tags = [
        ("title", f"{card['title']} — {SITE_NAME}"),
        ('meta name="description"', dek),
        ('link rel="canonical"', address),
        ('meta property="og:type"', "article"),
        ('meta property="og:site_name"', SITE_NAME),
        ('meta property="og:title"', card["title"]),
        ('meta property="og:description"', dek),
        ('meta property="og:url"', address),
    ]
    cover = card.get("cover") or {}
    if cover.get("v"):
        image = f"{site}/api/public/opinion/cover?slug={slug}&v={quote(cover['v'], safe='')}"
        tags += [('meta property="og:image"', image), ('meta property="og:image:type"', "image/jpeg")]
        if cover.get("alt"):
            tags.append(('meta property="og:image:alt"', cover["alt"]))
        tags.append(('meta name="twitter:card"', "summary_large_image"))
    else:
        tags.append(('meta name="twitter:card"', "summary"))
    if card.get("published_utc"):
        tags.append(('meta property="article:published_time"', card["published_utc"]))
    head = "".join(_tag(name, value) for name, value in tags)
    page = _GENERIC.sub("", page)
    at = _CHARSET.search(page)
    cut = at.end() if at else page.find("<head>") + len("<head>")
    return page[:cut] + head + page[cut:]


def _tag(name: str, value: str) -> str:
    said = escape(value, quote=True)
    if name == "title":
        return f"<title>{said}</title>"
    if name.startswith("link"):
        return f'<{name} href="{said}">'
    return f'<{name} content="{said}">'
