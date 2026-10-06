"""The news desk: reading the sources, writing the items, and refreshing only when asked and stale.
Sources and the model are fakes: no test touches the network."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from conftest import CLIENT_ID, ORIGIN, fake_verifier, sign_in
from markethub import sample
from markethub.api import create_app
from markethub.market import Company, Directory
from markethub.news import FileNews, MemoryNews, NewsDesk, market_day, market_items
from markethub.newsfeeds import (Bea, Bls, Fed, Press, SecFilings, SourceDown, filing_documents, html_text, item,
                                 reads_as_advice, sec_entries)
from markethub.newswriter import NewsWriter
from markethub.users import MemoryUsers

NOW = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)  # a Tuesday, 11:00 in New York
SINCE = NOW - timedelta(hours=72)
APPLE, COKE = Company("AAPL", "Apple Inc.", 320193), Company("KO", "COCA COLA CO", 21344)


def directory():
    return Directory(loader=lambda: [APPLE, Company("GOOGL", "Alphabet Inc.", 1652044), Company("GOOG", "Alphabet Inc.", 1652044), COKE])


def filing(name, cik, accession, items, when="2026-10-06T09:00:00-04:00", form="8-K"):
    listed = "".join(f"\n&lt;br&gt;Item {code}: Something" for code in items)
    return (f'<entry><title>{form} - {name} ({cik:010d}) (Filer)</title>'
            f'<link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace("-", "")}/{accession}-index.htm"/>'
            f'<summary type="html"> &lt;b&gt;Filed:&lt;/b&gt; 2026-10-06 &lt;b&gt;AccNo:&lt;/b&gt; {accession} &lt;b&gt;Size:&lt;/b&gt; 2 MB{listed}</summary>'
            f'<updated>{when}</updated></entry>')


def atom(*entries):
    return ('<?xml version="1.0" encoding="ISO-8859-1" ?><feed xmlns="http://www.w3.org/2005/Atom">'
            f'<title>Latest Filings</title>{"".join(entries)}</feed>').encode("latin-1")


INDEX = """<table><tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
<tr><td>1</td><td>8-K</td><td><a href="/ix?doc=/Archives/edgar/data/320193/000032019326000070/aapl-8k.htm">aapl-8k.htm</a> iXBRL</td><td>8-K</td><td>52179</td></tr>
<tr><td>2</td><td>Press release</td><td><a href="/Archives/edgar/data/320193/000032019326000070/ex991.htm">ex991.htm</a></td><td>EX-99.1</td><td>90000</td></tr>
<tr><td>3</td><td>GRAPHIC</td><td><a href="/Archives/edgar/data/320193/000032019326000070/logo.jpg">logo.jpg</a></td><td>GRAPHIC</td><td>100</td></tr></table>"""
RELEASE = "<html><head><title>x</title><style>p{}</style></head><body><p>Apple reports fourth quarter results.</p>" + "<p>Revenue was $100 billion, up 6 percent.</p>" * 20 + "</body></html>"

FED = """<?xml version="1.0" encoding="utf-8" ?><rss version="2.0"><channel><title>FRB</title>
<item><title>Federal Reserve issues FOMC statement</title><link><![CDATA[https://www.federalreserve.gov/newsevents/pressreleases/monetary20261006a.htm]]></link>
<description><![CDATA[Federal Reserve issues FOMC statement]]></description><category>Monetary Policy</category><pubDate><![CDATA[Tue, 6 Oct 2026 14:00:00 GMT]]></pubDate></item>
<item><title>Federal Reserve Board announces approval of application by Some Bank</title><link>https://www.federalreserve.gov/newsevents/pressreleases/orders20261005a.htm</link>
<category>Orders on Banking Applications</category><pubDate>Mon, 5 Oct 2026 20:30:00 GMT</pubDate></item>
<item><title>Agencies issue a rule on capital</title><link>https://www.federalreserve.gov/newsevents/pressreleases/bcreg20261005b.htm</link>
<category>Banking and Consumer Regulatory Policy</category><pubDate>Mon, 5 Oct 2026 16:00:00 GMT</pubDate></item>
<item><title>Federal Reserve Board names a new vice chair</title><link>https://www.federalreserve.gov/newsevents/pressreleases/other20261005a.htm</link>
<category>Other Announcements</category><pubDate>Mon, 5 Oct 2026 15:00:00 GMT</pubDate></item></channel></rss>""".encode()
BLS = """<?xml version='1.0' encoding='UTF-8'?><feed xmlns="http://www.w3.org/2005/Atom"><title>Employment Situation</title>
<entry><title>Payroll employment (+29,000) changes little in September</title><link href="https://www.bls.gov/news.release/archives/empsit_10022026.htm"/>
<id>empsit-2026_10_02</id><content>Nonfarm payroll employment changed little in September. The unemployment rate was 4.2 percent. Employment in all major industries changed little.</content>
<published>2026-10-02T08:30:00.289-04:00</published><category>News Release</category></entry>
<entry><title>Payroll employment increases by 162,000 in August</title><link href="https://www.bls.gov/news.release/archives/empsit_09042026.htm"/>
<id>empsit-2026_09_04</id><content>Old.</content><published>2026-09-04T08:30:00-04:00</published></entry></feed>""".encode()
BEA = """<?xml version="1.0" encoding="us-ascii"?><rss version="2.0"><channel><title>BEA</title><pubDate>Wed, 30 Sep 2026 08:30:00 EDT</pubDate>
<item name="Personal Income and Outlays"><title>Personal Income and Outlays, August 2026</title><link>https://www.bea.gov/news/2026/personal-income-and-outlays-august-2026</link>
<description><![CDATA[<p>Personal income increased $66.6 billion (0.2 percent at a monthly rate) in August, said the U.S. Bureau of Economic Analysis. Disposable personal income increased $68.6 billion. Outlays increased too.</p>]]></description>
<pubDate>Mon, 05 Oct 2026 08:30:00 EDT</pubDate></item></channel></rss>""".encode()
PRESS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Finance</title>
<item><link>https://www.cnbc.com/2026/10/06/jobs.html</link><title>Labor market faltered in September as jobs increased by just 29,000</title>
<description><![CDATA[The publisher's own summary, which is not kept.]]></description><pubDate>Tue, 06 Oct 2026 12:00:00 GMT</pubDate></item>
<item><link>https://www.cnbc.com/2026/10/06/wells.html</link><title>Wells Fargo gets a bold upgrade ahead of earnings. Why the stock can play catch-up</title><pubDate>Tue, 06 Oct 2026 11:00:00 GMT</pubDate></item>
<item><link>https://www.cnbc.com/2026/10/06/buy.html</link><title>Three stocks to buy before the Fed meets, and one price target to watch</title><pubDate>Tue, 06 Oct 2026 10:00:00 GMT</pubDate></item>
<item><link>javascript:alert(1)</link><title>A headline whose link is not a web address at all</title><pubDate>Tue, 06 Oct 2026 10:00:00 GMT</pubDate></item>
<item><link>https://www.cnbc.com/2026/10/06/jobs-again.html</link><title>Labor market faltered in September as jobs increased by just 29,000</title><pubDate>Tue, 06 Oct 2026 09:00:00 GMT</pubDate></item></channel></rss>""".encode()


class FakeHttp:
    """Pages by address; an address that is not there is a source that does not answer."""

    def __init__(self, pages: dict):
        self.pages, self.asked = pages, []

    def get(self, url, **params):
        key = f"{url}?start={params['start']}" if "start" in params else url
        self.asked.append(key)
        if key not in self.pages:
            raise SourceDown(f"{key} did not answer")
        return self.pages[key]

    def text(self, url, **params):
        return self.get(url, **params).decode()


SEC_FEED = "https://www.sec.gov/cgi-bin/browse-edgar?start=0"
APPLE_INDEX = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000070/0000320193-26-000070-index.htm"
COKE_INDEX = "https://www.sec.gov/Archives/edgar/data/21344/000002134426000011/0000021344-26-000011-index.htm"
COKE_FORM = "https://www.sec.gov/Archives/edgar/data/21344/000002134426000011/ko-8k.htm"
FOMC = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261006a.htm"


def sec_pages():
    return {
        SEC_FEED: atom(
            filing("Apple Inc.", 320193, "0000320193-26-000070", ["2.02", "9.01"]),
            filing("COCA COLA CO", 21344, "0000021344-26-000011", ["5.02"], when="2026-10-05T16:30:00-04:00"),
            filing("COCA COLA CO", 21344, "0000021344-26-000012", ["5.03", "9.01"]),  # bylaws: not followed
            filing("Alphabet Inc.", 1652044, "0001652044-26-000050", ["8.01"], form="8-K/A"),  # an amendment
            filing("Tiny Co", 999, "0000000999-26-000001", ["1.01"]),  # not among the largest
        ),
        APPLE_INDEX: INDEX.encode(),
        "https://www.sec.gov/Archives/edgar/data/320193/000032019326000070/ex991.htm": RELEASE.encode(),
        # A filing with no press release: the form itself is what there is to read.
        COKE_INDEX: f'<table><tr><td>1</td><td>8-K</td><td><a href="/ix?doc={COKE_FORM[len("https://www.sec.gov"):]}">ko-8k.htm</a></td><td>8-K</td><td>9</td></tr></table>'.encode(),
        COKE_FORM: ("<p>The Coca-Cola Company announced that its chief financial officer will retire.</p>" * 8).encode(),
        FOMC: b"<p>The Committee decided to maintain the target range for the federal funds rate.</p>",
    }


# --- Sources -----------------------------------------------------------------------------------


def test_sec_filings_of_the_largest_companies_titled_by_code():
    http = FakeHttp(sec_pages())
    found = SecFilings(http, directory())(SINCE)
    assert [(i["id"], i["title"], i["category"], i["tickers"]) for i in found] == [
        ("sec-0000320193-26-000070", "Apple Inc. published results", "Earnings", ["AAPL"]),
        ("sec-0000021344-26-000011", "Coca Cola Co reported a change among its directors or officers", "Companies", ["KO"]),
    ]
    apple = found[0]
    assert apple["url"] == APPLE_INDEX and apple["published_utc"] == "2026-10-06T13:00:00+00:00"
    assert apple["summary"] == "Form 8-K filed with the SEC (items 2.02 and 9.01)." and apple["written_by"] == "code"
    # The document behind it is the press release, not the cover form; nothing is fetched until asked.
    assert http.asked == [SEC_FEED]
    assert apple["_read"]().startswith("Apple reports fourth quarter results.")


def test_sec_feed_is_read_back_to_the_last_refresh_and_no_further():
    old = [filing("Apple Inc.", 320193, f"0000320193-26-{n:06d}", ["8.01"], when="2026-10-06T08:00:00-04:00") for n in range(100)]
    older = [filing("Apple Inc.", 320193, f"0000320193-26-{n:06d}", ["8.01"], when="2026-10-01T08:00:00-04:00") for n in range(100, 200)]
    http = FakeHttp({SEC_FEED: atom(*old), SEC_FEED.replace("start=0", "start=100"): atom(*older)})
    found = SecFilings(http, directory())(NOW - timedelta(hours=6))
    assert len(found) == 100 and len(http.asked) == 2  # the second page reaches past `since`: no third


def test_filing_parsers_ignore_what_they_cannot_read():
    assert sec_entries(atom("<entry><title>10-Q - X (0000000001) (Filer)</title></entry>")) == []
    with pytest.raises(SourceDown):
        sec_entries(b"<html>Request rate threshold exceeded</html><p>")
    docs = filing_documents(INDEX)
    assert [kind for kind, _ in docs] == ["8-K", "EX-99.1"]  # the picture is not a document to read
    assert docs[0][1] == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000070/aapl-8k.htm"
    assert html_text("<ix:header><p>machine data</p></ix:header><p>Hello&nbsp;<b>world</b></p><script>x()</script>") == "Hello world"


def test_agencies():
    http = FakeHttp({"fed": FED, "bls": BLS, "bea": BEA, FOMC: b"<p>The Committee decided.</p>"})
    fed = Fed(http, "fed")(SINCE)
    assert [i["title"] for i in fed] == ["Federal Reserve issues FOMC statement", "Federal Reserve Board names a new vice chair"]
    assert fed[0]["_read"]() == "The Committee decided." and "_read" not in fed[1]
    bls = Bls(http, ["bls", "missing"])(SINCE)  # one feed down does not lose the other
    assert bls[0]["source"] == "Bureau of Labor Statistics" and bls[0]["published_utc"] == "2026-10-02T12:30:00+00:00"
    assert bls[0]["summary"] == "Nonfarm payroll employment changed little in September. The unemployment rate was 4.2 percent."
    with pytest.raises(SourceDown):
        Bls(http, ["missing"])(SINCE)
    bea = Bea(http, "bea")(SINCE)
    assert bea[0]["published_utc"] == "2026-10-05T12:30:00+00:00"  # EDT
    assert bea[0]["summary"].endswith("Bureau of Economic Analysis. Disposable personal income increased $68.6 billion.")  # two sentences


def test_press_keeps_the_headline_and_the_link_and_drops_advice():
    found = Press(FakeHttp({"feed": PRESS}), [("CNBC", "feed")])(SINCE)
    assert [i["title"] for i in found] == ["Labor market faltered in September as jobs increased by just 29,000"]
    assert found[0] | {"id": ""} == item("", "press", "Press", found[0]["title"], "CNBC", "https://www.cnbc.com/2026/10/06/jobs.html",
                                         datetime(2026, 10, 6, 12, tzinfo=timezone.utc))
    assert found[0]["summary"] == ""  # the publisher's text is never kept
    assert reads_as_advice("Analysts lift their price target") and reads_as_advice("Bank gets an upgrade", press=True)
    assert not reads_as_advice("Company agrees to sell its unit and buy back shares")


# --- The day's market, in words ----------------------------------------------------------------


def overview(**over):
    snap = lambda s, pct, price=100.0, name=None: {"symbol": s, "name": name or s, "price": price, "change_pct": pct}  # noqa: E731
    return {"sample": False, "sample_sections": [], "as_of": "2026-10-06T15:00:00+00:00",
            "indices": [snap("SPX", 0.0087, 5712.4), snap("NDX", 0.012), snap("DJI", -0.001), snap("RUT", 0.0002), snap("VIX", -0.03, 16.2)],
            "sectors": [{"name": "Energy", "change_pct": 0.021}, {"name": "Utilities", "change_pct": -0.013}, {"name": "Technology", "change_pct": 0.004}],
            "movers": {"gainers": [snap("AAA", 0.123, name="Aaa Inc."), snap("BBB", 0.09)], "losers": [snap("ZZZ", -0.098, name="Zzz Corp.")], "active": []}} | over


def test_market_items_are_written_from_the_figures():
    items = market_items(overview())
    assert [i["id"] for i in items] == ["mkt-2026-10-06-indices", "mkt-2026-10-06-sectors", "mkt-2026-10-06-movers"]
    indices, sectors, movers = items
    assert indices["title"] == "S&P 500 up 0.87% at 5,712.40"
    assert indices["summary"] == "The Nasdaq 100 is up 1.20%, the Dow is down 0.10% and the Russell 2000 is little changed. The VIX is at 16.20."
    assert sectors["title"] == "Energy leads the US sectors, up 2.10%; Utilities is last, down 1.30%"
    assert sectors["summary"].startswith("2 of 3 sectors are higher")
    assert movers["title"] == "Largest moves among US stocks: AAA +12.30%, ZZZ −9.80%" and movers["tickers"] == ["AAA", "BBB", "ZZZ"]
    assert all(i["layer"] == "market" and i["written_by"] == "code" for i in items)


def test_sample_figures_are_never_written_up_as_news():
    assert market_items(sample.overview() | {"sample_sections": []}) == []
    assert [i["id"] for i in market_items(overview(sample_sections=["sectors", "movers"]))] == ["mkt-2026-10-06-indices"]


def test_market_day():
    utc = lambda *a: datetime(*a, tzinfo=timezone.utc)  # noqa: E731
    assert market_day(utc(2026, 10, 6, 15)) == date(2026, 10, 6)
    assert market_day(utc(2026, 10, 6, 12)) == date(2026, 10, 5)  # 8:00 in New York: still Monday's figures
    assert market_day(utc(2026, 10, 4, 18)) == date(2026, 10, 2)  # Sunday -> Friday
    assert market_day(utc(2026, 10, 5, 12)) == date(2026, 10, 2)  # Monday before the open -> Friday
    assert market_day(utc(2026, 12, 1, 14, 0)) == date(2026, 11, 30)  # winter time: 9:00 in New York


# --- The desk ----------------------------------------------------------------------------------


class Clock:
    def __init__(self):
        self.at = NOW

    def __call__(self):
        return self.at


class FakeWriter:
    def __init__(self, answers=None):
        self.answers, self.read = answers or {}, []

    def write(self, draft, document):
        self.read.append(draft["id"])
        return self.answers.get(draft["id"], {"newsworthy": True, "title": f"Written: {draft['title']}", "summary": document[:20]})


class FakeMarkets:
    def overview(self, detail=False):
        return overview()


def desk(writer=None, sources=None, markets=None, **kw):
    http = FakeHttp(sec_pages() | {"fed": FED, "feed": PRESS})
    sources = sources or [SecFilings(http, directory()), Fed(http, "fed"), Press(http, [("CNBC", "feed")])]
    clock = Clock()
    return NewsDesk(MemoryNews(), sources, writer=writer, markets=markets, now=clock, **kw), clock, http


def test_a_visit_is_told_the_news_is_stale_and_a_refresh_fills_it():
    d, clock, _ = desk(markets=FakeMarkets())
    first = d.news()
    assert first["items"] == [] and first["stale"] is True and first["sample"] is False
    assert d.refresh() == {"refreshed": True}
    got = d.news(limit=50)
    assert got["stale"] is False and got["refreshed_utc"] == "2026-10-06T15:00:00+00:00"
    assert [i["id"][:3] for i in got["items"]] == ["mkt", "mkt", "mkt", "fed", "sec", "sec", "fed"]  # newest first; no bank orders or rules
    assert [i["source"] for i in got["press"]] == ["CNBC"]
    assert all("_read" not in i for i in got["items"])  # without a model the code's titles stand
    assert d.store.items.keys() >= {"sec-0000320193-26-000070", "mkt-2026-10-06-indices"}  # the archive


def test_filters():
    d, _, _ = desk(markets=FakeMarkets())
    d.refresh()
    assert {i["category"] for i in d.news(category="Earnings")["items"]} == {"Earnings"}
    assert [i["id"] for i in d.news(tickers={"KO", "MSFT"})["items"]] == ["sec-0000021344-26-000011"]
    assert d.news(tickers={"KO"})["press"] == [] and d.news(category="bogus", limit=2)["items"].__len__() == 2


def test_nothing_is_read_while_the_news_is_fresh_and_nothing_twice():
    writer = FakeWriter()
    d, clock, http = desk(writer=writer)
    d.refresh()
    asked = len(http.asked)
    assert d.refresh() == {"refreshed": False, "reason": "fresh"} and len(http.asked) == asked
    clock.at += timedelta(minutes=16)
    assert d.news()["stale"] is True and d.refresh() == {"refreshed": True}
    assert len(writer.read) == len(set(writer.read)) == 3  # the two filings and the FOMC statement, once each
    assert len(d.news(limit=50)["items"]) == 4


def test_the_model_writes_the_item_and_a_filing_that_is_not_news_is_remembered():
    writer = FakeWriter({"sec-0000021344-26-000011": {"newsworthy": False, "title": "", "summary": ""}})
    d, clock, _ = desk(writer=writer)
    d.refresh()
    items = {i["id"]: i for i in d.news(limit=50)["items"]}
    apple = items["sec-0000320193-26-000070"]
    assert apple["title"] == "Written: Apple Inc. published results" and apple["written_by"] == "model"
    assert apple["summary"] == "Apple reports fourth"
    assert "sec-0000021344-26-000011" not in items and d.store.front()["seen"] == ["sec-0000021344-26-000011"]
    clock.at += timedelta(hours=1)
    d.refresh()
    assert writer.read.count("sec-0000021344-26-000011") == 1


def test_a_writer_that_fails_leaves_the_codes_title():
    class Broken:
        def write(self, draft, document):
            return None
    d, _, _ = desk(writer=Broken())
    d.refresh()
    apple = next(i for i in d.news(limit=50)["items"] if i["id"] == "sec-0000320193-26-000070")
    assert apple["title"] == "Apple Inc. published results" and apple["written_by"] == "code"


def test_documents_left_when_the_time_runs_out_are_read_next_time():
    writer = FakeWriter()
    d, clock, _ = desk(writer=writer, budget=-1)  # no time at all
    d.refresh()
    front = d.store.front()
    assert writer.read == [] and [i["title"] for i in front["items"]] == ["Federal Reserve Board names a new vice chair"]  # it has no document to read
    assert front["since_utc"] == "2026-10-05T20:30:00+00:00"  # the oldest filing left unread
    d.budget = 30
    clock.at += timedelta(minutes=16)
    d.refresh()
    assert len(writer.read) == 3 and len(d.news(limit=50)["items"]) == 4


def test_a_source_that_is_down_does_not_cost_the_others():
    def down(since):
        raise SourceDown("nobody home")

    def broken(since):
        raise ValueError("surprise")
    http = FakeHttp({"feed": PRESS})
    d, _, _ = desk(sources=[down, broken, Press(http, [("CNBC", "feed")])])
    assert d.refresh() == {"refreshed": True} and len(d.news()["press"]) == 1


def test_a_refresh_running_elsewhere_is_left_alone():
    d, clock, http = desk()
    d.store.save_front({"started_utc": (NOW - timedelta(seconds=60)).isoformat()})
    assert d.refresh() == {"refreshed": False, "reason": "running"} and http.asked == []
    clock.at += timedelta(minutes=5)  # that one died: the next visit takes over
    assert d.refresh() == {"refreshed": True}


def test_file_store(tmp_path):
    store = FileNews(tmp_path)
    assert store.front() is None
    store.save_front({"items": [], "refreshed_utc": "x"})
    store.archive([{"id": "sec-1", "title": "A — B"}, {"id": "../escape", "title": "no"}])
    assert store.front()["refreshed_utc"] == "x"
    assert [p.name for p in (tmp_path / "items").iterdir()] == ["sec-1.json"]


# --- The writer --------------------------------------------------------------------------------


def answer(text, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop,
                           usage=SimpleNamespace(input_tokens=4000, output_tokens=120))


class FakeClaude:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []
        self.messages = SimpleNamespace(create=self.create)

    def create(self, **kw):
        self.calls.append(kw)
        out = self.answers.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


DRAFT = {"id": "sec-1", "title": "Apple Inc. published results", "source": "SEC filing", "published_utc": "2026-10-06T13:00:00+00:00"}


def test_writer_asks_for_json_and_reads_only_the_opening_of_the_document():
    claude = FakeClaude(answer('{"newsworthy": true, "title": "Apple reports  revenue of $100B", "summary": "Up 6%."}'))
    out = NewsWriter(client=claude).write(DRAFT, "x" * 50_000)
    assert out == {"newsworthy": True, "title": "Apple reports revenue of $100B", "summary": "Up 6%."}
    call = claude.calls[0]
    assert call["model"] == "claude-haiku-4-5" and call["output_config"]["format"]["type"] == "json_schema"
    assert "never advise" in call["system"] and len(call["messages"][0]["content"]) < 17_000


def test_writer_answers_that_cannot_be_shown():
    advice = answer('{"newsworthy": true, "title": "Apple looks undervalued after results", "summary": "x"}')
    cut = answer('{"newsworthy": true, "title": "App', stop="max_tokens")
    writer = NewsWriter(client=FakeClaude(advice, cut))
    assert writer.write(DRAFT, "doc") is None and writer.write(DRAFT, "doc") is None


def test_writer_stops_asking_when_the_account_is_refused():
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    refused = anthropic.AuthenticationError("no", response=response, body=None)
    claude = FakeClaude(refused, answer("{}"))
    writer = NewsWriter(client=claude)
    assert writer.write(DRAFT, "doc") is None and writer.write(DRAFT, "doc") is None
    assert len(claude.calls) == 1


# --- The API -----------------------------------------------------------------------------------


@pytest.fixture
def live_client(users, market):
    d, clock, _ = desk(markets=FakeMarkets())
    app = create_app(users=users, market=market, directory=directory(), verifier=fake_verifier, client_id=CLIENT_ID,
                     session_secret="test-secret", secure_cookies=False, news=d)
    c = TestClient(app)
    c.headers.update({"origin": ORIGIN})
    return c


def test_news_api_refreshes_on_request(live_client):
    c = live_client
    assert c.get("/api/public/news").json() | {"categories": 0} == {"sample": False, "categories": 0, "items": [], "press": [],
                                                                    "refreshed_utc": None, "stale": True}
    assert c.post("/api/public/news/refresh", headers={"origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/public/news/refresh").json() == {"refreshed": True}
    assert c.post("/api/public/news/refresh").json() == {"refreshed": False, "reason": "fresh"}
    got = c.get("/api/public/news", params={"limit": 100}).json()
    assert len(got["items"]) == 7 and got["press"] and got["stale"] is False
    assert [i["id"] for i in c.get("/api/public/news", params={"ticker": "AAPL"}).json()["items"]] == ["sec-0000320193-26-000070"]
    assert [i["id"] for i in c.get("/api/public/quote", params={"t": "AAPL"}).json()["news"]] == ["sec-0000320193-26-000070"]


def test_my_news_is_about_the_users_own_stocks(live_client):
    c = live_client
    assert c.get("/api/news/mine").status_code == 401
    c.post("/api/public/news/refresh")
    sign_in(c)
    assert c.get("/api/news/mine").json()["items"] == []  # nothing saved yet: not everybody's news
    c.put("/api/portfolio", json={"positions": [{"ticker": "KO", "shares": 1, "avg_cost": 50}], "watchlist": ["AAPL"]})
    assert {i["tickers"][0] for i in c.get("/api/news/mine").json()["items"]} == {"KO", "AAPL"}


def test_sample_news_stays_labelled_and_off_the_quote(client):
    assert client.get("/api/public/news").json()["sample"] is True
    assert client.post("/api/public/news/refresh").json() == {"refreshed": False, "reason": "sample"}
    assert client.get("/api/public/quote?t=AAPL").json()["news"] == []
