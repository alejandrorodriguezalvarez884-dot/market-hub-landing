"""The opinion pages as they leave the server: with the article in them, not only a script that
fetches it.

The article page and the list are static pages that load the articles in the browser. A site that
reads a shared link's Open Graph and Twitter Card tags runs no script, and a search engine may not
run it either, or not soon: both saw an empty page. So the service hands those pages out already
filled. The article page carries the article's own title, dek, cover and address in its head,
with its structured data (schema.org Article), and the article itself in its body; the list page
carries the list, each title a link to its article. The page's script draws the same thing again
when it runs. What is said comes from the cards of the list the service holds in memory, and an
article's text is read once and kept, so a crawler costs no read of the store, and an invented
slug none at all. An unknown slug gets the page as it was built.

Everything taken from an article is escaped: nothing in an article can become markup.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from urllib.parse import quote, urlsplit

SITE_NAME = "The Market Hub"
PATH = "/opinion/article/"
LIST_PATH = "/opinion/"
SHARE_IMAGE = "/share.png"  # the site's own card (film/share.mjs), for an article without a cover
HOME_PATH = "/"
HOME_ARTICLES = 3  # the newest, on the home page

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


def article_page(page: str, card: dict, site: str, article: dict | None = None) -> str:
    """``page`` (the built article page) with the tags of the article ``card`` instead of the
    generic ones and, given the whole ``article``, its text in place of the placeholder. ``site``
    is the public address, as https://themarkethub.app."""
    slug = quote(card["slug"], safe="")
    address = f"{site}{PATH}?slug={slug}"
    dek = card.get("dek") or ""
    image = _cover(card)
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
    if image:
        tags += [('meta property="og:image"', site + image), ('meta property="og:image:type"', "image/jpeg")]
        if card["cover"].get("alt"):
            tags.append(('meta property="og:image:alt"', card["cover"]["alt"]))
    else:  # without a cover of its own, the site's card
        tags += [('meta property="og:image"', site + SHARE_IMAGE), ('meta property="og:image:type"', "image/png"),
                 ('meta property="og:image:width"', "1200"), ('meta property="og:image:height"', "630")]
    tags.append(('meta name="twitter:card"', "summary_large_image"))
    if card.get("published_utc"):
        tags.append(('meta property="article:published_time"', card["published_utc"]))
    head = "".join(_tag(name, value) for name, value in tags) + _schema(_article_data(card, site, address, image))
    page = _GENERIC.sub("", page)
    at = _CHARSET.search(page)
    cut = at.end() if at else page.find("<head>") + len("<head>")
    page = page[:cut] + head + page[cut:]
    return _fill(page, "article", "piece", _article_html(article)) if article else page


def list_page(page: str, cards: list[dict]) -> str:
    """``page`` (the built list page) with the articles of ``cards``, newest first, in place of
    the placeholder: the newest leads, the rest follow, each with its title as a link."""
    if not cards:
        return page
    first, *rest = cards
    words = (f'<div class="min-w-0">{_overline(first)}'
             f'<h2 class="lede mt-3 !max-w-[22em] !text-ink-strong">{_to_article(first, "hover:underline")}</h2>'
             f'<p class="mt-4 max-w-2xl text-lg leading-relaxed text-ink">{escape(first.get("dek") or "")}</p>{_tags(first)}</div>')
    picture = _pictured(first, "lg:order-last")
    shape = "grid items-center gap-x-12 gap-y-6 lg:grid-cols-[1fr_1.15fr]" if picture else ""
    lead = f'<article class="sec pb-10 {shape}">{picture}{words}</article>'
    others = "".join(
        f'<article class="sec pb-2">{_pictured(a, "mb-5")}{_overline(a)}'
        f'<h2 class="mt-2 text-[1.5rem] font-medium leading-tight tracking-tight text-ink-strong">{_to_article(a, "hover:underline")}</h2>'
        f'<p class="mt-2.5 text-ink">{escape(a.get("dek") or "")}</p>{_tags(a)}</article>' for a in rest)
    return _fill(page, "div", "opinion", lead + f'<div class="grid gap-x-14 gap-y-10 md:grid-cols-2">{others}</div>')


def home_page(page: str, cards: list[dict]) -> str:
    """``page`` (the built home page) with the newest opinion articles of ``cards`` in its place for
    them, as one more part of the page. Without articles that place stays empty."""
    if not cards:
        return page
    items = "".join(
        f'<article data-rv style="--i:{i}">{_pictured(a, "mb-5")}{_overline(a)}'
        f'<h3 class="mt-2 text-lg font-medium leading-snug text-ink-strong">{_to_article(a, "hover:underline")}</h3>'
        f'<p class="mt-2 text-sm text-ink">{escape(a.get("dek") or "")}</p></article>' for i, a in enumerate(cards[:HOME_ARTICLES]))
    part = ('<section class="chapter" aria-labelledby="opinion-title">'
            '<header class="chapter-head" data-rv><h2 id="opinion-title" class="chapter-title">The latest from Opinion</h2></header>'
            f'<div class="mt-8 grid gap-x-14 gap-y-10 md:grid-cols-3">{items}</div>'
            f'<p class="mt-8 text-[13px]" data-rv><a href="{LIST_PATH}" class="link">All the articles</a></p></section>')
    return _fill(page, "div", "home-opinion", part)


# --- Structured data ----------------------------------------------------------------------------


def _article_data(card: dict, site: str, address: str, image: str | None) -> dict:
    publisher = {"@type": "Organization", "name": SITE_NAME, "url": f"{site}/", "logo": {"@type": "ImageObject", "url": f"{site}/logo.png"}}
    author = {"@type": "Person", "name": card["author"]} if card.get("author") else {"@type": "Organization", "name": SITE_NAME, "url": f"{site}/"}
    data = {"@context": "https://schema.org", "@type": "Article", "headline": card["title"], "description": card.get("dek") or "",
            "url": address, "mainEntityOfPage": address, "author": author, "publisher": publisher, "inLanguage": "en"}
    if card.get("published_utc"):
        data["datePublished"] = card["published_utc"]
        data["dateModified"] = card.get("updated_utc") or card["published_utc"]
    if image:
        data["image"] = [site + image]
    if card.get("tags"):
        data["keywords"] = ", ".join(card["tags"])
    return data


def _schema(data: dict) -> str:
    # No "<" at all, so nothing in it can end the script element: JSON says the same with "\u003c".
    said = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{said}</script>'


# --- The article, as the page's script draws it (lib/opinion.ts) ----------------------------------


def _article_html(a: dict) -> str:
    image = _cover(a)
    cover = (f'<img class="rounded-md bg-line object-cover mt-8 aspect-video w-full" src="{escape(image)}" '
             f'alt="{escape((a.get("cover") or {}).get("alt") or "")}" decoding="async">') if image else ""
    tickers = "".join(f'<a href="/quote/?t={quote(t, safe="")}" class="chip">{escape(t)}</a>' for t in a.get("tickers") or [])
    sources = "".join(f"<li>{_source(s)}</li>" for s in a.get("sources") or [] if s.get("url"))
    return (_overline(a)
            + f'<h1 class="mt-3 text-[2rem] font-medium leading-[1.12] tracking-tight text-ink-strong sm:text-[2.6rem]">{escape(a["title"])}</h1>'
            + f'<p class="mt-5 text-xl leading-relaxed text-ink-strong">{escape(a.get("dek") or "")}</p>'
            + cover
            + f'<div class="mt-8 space-y-5 text-[17px] leading-[1.7] text-ink">{prose(a.get("body") or "")}</div>'
            + (f'<p class="mt-8 flex flex-wrap gap-1.5">{tickers}</p>' if tickers else "")
            + (f'<footer class="sec mt-12"><div class="sec-head"><h2 class="sec-title">Sources</h2></div>'
               f'<ul class="space-y-1.5 text-sm text-ink">{sources}</ul></footer>' if sources else ""))


def _source(s: dict) -> str:
    url, title = str(s["url"]), escape(str(s.get("title") or s["url"]))
    if url.startswith("/"):
        return f'<a href="{escape(url)}" class="link">{title}</a>'
    return f'<a href="{escape(url)}" class="link" target="_blank" rel="noopener">{title}</a> ↗'


def _overline(a: dict) -> str:
    by = f'<span class="text-ink">By {escape(a["author"])}</span>' if a.get("author") else ""
    when = _day(a.get("published_utc") or "")
    return (f'<p class="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12.5px] text-muted">'
            f'<span class="font-medium text-ink-strong">{escape(a.get("kind") or "")}</span>{by}'
            f'<time datetime="{escape(a.get("published_utc") or "")}">{when}</time>'
            f'<span>{escape(str(a.get("minutes") or ""))} min read</span></p>')


def _day(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return f"{d:%B} {d.day}, {d.year}"


def _cover(a: dict) -> str | None:
    """The address of an article's picture, from the site's root, if it has one."""
    v = (a.get("cover") or {}).get("v")
    return f"/api/public/opinion/cover?slug={quote(a['slug'], safe='')}&v={quote(v, safe='')}" if v else None


def _to_article(a: dict, cls: str) -> str:
    return f'<a href="{PATH}?slug={quote(a["slug"], safe="")}" class="{cls}">{escape(a["title"])}</a>'


def _pictured(a: dict, cls: str) -> str:
    image = _cover(a)
    if not image:
        return ""
    alt = escape((a.get("cover") or {}).get("alt") or "")
    return (f'<a href="{PATH}?slug={quote(a["slug"], safe="")}" class="block {cls}" tabindex="-1">'
            f'<img class="rounded-md bg-line object-cover aspect-video w-full" src="{escape(image)}" alt="{alt}" loading="lazy" decoding="async"></a>')


def _tags(a: dict) -> str:
    chips = "".join(f'<span class="chip !font-sans">{escape(t)}</span>' for t in (a.get("tags") or [])[:4])
    return f'<p class="mt-3 flex flex-wrap gap-1.5">{chips}</p>' if chips else ""


# An article is written in a small part of Markdown: paragraphs, "## " headings, "> " quotes,
# "- " lists, **bold**, *emphasis* and [links](address). The same reading as prose() in
# lib/opinion.ts.
_MARK = re.compile(r"\*\*([^*]+)\*\*|\*([^*]+)\*|\[([^\]]+)\]\(([^)\s]+)\)")


def _inline(text: str) -> str:
    out, at = [], 0
    for m in _MARK.finditer(text):
        out.append(escape(text[at:m.start()]))
        if m[1] is not None:
            out.append(f'<strong class="font-semibold text-ink-strong">{escape(m[1])}</strong>')
        elif m[2] is not None:
            out.append(f"<em>{escape(m[2])}</em>")
        elif m[4].startswith("/"):
            out.append(f'<a href="{escape(m[4])}" class="link">{escape(m[3])}</a>')
        elif re.match(r"https?://", m[4]):
            out.append(f'<a href="{escape(m[4])}" class="link" target="_blank" rel="noopener">{escape(m[3])}</a>')
        else:
            out.append(escape(m[3]))
        at = m.end()
    out.append(escape(text[at:]))
    return "".join(out)


def prose(body: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", body.replace("\r\n", "\n")) if b.strip()]
    out = []
    for block in blocks:
        lines = block.split("\n")
        if block.startswith("## "):
            out.append(f'<h2 class="pt-4 text-[1.375rem] font-medium leading-snug tracking-tight text-ink-strong">{_inline(block[3:])}</h2>')
        elif all(line.startswith("> ") for line in lines):
            out.append(f'<blockquote class="border-l-2 border-line-strong pl-5 text-ink-strong">{_inline(" ".join(line[2:] for line in lines))}</blockquote>')
        elif all(line.startswith("- ") for line in lines):
            out.append('<ul class="list-disc space-y-2 pl-6">' + "".join(f"<li>{_inline(line[2:])}</li>" for line in lines) + "</ul>")
        else:
            out.append(f"<p>{_inline(' '.join(lines))}</p>")
    return "".join(out)


# --- Putting it in the page -----------------------------------------------------------------------


def _fill(page: str, tag: str, id_: str, inner: str) -> str:
    """``page`` with what is inside the element ``<tag id="id_">`` replaced by ``inner``. The page
    as it was if the element is not there."""
    start = re.search(rf'<{tag}\b[^>]*\bid="{re.escape(id_)}"[^>]*>', page)
    if not start:
        return page
    depth, at = 1, start.end()
    for m in re.compile(rf"<(/?){tag}\b[^>]*>").finditer(page, at):
        depth += -1 if m[1] else 1
        if depth == 0:
            return page[:start.end()] + inner + page[m.start():]
    return page


def _tag(name: str, value: str) -> str:
    said = escape(value, quote=True)
    if name == "title":
        return f"<title>{said}</title>"
    if name.startswith("link"):
        return f'<{name} href="{said}">'
    return f'<{name} content="{said}">'
