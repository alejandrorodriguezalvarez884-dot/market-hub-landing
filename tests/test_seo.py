"""What search engines are told: robots.txt lets everything be crawled, and the sitemap lists the
portal's own pages and the opinion articles, never other sources' news and figures."""

from conftest import ARTICLE

from markethub.config import SITE_URL


def test_robots_lets_everything_be_crawled_and_names_the_sitemap(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert "Allow: /" in r.text and "Disallow" not in r.text
    assert f"Sitemap: {SITE_URL}/sitemap.xml" in r.text


def test_the_sitemap_lists_the_landing_the_sections_and_each_article(client):
    r = client.get("/sitemap.xml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    for page in ("/", "/today/", "/markets/", "/news/", "/opinion/", "/media/"):
        assert f"<loc>{SITE_URL}{page}</loc>" in r.text
    assert f"<loc>{SITE_URL}/opinion/article/?slug={ARTICLE['slug']}</loc><lastmod>2026-10-06</lastmod>" in r.text
    # Other sources' news and figures are not offered, nor My Hub.
    for page in ("/quote/", "/news/article/", "/dashboard/", "/signin/"):
        assert f"{SITE_URL}{page}<" not in r.text and f"{SITE_URL}{page}?" not in r.text


def test_an_article_without_a_date_is_listed_without_one(client, opinion):
    opinion.store.articles["fees-and-more"] = ARTICLE | {"slug": "fees-and-more", "published_utc": "not a date"}
    opinion._cached = None
    r = client.get("/sitemap.xml").text
    assert f"<loc>{SITE_URL}/opinion/article/?slug=fees-and-more</loc></url>" in r
