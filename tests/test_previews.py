"""A shared link to an opinion article shows the article: the page is handed out with its title,
dek and cover as Open Graph and Twitter Card tags, read from the list held in memory."""

import html
import re

import pytest
from conftest import ARTICLE, CLIENT_ID, fake_verifier
from fastapi.testclient import TestClient

from markethub.api import create_app
from markethub.instagram import Posts
from markethub.xposts import XPosts

SLUG = ARTICLE["slug"]
# The head the build writes for the article page, as Layout.astro writes it.
BUILT = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
         '<meta name="description" content="An opinion article of Market Hub, with its readers\' comments.">'
         '<link rel="canonical" href="https://themarkethub.app/opinion/article/"><meta property="og:type" content="website">'
         '<meta property="og:title" content="Opinion — Market Hub"><meta property="og:description" content="An opinion article of Market Hub, with its readers\' comments.">'
         '<meta property="og:url" content="https://themarkethub.app/opinion/article/"><title>Opinion — Market Hub</title></head>'
         '<body><article id="piece"></article></body></html>')


@pytest.fixture
def site(tmp_path, users, market, directory, opinion, shared, writer, logins, captcha, entries, reader, submissions, posts, x_posts):
    (tmp_path / "opinion" / "article").mkdir(parents=True)
    (tmp_path / "opinion" / "article" / "index.html").write_text(BUILT, encoding="utf-8")
    (tmp_path / "index.html").write_text("<html><head><title>Home</title></head></html>", encoding="utf-8")
    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=CLIENT_ID,
                     session_secret="test-secret", secure_cookies=False, opinion=opinion, community_store=shared,
                     insight_writer=writer, logins=logins, password_cost=(10, 8, 1), captcha=captcha, competition_store=entries,
                     stock_reader=reader, submissions=submissions, posts=Posts(posts), x_posts=XPosts(x_posts), static_dir=str(tmp_path))
    return TestClient(app)


def tags(page: str) -> dict[str, list[str]]:
    """Every meta and link tag of the page's head, by name, with its value unescaped."""
    found: dict[str, list[str]] = {}
    for name, value in re.findall(r'<(?:meta (?:name|property)="([^"]+)" content|link rel="(?:canonical)" href)="([^"]*)"', page):
        found.setdefault(name or "canonical", []).append(html.unescape(value))
    found["title"] = [html.unescape(t) for t in re.findall(r"<title>([^<]*)</title>", page)]
    return found


def test_an_article_page_carries_its_own_title_dek_and_address(site):
    r = site.get("/opinion/article/", params={"slug": SLUG})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    said = tags(r.text)
    address = f"https://themarkethub.app/opinion/article/?slug={SLUG}"
    assert said["title"] == ["A quiet jobs report — Market Hub"]
    assert said["og:title"] == ["A quiet jobs report"] and said["og:description"] == ["What 29,000 jobs say."]
    assert said["description"] == ["What 29,000 jobs say."] and said["og:type"] == ["article"]
    assert said["og:url"] == [address] and said["canonical"] == [address]
    # Without a cover there is no picture to show, and the card is the small one.
    assert "og:image" not in said and said["twitter:card"] == ["summary"]
    # The rest of the page is the build as it is, and the charset still comes first.
    assert r.text.startswith('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">') and '<article id="piece">' in r.text
    assert "public" in r.headers["cache-control"]


def test_a_cover_makes_the_large_card(site, opinion):
    opinion.store.articles[SLUG] = {**ARTICLE, "cover": {"alt": "A chart, drawn", "v": "7575463e7867"}}
    said = tags(site.get("/opinion/article/", params={"slug": SLUG}).text)
    assert said["og:image"] == [f"https://themarkethub.app/api/public/opinion/cover?slug={SLUG}&v=7575463e7867"]
    assert said["og:image:alt"] == ["A chart, drawn"] and said["twitter:card"] == ["summary_large_image"]


def test_what_an_article_says_is_escaped(site, opinion):
    opinion.store.articles[SLUG] = {**ARTICLE, "title": 'Fed "cuts" <script>alert(1)</script>', "dek": "A & B > C",
                                    "cover": {"alt": '"><img src=x>', "v": 'v"1'}}
    page = site.get("/opinion/article/", params={"slug": SLUG}).text
    assert "<script>alert" not in page and "<img src=x>" not in page and 'v"1' not in page
    said = tags(page)
    assert said["og:title"] == ['Fed "cuts" <script>alert(1)</script>'] and said["og:description"] == ["A & B > C"]
    assert said["og:image"][0].endswith("&v=v%221")


def test_an_unknown_slug_gets_the_page_as_built(site):
    for slug in ("no-such-article", "../etc/passwd", "", "x" * 300):
        r = site.get("/opinion/article/", params={"slug": slug} if slug else None)
        assert r.status_code == 200 and r.text == BUILT
    assert site.head("/opinion/article/", params={"slug": SLUG}).status_code == 200
    # Without the slash the static site sends it on to the page, query and all.
    moved = site.get("/opinion/article", params={"slug": SLUG}, follow_redirects=False)
    assert moved.status_code in (307, 308) and moved.headers["location"].endswith(f"/opinion/article/?slug={SLUG}")


def test_a_crawler_reads_nothing_from_the_store(site, opinion):
    reads = []
    front = opinion.store.front
    opinion.store.front = lambda: reads.append(1) or front()
    opinion.store.article = lambda slug: pytest.fail("the page reads the card, not the article")
    for _ in range(20):
        site.get("/opinion/article/", params={"slug": SLUG})
        site.get("/opinion/article/", params={"slug": "no-such-article"})
    assert len(reads) == 1  # the list, once a minute
