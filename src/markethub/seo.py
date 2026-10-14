"""What search engines are told about the portal: robots.txt and the sitemap.

Only Market Hub's own writing is offered to be indexed: the public sections and the opinion
articles (each article's page carries its own title and canonical address, previews.py). The
news items and the quotes are other sources' facts and figures; their pages, and those of My Hub,
say noindex in the site's own HTML (``noindex`` in Layout.astro)."""

from __future__ import annotations

import re
from urllib.parse import quote
from xml.sax.saxutils import escape

# The public pages of the portal that are its own, in the order the sitemap lists them.
PAGES = ("/", "/today/", "/markets/", "/news/", "/opinion/", "/media/", "/tools/",
         "/contact/", "/privacy/", "/terms/")
ARTICLE_PATH = "/opinion/article/"


def robots(site: str) -> str:
    return f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n"


def sitemap(site: str, articles: list[dict]) -> str:
    """``articles`` are the cards of the opinion articles, newest first."""
    rows = [f"<url><loc>{escape(site + p)}</loc></url>" for p in PAGES]
    for a in articles:
        day = str(a.get("updated_utc") or a.get("published_utc") or "")[:10]
        stamp = f"<lastmod>{day}</lastmod>" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) else ""
        address = f"{site}{ARTICLE_PATH}?slug={quote(a['slug'], safe='')}"
        rows.append(f"<url><loc>{escape(address)}</loc>{stamp}</url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n")
