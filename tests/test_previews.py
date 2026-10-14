"""The opinion pages leave the server with the articles in them. An article's page carries its
title, dek and cover as Open Graph and Twitter Card tags, its structured data, and its text in
the body; the list page carries the list. What is read comes from memory: the list once a minute,
an article's text once."""

import html
import json
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
         '<body><article id="piece" class="mt-8"><div class="skeleton h-5 w-56"></div><div class="skeleton mt-4 h-24"></div></article>'
         '<section id="comments" hidden></section></body></html>')
# The list page as the build writes it: a placeholder where the articles go.
BUILT_LIST = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Opinion — The Market Hub</title></head><body><main>'
              '<h1>Opinion</h1><div id="opinion" class="mt-10"><div class="skeleton h-56"></div><div class="skeleton mt-8 h-40"></div></div>'
              '<footer>Footer</footer></main></body></html>')
# The home page as the build writes it: an empty place for the newest articles.
BUILT_HOME = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>The Market Hub</title></head><body>'
              '<div class="home"><section class="chapter">The rest</section><div id="home-opinion"></div></div><footer>Home footer</footer></body></html>')
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


@pytest.fixture
def site(tmp_path, users, market, directory, opinion, shared, writer, logins, captcha, entries, reader, submissions, posts, x_posts):
    (tmp_path / "opinion" / "article").mkdir(parents=True)
    (tmp_path / "opinion" / "article" / "index.html").write_text(BUILT, encoding="utf-8")
    (tmp_path / "opinion" / "index.html").write_text(BUILT_LIST, encoding="utf-8")
    (tmp_path / "index.html").write_text(BUILT_HOME, encoding="utf-8")
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
    assert said["title"] == ["A quiet jobs report — The Market Hub"]
    assert said["og:title"] == ["A quiet jobs report"] and said["og:description"] == ["What 29,000 jobs say."]
    assert said["description"] == ["What 29,000 jobs say."] and said["og:type"] == ["article"]
    assert said["og:url"] == [address] and said["canonical"] == [address] and said["og:site_name"] == ["The Market Hub"]
    # Without a cover of its own, the site's card.
    assert said["og:image"] == ["https://themarkethub.app/share.png"] and said["twitter:card"] == ["summary_large_image"]
    # The rest of the page is the build as it is, and the charset still comes first.
    assert r.text.startswith('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">') and '<article id="piece" class="mt-8">' in r.text
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
    # Nor can the structured data end its script early, and it still says the title as it is.
    assert json.loads(LD.findall(page)[0])["headline"] == 'Fed "cuts" <script>alert(1)</script>'
    said = tags(page)
    assert said["og:title"] == ['Fed "cuts" <script>alert(1)</script>'] and said["og:description"] == ["A & B > C"]
    assert said["og:image"][0].endswith("&v=v%221")


def test_an_article_that_is_not_there_is_a_404(site):
    for slug in ("no-such-article", "../etc/passwd", "", "x" * 300):
        r = site.get("/opinion/article/", params={"slug": slug} if slug else None)
        assert r.status_code == 404 and r.text == BUILT
    assert site.head("/opinion/article/", params={"slug": SLUG}).status_code == 200
    # Without the slash the static site sends it on to the page, query and all.
    moved = site.get("/opinion/article", params={"slug": SLUG}, follow_redirects=False)
    assert moved.status_code in (307, 308) and moved.headers["location"].endswith(f"/opinion/article/?slug={SLUG}")


def test_a_crawler_reads_each_article_once(site, opinion):
    reads, texts = [], []
    front, article = opinion.store.front, opinion.store.article
    opinion.store.front = lambda: reads.append(1) or front()
    opinion.store.article = lambda slug: texts.append(slug) or article(slug)
    for _ in range(20):
        site.get("/opinion/article/", params={"slug": SLUG})
        site.get("/opinion/article/", params={"slug": "no-such-article"})
        site.get("/opinion/")
    assert len(reads) == 1  # the list, once a minute
    assert texts == [SLUG, "no-such-article"]  # each slug once: a listed article's text, and whether an invented one is there


def test_an_article_older_than_the_list_still_has_its_page(site, opinion):
    old = {**ARTICLE, "slug": "an-old-one", "title": "An old one"}
    front = opinion.store.front
    opinion.store.articles[old["slug"]] = old
    opinion.store.front = lambda: [a for a in front() if a["slug"] != "an-old-one"]  # the list no longer holds it
    r = site.get("/opinion/article/", params={"slug": "an-old-one"})
    assert r.status_code == 200 and tags(r.text)["og:title"] == ["An old one"] and ">An old one</h1>" in r.text


def test_when_the_store_does_not_answer_an_unknown_slug_is_not_called_gone(site, opinion):
    def down(slug):
        raise RuntimeError("store down")
    opinion.store.article = down
    r = site.get("/opinion/article/", params={"slug": "maybe-there"})
    assert r.status_code == 503 and r.headers["retry-after"] == "300"


def test_the_home_page_carries_the_newest_articles(site, opinion):
    for i in range(4):
        opinion.store.articles[f"article-{i}"] = {**ARTICLE, "slug": f"article-{i}", "title": f"Article {i}",
                                                  "published_utc": f"2026-10-1{i}T08:00:00+00:00"}
    r = site.get("/")
    assert r.status_code == 200 and "public" in r.headers["cache-control"]
    page = r.text
    assert page.count('class="hover:underline"') == 3  # the three newest
    assert page.index(">Article 3</a>") < page.index(">Article 2</a>") < page.index(">Article 1</a>") and ">Article 0</a>" not in page
    assert '<a href="/opinion/" class="link">All the articles</a>' in page and page.endswith("<footer>Home footer</footer></body></html>")
    assert site.head("/").status_code == 200


def test_without_articles_the_home_page_is_as_built(site, opinion):
    opinion.store.articles.clear()
    assert site.get("/").text == BUILT_HOME


def test_an_article_page_carries_the_article_itself(site):
    page = site.get("/opinion/article/", params={"slug": SLUG}).text
    body = page[page.index("<body>"):]
    assert "skeleton" not in body and '<section id="comments" hidden>' in body
    assert ">A quiet jobs report</h1>" in body and "What 29,000 jobs say.</p>" in body
    assert "<p>First paragraph.</p>" in body and ">A heading</h2>" in body and "<p>Second paragraph.</p>" in body
    assert '<a href="https://www.bls.gov/" class="link" target="_blank" rel="noopener">BLS</a>' in body
    assert '<time datetime="2026-10-06T08:00:00+00:00">October 6, 2026</time>' in body


def test_the_text_of_an_article_is_escaped(site, opinion):
    opinion.store.articles[SLUG] = {**ARTICLE, "body": 'Text <b>bold</b>, [a link](javascript:alert(1)), [ours](/today/) and **"x"**'}
    page = site.get("/opinion/article/", params={"slug": SLUG}).text
    assert "<b>bold</b>" not in page and "&lt;b&gt;bold&lt;/b&gt;" in page and "javascript:" not in page
    assert '<a href="/today/" class="link">ours</a>' in page and "&quot;x&quot;</strong>" in page


def test_an_article_page_says_what_it_is_in_structured_data(site, opinion):
    opinion.store.articles[SLUG] = {**ARTICLE, "cover": {"alt": "A chart", "v": "abc"}, "author": "Ana"}
    data = [json.loads(b) for b in LD.findall(site.get("/opinion/article/", params={"slug": SLUG}).text)]
    assert len(data) == 1
    a = data[0]
    assert a["@type"] == "Article" and a["headline"] == "A quiet jobs report" and a["description"] == "What 29,000 jobs say."
    assert a["mainEntityOfPage"] == f"https://themarkethub.app/opinion/article/?slug={SLUG}"
    assert a["datePublished"] == "2026-10-06T08:00:00+00:00" and a["dateModified"] == a["datePublished"]
    assert a["image"] == [f"https://themarkethub.app/api/public/opinion/cover?slug={SLUG}&v=abc"]
    assert a["author"] == {"@type": "Person", "name": "Ana"} and a["publisher"]["name"] == "The Market Hub"


def test_without_the_text_the_page_still_goes_with_its_tags(site, opinion):
    def down(slug):
        raise RuntimeError("store down")
    opinion.store.article = down
    r = site.get("/opinion/article/", params={"slug": SLUG})
    assert r.status_code == 200 and tags(r.text)["og:title"] == ["A quiet jobs report"]
    assert '<div class="skeleton h-5 w-56">' in r.text  # the script fetches the text, as before


def test_the_list_page_carries_the_articles_as_links(site, opinion):
    opinion.store.articles["a-second-one"] = {**ARTICLE, "slug": "a-second-one", "title": "A second <one>",
                                              "published_utc": "2026-10-07T08:00:00+00:00", "cover": {"alt": "A picture", "v": "v1"}}
    r = site.get("/opinion/")
    assert r.status_code == 200 and "public" in r.headers["cache-control"]
    page = r.text
    assert "skeleton" not in page and page.endswith("<footer>Footer</footer></main></body></html>")
    # Newest first, each title a link to its page.
    first = page.index('href="/opinion/article/?slug=a-second-one" class="hover:underline">A second &lt;one&gt;</a>')
    second = page.index(f'href="/opinion/article/?slug={SLUG}" class="hover:underline">A quiet jobs report</a>')
    assert first < second
    assert 'src="/api/public/opinion/cover?slug=a-second-one&amp;v=v1" alt="A picture"' in page
    assert '<span class="chip !font-sans">Macro</span>' in page


def test_an_empty_list_leaves_the_page_as_built(site, opinion):
    opinion.store.articles.clear()
    assert site.get("/opinion/").text == BUILT_LIST
