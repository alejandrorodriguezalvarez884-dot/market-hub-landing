"""Opinion: anyone reads the articles and their threads; only a signed-in reader comments, and
what a comment shows of its author is a first name."""

from conftest import ARTICLE, sign_in

SLUG = ARTICLE["slug"]


def post(client, text, parent=None, slug=SLUG):
    return client.post("/api/opinion/comments", json={"slug": slug, "text": text, "parent_id": parent})


def thread(client):
    return client.get("/api/public/opinion/comments", params={"slug": SLUG}).json()


def test_articles_are_public_and_the_list_carries_no_body(client):
    cards = client.get("/api/public/opinion").json()["articles"]
    assert [a["slug"] for a in cards] == [SLUG] and "body" not in cards[0] and "sources" not in cards[0]
    one = client.get("/api/public/opinion/item", params={"slug": SLUG}).json()
    assert one["body"].startswith("First paragraph.") and one["sources"][0]["url"] == "https://www.bls.gov/"
    assert client.get("/api/public/opinion/item", params={"slug": "no-such-article"}).status_code == 404
    assert client.get("/api/public/opinion/item", params={"slug": "../etc/passwd"}).status_code == 404


def test_reading_the_thread_needs_no_account_and_commenting_does(client):
    assert thread(client) == {"comments": [], "signed_in": False, "moderator": False}
    assert post(client, "Hello").status_code == 401
    sign_in(client)
    made = post(client, "  A first comment.\r\n\r\n\r\n\r\nWith a second line.  ").json()
    assert made["text"] == "A first comment.\n\nWith a second line." and made["mine"] is True and made["depth"] == 0
    # What the page gets of the author: the first name, and never the account.
    assert made["name"] == "Ana" and "user_id" not in made and "email" not in str(made)
    assert thread(client)["signed_in"] is True
    # The account page shows them as kept; nobody else's.
    assert [c["text"] for c in client.get("/api/opinion/mine").json()["comments"]] == [made["text"]]
    client.post("/api/auth/logout")
    assert client.get("/api/opinion/mine").status_code == 401


def test_answers_nest_and_stop_at_a_depth(client):
    sign_in(client)
    parent = post(client, "Top").json()
    answer = post(client, "Answer", parent["id"]).json()
    assert (answer["parent_id"], answer["depth"]) == (parent["id"], 1)
    deep = answer
    for _ in range(5):
        deep = post(client, "Deeper", deep["id"]).json()
    assert deep["depth"] == 6
    assert post(client, "Too deep", deep["id"]).status_code == 400
    assert [c["depth"] for c in thread(client)["comments"]] == [0, 1, 2, 3, 4, 5, 6]


def test_comments_that_are_refused(client):
    sign_in(client)
    assert post(client, "   ").status_code == 400
    assert post(client, "x" * 2001).status_code == 400
    assert post(client, "Hello", slug="no-such-article").status_code == 400
    assert post(client, "Hello", parent="nosuchcomment").status_code == 400
    assert client.post("/api/opinion/comments", json={"slug": SLUG, "text": "Hi"}, headers={"origin": "https://evil.example"}).status_code == 403


def test_only_its_author_or_the_owner_takes_a_comment_down(client, opinion):
    sign_in(client, "1001")
    mine = post(client, "Mine").json()
    reply = post(client, "A reply", mine["id"]).json()
    client.post("/api/auth/logout")
    sign_in(client, "2002")
    assert thread(client)["comments"][0]["mine"] is False
    assert client.delete(f"/api/opinion/comments/{mine['id']}").status_code == 403
    client.post("/api/auth/logout")
    sign_in(client, "1001")
    assert client.delete(f"/api/opinion/comments/{mine['id']}").json() == {"deleted": True}
    assert client.delete(f"/api/opinion/comments/{mine['id']}").json() == {"deleted": False}
    first, second = thread(client)["comments"]
    # Its place stays, empty, so the answer under it keeps its sense. No answering it any more.
    assert first == {"id": mine["id"], "parent_id": None, "depth": 0, "created_utc": first["created_utc"], "deleted": True,
                     "name": "", "text": "", "mine": False}
    assert second["id"] == reply["id"] and post(client, "To a ghost", mine["id"]).status_code == 400
    # The owner's address is the one in MARKETHUB_ADMINS.
    assert opinion.can_moderate({"email": "Owner@gmail.com"}) and not opinion.can_moderate({"email": "user1001@gmail.com"})
    assert opinion.remove({"id": "9", "email": "owner@gmail.com"}, reply["id"]) is True


def test_deleting_the_account_takes_its_comments(client, opinion):
    sign_in(client, "1001")
    post(client, "One")
    post(client, "Two")
    assert client.delete("/api/me").json() == {"deleted": True}
    assert all(c["deleted"] and c["text"] == "" for c in thread(client)["comments"])
    assert all(c["user_id"] == "" for c in opinion.store.kept.values())  # nothing of the account is left on them


def test_a_reader_cannot_comment_without_end(client):
    sign_in(client)
    codes = [post(client, f"Comment {i}").status_code for i in range(22)]
    assert codes[:20] == [200] * 20 and codes[20:] == [429, 429]
