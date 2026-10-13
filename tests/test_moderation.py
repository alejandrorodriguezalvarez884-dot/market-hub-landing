"""Comments readers should not have to read: a reader reports one and stops seeing it, two
reports hide it from everybody until the owner has looked, and a reader who blocks an author
stops seeing what that author writes. Nobody is told who reported or blocked whom."""

import pytest

from conftest import ARTICLE, sign_in
from markethub import opinion as opinion_
from markethub.opinion import publishable

SLUG = ARTICLE["slug"]
OWNER = "9009"


@pytest.fixture(autouse=True)
def owner(opinion):
    opinion.admins.add(f"user{OWNER}@gmail.com")


def as_(client, sub):
    client.post("/api/auth/logout")
    sign_in(client, sub)
    return client


def post(client, text, parent=None):
    r = client.post("/api/opinion/comments", json={"slug": SLUG, "text": text, "parent_id": parent})
    assert r.status_code == 200, r.text
    return r.json()


def thread(client):
    return client.get("/api/public/opinion/comments", params={"slug": SLUG}).json()["comments"]


def report(client, id_):
    return client.post(f"/api/comments/{id_}/report")


def block(client, id_):
    return client.post("/api/blocks", json={"comment_id": id_})


# --- Reporting -------------------------------------------------------------------------------------


def test_a_reported_comment_is_hidden_from_who_reported_it_and_from_nobody_else(client, opinion):
    rude = post(as_(client, "1001"), "Something rude")
    under = post(client, "And more", rude["id"])
    assert report(as_(client, "2002"), rude["id"]).json() == {"reported": True}
    first, second = thread(client)
    assert first["hidden"] == "reported" and first["text"] == "" and first["name"] == "" and first["deleted"] is False
    assert second["id"] == under["id"] and second["hidden"] is None and second["text"] == "And more"
    # Reporting twice is one report. Its author and everybody else still read it.
    report(client, rude["id"])
    assert len(opinion.store.kept[rude["id"]]["reported_by"]) == 1
    assert thread(as_(client, "3003"))[0]["text"] == "Something rude" and "reports" not in thread(client)[0]
    assert thread(as_(client, "1001"))[0]["text"] == "Something rude"
    client.post("/api/auth/logout")
    assert thread(client)[0]["text"] == "Something rude"


def test_two_reports_hide_a_comment_from_everybody_until_the_owner_has_looked(client):
    rude = post(as_(client, "1001"), "Something rude")
    report(as_(client, "2002"), rude["id"])
    report(as_(client, "3003"), rude["id"])
    for reader in ("1001", "4004"):
        assert thread(as_(client, reader))[0] | {"created_utc": ""} == {
            "id": rude["id"], "parent_id": None, "depth": 0, "created_utc": "", "deleted": False, "hidden": "held",
            "name": "", "text": "", "mine": reader == "1001"}
    client.post("/api/auth/logout")
    assert thread(client)[0]["hidden"] == "held" and thread(client)[0]["text"] == ""
    # The owner reads it, with how many reported it, and it stays or goes.
    seen = thread(as_(client, OWNER))[0]
    assert seen["text"] == "Something rude" and seen["reports"] == 2 and seen["hidden"] is None
    waiting = client.get("/api/moderation/reports").json()["comments"]
    assert waiting == [{"id": rude["id"], "slug": SLUG, "name": "Ana", "text": "Something rude",
                        "created_utc": waiting[0]["created_utc"], "reports": 2, "held": True}]
    assert "user_id" not in waiting[0] and "reported_by" not in waiting[0]
    assert client.post(f"/api/moderation/reports/{rude['id']}/keep").json() == {"kept": True}
    assert client.get("/api/moderation/reports").json()["comments"] == []
    assert thread(as_(client, "2002"))[0]["text"] == "Something rude"  # kept: shown again, to who reported it too


def test_the_owner_takes_a_reported_comment_down_and_its_reports_go_with_it(client, opinion):
    rude = post(as_(client, "1001"), "Something rude")
    report(as_(client, "2002"), rude["id"])
    as_(client, OWNER)
    assert client.get("/api/moderation/reports").json()["comments"][0]["held"] is False
    assert client.delete(f"/api/opinion/comments/{rude['id']}").json() == {"deleted": True}
    assert client.get("/api/moderation/reports").json()["comments"] == []
    kept = opinion.store.kept[rude["id"]]
    assert kept["reported_by"] == [] and kept["reported"] is False and kept["user_id"] == ""


def test_only_the_owner_reviews_reports(client):
    rude = post(as_(client, "1001"), "Something rude")
    as_(client, "2002")
    assert client.get("/api/moderation/reports").status_code == 403
    assert client.post(f"/api/moderation/reports/{rude['id']}/keep").status_code == 403
    client.post("/api/auth/logout")
    assert client.get("/api/moderation/reports").status_code == 401 and report(client, rude["id"]).status_code == 401


def test_reports_that_are_refused(client):
    mine = post(as_(client, "1001"), "Mine")
    assert report(client, mine["id"]).status_code == 400  # one's own
    assert report(client, "no-such-comment").status_code == 400 and report(client, "../x").status_code in (400, 404)
    client.delete(f"/api/opinion/comments/{mine['id']}")
    assert report(as_(client, "2002"), mine["id"]).status_code == 400  # already gone


def test_a_member_reports_a_comment_of_the_competitions_discussion(client, opinion):
    opinion.post({"id": "1001", "name": "Ana"}, "competition-2026-11", "Something rude")
    rude = opinion.store.comments("competition-2026-11")[0]
    assert report(as_(client, "2002"), rude["id"]).json() == {"reported": True}
    assert opinion.comments("competition-2026-11", {"id": "2002"})[0]["hidden"] == "reported"


# --- Blocking --------------------------------------------------------------------------------------


def test_a_blocked_authors_comments_are_hidden_from_who_blocked_them_everywhere(client, opinion):
    one = post(as_(client, "1001"), "First of theirs")
    post(client, "Second of theirs")
    opinion.post({"id": "1001", "name": "Ana"}, "competition-2026-11", "Theirs, elsewhere")
    post(as_(client, "3003"), "Somebody else's")
    assert block(as_(client, "2002"), one["id"]).json() == {"blocked": True}
    shown = thread(client)
    assert [c["hidden"] for c in shown] == ["blocked", "blocked", None] and shown[0]["text"] == "" and shown[2]["text"] == "Somebody else's"
    assert opinion.comments("competition-2026-11", {"id": "2002"})[0]["hidden"] == "blocked"
    # Blocking twice is one block. Nobody else is affected, and the author is not told.
    block(client, one["id"])
    assert len(opinion.store.blocked) == 1
    assert [c["hidden"] for c in thread(as_(client, "3003"))] == [None, None, None]
    assert [c["hidden"] for c in thread(as_(client, "1001"))] == [None, None, None]
    assert client.get("/api/blocks").json() == {"blocked": []}


def test_a_reader_sees_who_they_blocked_by_name_and_unblocks_them(client):
    one = post(as_(client, "1001"), "Theirs")
    block(as_(client, "2002"), one["id"])
    (kept,) = client.get("/api/blocks").json()["blocked"]
    assert set(kept) == {"key", "name", "since_utc"} and kept["name"] == one["name"] and "1001" not in str(kept)
    # A key is only good for whoever made the block.
    assert as_(client, "3003").delete(f"/api/blocks/{kept['key']}").json() == {"unblocked": False}
    assert as_(client, "2002").delete(f"/api/blocks/{kept['key']}").json() == {"unblocked": True}
    assert client.get("/api/blocks").json() == {"blocked": []} and thread(client)[0]["text"] == "Theirs"


def test_blocks_that_are_refused(client, monkeypatch):
    mine = post(as_(client, "1001"), "Mine")
    assert block(client, mine["id"]).status_code == 400  # oneself
    assert block(client, "no-such-comment").status_code == 400
    theirs = post(as_(client, "2002"), "Theirs")
    monkeypatch.setattr(opinion_, "BLOCKS_MAX", 0)
    assert block(as_(client, "1001"), theirs["id"]).status_code == 400
    client.post("/api/auth/logout")
    assert block(client, theirs["id"]).status_code == 401 and client.get("/api/blocks").status_code == 401


# --- What goes with an account ---------------------------------------------------------------------


def test_deleting_an_account_takes_its_reports_and_the_blocks_of_it_and_by_it(client, opinion):
    theirs = post(as_(client, "1001"), "Theirs")
    mine = post(as_(client, "2002"), "Mine")
    report(client, theirs["id"])
    block(client, theirs["id"])
    block(as_(client, "3003"), mine["id"])
    assert len(opinion.store.blocked) == 2
    assert as_(client, "2002").delete("/api/me").json() == {"deleted": True}
    assert opinion.store.blocked == {}  # the one they made, and the one made of them
    assert opinion.store.kept[theirs["id"]]["reported_by"] == [] and opinion.store.kept[theirs["id"]]["reported"] is False
    assert "2002" not in str(opinion.store.kept)


# --- What is not published at all ------------------------------------------------------------------


@pytest.mark.parametrize("text", ["you f*cking idiot", "Kill yourself", "what a CUNT", "eres un hijo de puta", "maricón"])
def test_a_comment_in_language_nobody_should_have_to_read_is_not_taken(client, text):
    sign_in(client)
    r = client.post("/api/opinion/comments", json={"slug": SLUG, "text": text, "parent_id": None})
    assert r.status_code == 400 and "do not publish" in r.json()["detail"]
    assert thread(client) == []


@pytest.mark.parametrize("text", ["Scunthorpe had a good quarter", "The spice trade, classic", "A computadora and a disputa", "Assess the class action",
                                  "Hitchcock would short it", "kyst is Norwegian for coast"])
def test_the_floor_reads_whole_words_and_leaves_ordinary_ones_alone(text):
    assert publishable(text)


def test_a_name_shown_to_others_passes_the_same_floor(client):
    sign_in(client)
    client.put("/api/portfolio", json={"positions": [{"ticker": "AAPL", "shares": 1, "avg_cost": None}], "watchlist": []})
    r = client.put("/api/sharing", json={"enabled": True, "handle": "fuck you all"})
    assert r.status_code == 400 and r.json()["detail"] == "That name is not available."
