"""What search engines are told about the portal: robots.txt and the sitemap.

Only Market Hub's own writing is offered to be indexed: the public sections and the opinion
articles (each article's page carries its own title and canonical address, previews.py). The
news items and the quotes are other sources' facts and figures; their pages, and those of My Hub,
say noindex in the site's own HTML (``noindex`` in Layout.astro).

Each page is also built in Spanish under /es/ (docs/i18n.md). A page that is in both languages is
listed in each, with the address of the other as its alternate (hreflang), as its own head says."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import quote
from xml.sax.saxutils import escape

# The public pages of the portal that are its own, in the order the sitemap lists them.
PAGES = ("/", "/today/", "/markets/", "/news/", "/opinion/", "/media/", "/tools/",
         "/contact/", "/privacy/", "/terms/")
ARTICLE_PATH = "/opinion/article/"


def spanish(path: str) -> str:
    """"/opinion/" in Spanish: "/es/opinion/"."""
    return f"/es{path}"


def robots(site: str) -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n"


def _rows(english: str, in_spanish: str | None, stamp: str = "") -> list[str]:
    """The rows of one page: its English address and, when there is one, its Spanish one, each
    naming both (and English as the default)."""
    if not in_spanish:
        return [f"<url><loc>{escape(english)}</loc>{stamp}</url>"]
    both = "".join(f'<xhtml:link rel="alternate" hreflang="{code}" href="{escape(url)}"/>'
                   for code, url in (("en", english), ("es", in_spanish), ("x-default", english)))
    return [f"<url><loc>{escape(url)}</loc>{stamp}{both}</url>" for url in (english, in_spanish)]


def sitemap(site: str, articles: list[dict], spanish_pages: Iterable[str] = PAGES, spanish_articles: bool = True) -> str:
    """``articles`` are the cards of the opinion articles, newest first. ``spanish_pages`` are the
    pages of ``PAGES`` built in Spanish too, and ``spanish_articles`` says whether the article page is."""
    in_spanish = set(spanish_pages)
    rows = []
    for p in PAGES:
        rows += _rows(site + p, site + spanish(p) if p in in_spanish else None)
    for a in articles:
        day = str(a.get("updated_utc") or a.get("published_utc") or "")[:10]
        stamp = f"<lastmod>{day}</lastmod>" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else ""
        address = f"{ARTICLE_PATH}?slug={quote(a['slug'], safe='')}"
        rows += _rows(site + address, site + spanish(address) if spanish_articles else None, stamp)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "\n".join(rows) + "\n</urlset>\n")
