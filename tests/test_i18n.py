"""The service in Spanish: a page under /es/ says "X-MH-Lang: es", and only then do the service's
own words come back in Spanish (i18n.py). The phone app, and anything that carries its token,
keeps getting English. The opinion pages and the sitemap are there in both languages."""

import html
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import ARTICLE, CLIENT_ID, fake_verifier, sign_in
from fastapi.testclient import TestClient

from markethub import i18n, previews
from markethub.api import create_app
from markethub.config import SITE_URL
from markethub.instagram import Posts
from markethub.xposts import XPosts
from test_accounts import EMAIL, PASSWORD, register
from test_bots import TREND, competition
from test_previews import BUILT, BUILT_HOME, BUILT_LIST, LD, SLUG, tags

ES = {"x-mh-lang": "es"}
SRC = Path(__file__).resolve().parents[1] / "src" / "markethub"


def asking(path="/api/me", **headers):
    return SimpleNamespace(url=SimpleNamespace(path=path), headers={k.lower(): v for k, v in headers.items()})


# --- Who gets Spanish -------------------------------------------------------------------------------


def test_spanish_only_when_the_page_says_so():
    assert i18n.lang_of(asking(**{"X-MH-Lang": "es"})) == "es"
    assert i18n.lang_of(asking(**{"X-MH-Lang": " ES "})) == "es"
    assert i18n.lang_of(asking()) == "en"
    assert i18n.lang_of(asking(**{"X-MH-Lang": "en"})) == "en"
    assert i18n.lang_of(asking(**{"X-MH-Lang": "fr"})) == "en"
    # Never from what the browser or the phone says by itself.
    assert i18n.lang_of(asking(**{"Accept-Language": "es-ES,es;q=0.9"})) == "en"


def test_the_phone_app_always_gets_english():
    assert i18n.lang_of(asking("/api/app/auth/password", **{"X-MH-Lang": "es"})) == "en"
    assert i18n.lang_of(asking("/api/portfolio", **{"X-MH-Lang": "es", "Authorization": "Bearer abc"})) == "en"


def test_a_refusal_is_said_in_the_pages_language(client):
    assert client.get("/api/me", headers=ES).json() == {"detail": "Entra primero."}
    assert client.get("/api/me").json() == {"detail": "Sign in first."}
    assert client.get("/api/me", headers={"accept-language": "es-ES"}).json() == {"detail": "Sign in first."}
    # The same status either way.
    assert client.get("/api/me", headers=ES).status_code == client.get("/api/me").status_code == 401


def test_what_a_module_refuses_is_said_in_spanish_with_its_figures(client):
    sign_in(client)
    many = {"positions": [], "watchlist": ["AAPL"] * 500}
    en = client.put("/api/portfolio", json=many)
    es = client.put("/api/portfolio", json=many, headers=ES)
    assert en.status_code == es.status_code == 400
    assert en.json()["detail"].startswith("Up to ") and es.json()["detail"].startswith("Hasta ")
    bad = client.put("/api/portfolio", json={"positions": [], "watchlist": ["not a ticker!"]}, headers=ES)
    assert bad.json()["detail"].startswith("No es un ticker: ")
    named = client.put("/api/sharing", json={"enabled": True, "handle": "x"}, headers=ES)
    assert named.status_code == 400 and named.json()["detail"].startswith("Elige un nombre de 3 a 20")
    entry = client.put("/api/competitions/entry", json={"handle": "Ana", "picks": []}, headers=ES)
    assert entry.status_code == 400 and re.fullmatch(r"Elige de \d+ a \d+ acciones\.", entry.json()["detail"])


def test_a_token_keeps_english_even_when_asked_for_spanish(client):
    assert register(client).status_code == 200
    phone = TestClient(client.app)
    token = phone.post("/api/app/auth/password", json={"email": EMAIL, "password": PASSWORD}).json()["token"]
    wrong = phone.post("/api/app/auth/password", json={"email": EMAIL, "password": "not it at all"}, headers=ES)
    assert wrong.json()["detail"] == "That email and password do not match an account."
    r = phone.put("/api/portfolio", json={"positions": [], "watchlist": ["not a ticker!"]},
                  headers={"authorization": f"Bearer {token}", **ES})
    assert r.status_code == 400 and r.json()["detail"].startswith("Not a ticker: ")
    # The site's own sign-in, asked from a Spanish page, answers in Spanish.
    site = client.post("/api/auth/password", json={"email": EMAIL, "password": "not it at all"}, headers=ES)
    assert site.json()["detail"] == "Ese email y esa contraseña no corresponden a ninguna cuenta."


def test_sentences_with_figures():
    say = lambda en: i18n.message(en, "es")  # noqa: E731
    assert say("The text needs 450 to 1,500 words; it has 12,345.") == "El texto necesita de 450 a 1500 palabras; tiene 12.345."
    assert say("NVDA is in the portfolio twice.") == "NVDA está dos veces en la cartera."
    assert say("Each stock takes between 5% and 40% of the portfolio.") == "Cada acción ocupa entre el 5 % y el 40 % de la cartera."
    assert say('An article argues; it does not tell readers what to do with their money ("buy now").') == \
        "Un artículo argumenta; no le dice al lector qué hacer con su dinero («buy now»)."
    # What has no Spanish, or is not a sentence, stays as it is; English is never touched.
    assert say("Something new.") == "Something new."
    assert say([{"loc": ["body"], "msg": "x"}]) == [{"loc": ["body"], "msg": "x"}]
    assert i18n.message("Sign in first.", "en") == "Sign in first."


def test_every_english_sentence_is_one_the_service_says():
    """A sentence changed in English and not here would quietly stay English on the Spanish pages."""
    code = "".join(p.read_text(encoding="utf-8") for p in SRC.glob("*.py") if p.name != "i18n.py").replace('\\"', '"')
    for en in i18n.MESSAGES:
        assert en in code, en
    for en, _ in i18n._SAID_WITH_VALUES:
        if en.endswith("characters; it has {n3}."):  # submissions._sized: what is measured, then the measure
            assert f'"{en.split(" needs ")[0]}"' in code and " characters; it has " in code, en
            continue
        longest = max(re.split(r"\{\w+\}", en), key=len)
        assert longest in code, en


# --- The names the service gives figures ------------------------------------------------------------


def test_my_hub_names_its_periods_groups_and_sectors_in_spanish(client):
    sign_in(client)
    client.put("/api/portfolio", json={"positions": [{"ticker": "AAPL", "shares": 2, "avg_cost": 100},
                                                      {"ticker": "KO", "shares": 5, "avg_cost": 50}], "watchlist": []})
    en, es = client.get("/api/dashboard").json(), client.get("/api/dashboard", headers=ES).json()
    assert [p["label"] for p in es["performance"]["periods"]] == ["Hoy", "1 mes", "3 meses", "Este año", "1 año"]
    assert [p["label"] for p in en["performance"]["periods"]] == ["Today", "1 month", "3 months", "This year", "1 year"]
    assert [g["label"] for g in es["groups"]] == ["Sector", "País", "Volatilidad", "Tamaño"]
    assert {p["ticker"]: p["sector"] for p in es["positions"]} == {"AAPL": "Tecnología", "KO": "Consumo defensivo"}
    assert {p["ticker"]: p["sector"] for p in en["positions"]} == {"AAPL": "Technology", "KO": "Consumer Defensive"}
    assert {i["label"] for i in es["groups"][0]["items"]} == {"Tecnología", "Consumo defensivo"}
    # Only words change: the figures are the same.
    assert es["totals"] == en["totals"] and [p["value"] for p in es["positions"]] == [p["value"] for p in en["positions"]]
    community = client.get("/api/community", headers=ES).json()
    assert [p["label"] for p in community["periods"]] == ["Hoy", "1 mes", "3 meses", "Este año", "1 año"]


def test_the_competitions_months_are_named_in_spanish(client):
    sign_in(client)
    en, es = client.get("/api/competitions").json(), client.get("/api/competitions", headers=ES).json()
    assert re.fullmatch(r"[a-z]+ de \d{4}", es["running"]["label"]) and re.fullmatch(r"[A-Z][a-z]+ \d{4}", en["running"]["label"])
    assert es["open"]["label"] == i18n.month(en["open"]["month"])
    assert i18n.month("2026-11") == "noviembre de 2026"


def test_the_bot_board_and_a_members_rules_in_spanish(client):
    sign_in(client)
    es = client.get("/api/bots", headers=ES).json()
    assert [p["label"] for p in es["periods"]] == ["Día", "Semana", "Mes", "Año"]
    bots, *_ = competition(380, hour=11)
    bots.submit("u1", TREND, name="Ana Torres")
    assert bots.overview("u1", "es")["you"]["rules"][0].startswith("Mira las 20 mayores empresas de EE. UU.")
    assert bots.overview("u1")["you"]["rules"][0].startswith("Looks at the 20 largest US companies")


def test_a_funds_sectors_and_mix_in_spanish():
    more = {"symbol": "SPY", "fund": {"sectors": [{"name": "Technology", "weight": 0.3}, {"name": "Odd One", "weight": 0.1}],
                                       "asset_mix": [{"name": "Stocks", "weight": 0.99}]}}
    said = i18n.quote_more(more, "es")
    assert [s["name"] for s in said["fund"]["sectors"]] == ["Tecnología", "Odd One"] and said["fund"]["asset_mix"][0]["name"] == "Acciones"
    assert more["fund"]["sectors"][0]["name"] == "Technology"  # what was built is not changed
    assert i18n.quote_more(more, "en") is more


def test_every_country_has_its_spanish_name():
    from markethub.holdings import COUNTRY_NAMES

    assert set(COUNTRY_NAMES.values()) <= set(i18n.COUNTRIES)


# --- The opinion pages in Spanish ------------------------------------------------------------------


def spanish(page: str) -> str:
    """A page of the build as its Spanish twin is built: the same, under /es/ and in Spanish."""
    return (page.replace('<html lang="en">', '<html lang="es">')
            .replace("https://themarkethub.app/opinion/article/", "https://themarkethub.app/es/opinion/article/")
            .replace('<link rel="canonical"', '<link rel="alternate" hreflang="en" href="https://themarkethub.app/opinion/article/">'
                     '<link rel="alternate" hreflang="es" href="https://themarkethub.app/es/opinion/article/"><link rel="canonical"', 1))


@pytest.fixture
def both(tmp_path, users, market, directory, opinion, shared, writer, logins, captcha, entries, reader, submissions, posts, x_posts):
    for root, change in ((tmp_path, lambda p: p), (tmp_path / "es", spanish)):
        (root / "opinion" / "article").mkdir(parents=True)
        (root / "opinion" / "article" / "index.html").write_text(change(BUILT), encoding="utf-8")
        (root / "opinion" / "index.html").write_text(change(BUILT_LIST), encoding="utf-8")
        (root / "index.html").write_text(change(BUILT_HOME), encoding="utf-8")
    for page in ("today", "markets"):
        (tmp_path / "es" / page).mkdir()
        (tmp_path / "es" / page / "index.html").write_text("<html lang=\"es\"></html>", encoding="utf-8")
    app = create_app(users=users, market=market, directory=directory, verifier=fake_verifier, client_id=CLIENT_ID,
                     session_secret="test-secret", secure_cookies=False, opinion=opinion, community_store=shared,
                     insight_writer=writer, logins=logins, password_cost=(10, 8, 1), captcha=captcha, competition_store=entries,
                     stock_reader=reader, submissions=submissions, posts=Posts(posts), x_posts=XPosts(x_posts), static_dir=str(tmp_path))
    return TestClient(app)


def alternates(page: str) -> dict[str, str]:
    return {code: html.unescape(url) for code, url in re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]*)"', page)}


def test_an_articles_spanish_page_names_both_its_addresses(both):
    r = both.get("/es/opinion/article/", params={"slug": SLUG})
    assert r.status_code == 200 and r.text.startswith('<!DOCTYPE html><html lang="es">')
    said = tags(r.text)
    es, en = f"https://themarkethub.app/es/opinion/article/?slug={SLUG}", f"https://themarkethub.app/opinion/article/?slug={SLUG}"
    assert said["canonical"] == [es] and said["og:url"] == [es] and said["og:locale"] == ["es_ES"]
    # The build's own alternates (without the slug) are replaced by the article's.
    assert alternates(r.text) == {"en": en, "es": es, "x-default": en} and r.text.count('hreflang="en"') == 1
    # The article stays in its own language; the words around it are Spanish.
    assert said["og:title"] == ["A quiet jobs report"]
    body = r.text
    assert "Análisis" in body and "4 min de lectura" in body and "6 de octubre de 2026" in body and ">Fuentes<" in body
    assert "min read" not in body and "October" not in body
    english = both.get("/opinion/article/", params={"slug": SLUG}).text
    assert alternates(english) == {"en": en, "es": es, "x-default": en} and tags(english)["og:locale"] == ["en_US"]
    assert "October 6, 2026" in english and "4 min read" in english
    # The structured data still says what the article is written in.
    assert '"inLanguage": "en"' in LD.search(body).group(1)


def test_an_unknown_slug_is_a_404_in_spanish_too(both):
    assert both.get("/es/opinion/article/", params={"slug": "no-such-thing"}).status_code == 404


def test_the_spanish_list_and_home_lead_to_spanish_pages(both, opinion):
    opinion.store.articles[SLUG] = {**ARTICLE, "tickers": ["NVDA"], "author": "Ana Torres",
                                    "body": "See [the quote](/quote/?t=NVDA) and [a file](/api/public/opinion/cover?slug=x)."}
    opinion._cached = None
    listed = both.get("/es/opinion/").text
    assert f'href="/es/opinion/article/?slug={SLUG}"' in listed and "Por Ana Torres" in listed and "Análisis" in listed
    assert 'href="/opinion/article/' not in listed
    home = both.get("/es/").text
    assert "Lo último de Opinión" in home and 'href="/es/opinion/"' in home and "Todos los artículos" in home
    assert "The latest from Opinion" in both.get("/").text
    page = both.get("/es/opinion/article/", params={"slug": SLUG}).text
    assert 'href="/es/quote/?t=NVDA"' in page  # its links stay in Spanish, but not the API's
    assert 'href="/api/public/opinion/cover?slug=x"' in page


# --- The sitemap -----------------------------------------------------------------------------------


def test_the_sitemap_lists_each_page_in_both_languages(client):
    r = client.get("/sitemap.xml").text
    assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in r
    for page in ("/", "/today/", "/opinion/"):
        en, es = f"{SITE_URL}{page}", f"{SITE_URL}/es{page}"
        links = (f'<xhtml:link rel="alternate" hreflang="en" href="{en}"/><xhtml:link rel="alternate" hreflang="es" href="{es}"/>'
                 f'<xhtml:link rel="alternate" hreflang="x-default" href="{en}"/>')
        assert f"<url><loc>{en}</loc>{links}</url>" in r and f"<url><loc>{es}</loc>{links}</url>" in r
    slug = ARTICLE["slug"]
    assert f"<loc>{SITE_URL}/es/opinion/article/?slug={slug}</loc><lastmod>2026-10-06</lastmod><xhtml:link" in r
    # Nothing that is noindex comes in by the Spanish door either.
    for page in ("/quote/", "/news/article/", "/dashboard/", "/signin/"):
        assert f"{SITE_URL}/es{page}<" not in r and f"{SITE_URL}/es{page}?" not in r and f'{SITE_URL}/es{page}"' not in r


def test_the_sitemap_names_only_the_spanish_pages_that_were_built(both):
    r = both.get("/sitemap.xml").text
    for page in ("/", "/today/", "/markets/", "/opinion/"):
        assert f"<loc>{SITE_URL}/es{page}</loc>" in r
    assert f"<loc>{SITE_URL}/es/news/</loc>" not in r and f"<url><loc>{SITE_URL}/news/</loc></url>" in r
    assert f"<loc>{SITE_URL}/es/opinion/article/?slug={ARTICLE['slug']}</loc>" in r
