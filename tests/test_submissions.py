"""Readers' articles: a signed-in reader sends one in, it is kept for review and the owner is
told by email. Nothing is published, and the article leaves with its author."""

from conftest import ARTICLE, sign_in

from markethub import submissions as desk_
from markethub.submissions import BODY_CHARS, FileSubmissions, MemorySubmissions, NoSubmissions, Submissions, clean, review_message

BODY = "\n\n".join(["## A heading"] + [" ".join(["Word"] * 99) + "."] * 5)  # 495 words and a heading of two
GOOD = {"title": "Why the quiet jobs report matters", "dek": "Twenty-nine thousand jobs is not a collapse, and the reason it is not is the interesting part.",
        "body": BODY, "sources": ["https://www.bls.gov/news.release/empsit.htm", "The Fed's minutes | https://www.federalreserve.gov/minutes"],
        "tickers": ["aapl"], "byline": "Ana R.", "agree": True}


def send(client, **over):
    return client.post("/api/opinion/submissions", json={**GOOD, **over})


def test_sending_needs_an_account(client, submissions, outbox):
    assert send(client).status_code == 401
    assert client.get("/api/opinion/submissions").status_code == 401
    assert client.delete("/api/opinion/submissions/abcdef123").status_code == 401
    assert not submissions.store.kept and not outbox.sent


def test_an_article_is_kept_for_review_and_the_owner_is_told(client, submissions, outbox):
    sign_in(client)
    made = send(client).json()
    assert made["status"] == "in review" and made["title"] == GOOD["title"] and made["words"] == 497
    assert made["tickers"] == ["AAPL"] and made["byline"] == "Ana R."
    assert made["sources"] == [{"title": "www.bls.gov", "url": "https://www.bls.gov/news.release/empsit.htm"},
                               {"title": "The Fed's minutes", "url": "https://www.federalreserve.gov/minutes"}]
    # The author gets nothing of the account back, and the article is not an opinion article.
    assert "user_id" not in made and "email" not in made
    assert [a["slug"] for a in client.get("/api/public/opinion").json()["articles"]] == [ARTICLE["slug"]]
    # What is kept says whose it is, for the review.
    (kept,) = submissions.store.kept.values()
    assert (kept["user_id"], kept["email"], kept["provider"]) == ("1001", "user1001@gmail.com", "google")
    # The owner's message carries the article whole and where it is kept, and answers go to a verified address.
    (mail,) = outbox.sent
    assert mail["subject"] == f"[Market Hub] Article for review: {GOOD['title']}" and mail["reply_to"] == "user1001@gmail.com"
    assert "NOT published" in mail["text"] and BODY in mail["text"] and f"submissions/1001/{made['id']}.json" in mail["text"]
    listed = client.get("/api/opinion/submissions").json()
    assert listed["open"] is True and [a["id"] for a in listed["articles"]] == [made["id"]] and listed["limits"]["words"] == [450, 1500]


def test_what_cannot_be_taken_is_said_and_nothing_is_kept(client, submissions, outbox):
    sign_in(client)
    for over, said in [({"agree": False}, "Tick the box"), ({"title": "Short"}, "The title needs"), ({"dek": "Too short."}, "The summary needs"),
                       ({"body": "Only a few words."}, "450 to 1,500 words"), ({"body": BODY + "\n\n<script>alert(1)</script>"}, "without HTML"),
                       ({"body": BODY + " You should buy it."}, "what to do with their money"), ({"sources": ["https://www.bls.gov/"]}, "Name 2 to 10 sources"),
                       ({"sources": ["https://www.bls.gov/", "javascript:alert(1)"]}, "A source must be a web address"),
                       ({"sources": ["https://www.bls.gov/", 7]}, "list of web addresses"), ({"tickers": ["not a ticker"]}, "tickers"),
                       ({"byline": "A"}, "The name to sign it with"), ({"body": "a " * (BODY_CHARS // 2 + 1)}, "characters")]:
        r = send(client, **over)
        assert r.status_code == 400 and said in r.json()["detail"], (over, r.text)
    assert not submissions.store.kept and not outbox.sent
    # A line break in a title never reaches the subject of the message.
    assert send(client, title="Why the quiet jobs\r\nBcc: someone@example.com report").status_code == 200
    assert "\n" not in outbox.sent[0]["subject"]


def test_the_name_of_the_account_signs_it_when_none_is_given(client):
    sign_in(client)
    assert send(client, byline="  ").json()["byline"] == "Ana"


def test_a_day_takes_three_and_a_refused_one_does_not_count(client):
    sign_in(client)
    assert send(client, body="Too short.").status_code == 400
    assert [send(client).status_code for _ in range(4)] == [200, 200, 200, 429]
    # Somebody else is not held back by it.
    client.post("/api/auth/logout")
    sign_in(client, "2002")
    assert send(client).status_code == 200


def test_an_account_keeps_only_so_many_at_a_time(client, submissions):
    submissions.kept_per_user = 2
    sign_in(client)
    first = send(client).json()
    assert send(client).status_code == 200
    r = send(client)
    assert r.status_code == 400 and "Take one back" in r.json()["detail"]
    assert client.delete(f"/api/opinion/submissions/{first['id']}").json() == {"withdrawn": True}
    assert send(client).status_code == 200


def test_the_author_takes_it_back_and_nobody_else_can(client, submissions, outbox):
    sign_in(client)
    made = send(client).json()
    client.post("/api/auth/logout")
    sign_in(client, "2002")
    assert client.delete(f"/api/opinion/submissions/{made['id']}").json() == {"withdrawn": False}
    assert client.get("/api/opinion/submissions").json()["articles"] == []
    assert len(submissions.store.kept) == 1
    client.post("/api/auth/logout")
    sign_in(client)
    assert client.delete(f"/api/opinion/submissions/{made['id']}").json() == {"withdrawn": True}
    assert client.delete("/api/opinion/submissions/no").json() == {"withdrawn": False}
    assert not submissions.store.kept and outbox.sent[-1]["subject"].startswith("[Market Hub] Article withdrawn")


def test_deleting_the_account_removes_its_articles(client, submissions, outbox):
    sign_in(client)
    send(client)
    assert client.delete("/api/me").json() == {"deleted": True}
    assert not submissions.store.kept and "deleted their account" in outbox.sent[-1]["text"]


def test_a_password_account_is_said_to_be_unverified_and_gets_no_reply_to(client, outbox):
    r = client.post("/api/auth/register", json={"email": "leo@example.com", "password": "a long enough password", "name": "Leo Sanz", "captcha": "human"})
    assert r.status_code == 200, r.text
    assert send(client, byline="").json()["byline"] == "Leo Sanz"
    (mail,) = outbox.sent
    assert mail["reply_to"] is None and "NOT verified" in mail["text"] and "leo@example.com" in mail["text"]


def test_the_article_is_kept_even_when_the_message_fails(client, submissions, outbox):
    outbox.broken = True
    sign_in(client)
    assert send(client).status_code == 200
    assert len(submissions.store.kept) == 1 and not outbox.sent


def test_a_store_that_fails_says_so_and_keeps_the_text_out_of_the_answer(client, submissions, outbox):
    def broken(doc):
        raise RuntimeError("bucket is down")

    submissions.store.put = broken
    sign_in(client)
    r = send(client)
    assert r.status_code == 503 and "could not be kept" in r.json()["detail"] and not outbox.sent


def test_articles_are_not_taken_where_nobody_would_hear_of_them(client, submissions):
    submissions.mailer, submissions.store.local = None, False  # a bucket, and no mailbox
    sign_in(client)
    assert client.get("/api/opinion/submissions").json()["open"] is False
    assert send(client).status_code == 503 and not submissions.store.kept


def test_the_site_is_told_whether_articles_are_taken(client, submissions):
    assert client.get("/api/config").json()["submissions"] is True
    submissions.mailer, submissions.store.local = None, False
    assert client.get("/api/config").json()["submissions"] is False


def test_a_deployed_service_with_no_bucket_takes_nothing(client, submissions, outbox, monkeypatch):
    monkeypatch.setattr(desk_, "SUBMISSIONS_BUCKET", "")
    monkeypatch.setenv("MARKETHUB_FIRESTORE", "1")
    assert isinstance(desk_.default_submissions(), NoSubmissions)
    monkeypatch.delenv("MARKETHUB_FIRESTORE")
    assert isinstance(desk_.default_submissions(), FileSubmissions)
    # Even with a mailbox: nothing is kept on the instance's own disk.
    submissions.store = NoSubmissions()
    sign_in(client)
    assert client.get("/api/opinion/submissions").json() == {"open": False, "articles": [], "limits": client.get("/api/opinion/submissions").json()["limits"], "per_day": 3}
    assert send(client).status_code == 503 and not outbox.sent


def test_the_phone_app_sends_with_its_token(client, logins, submissions):
    client.post("/api/auth/register", json={"email": "leo@example.com", "password": "a long enough password", "name": "Leo", "captcha": "human"})
    client.post("/api/auth/logout")
    token = client.post("/api/app/auth/password", json={"email": "leo@example.com", "password": "a long enough password"}).json()["token"]
    client.cookies.clear()
    r = client.post("/api/opinion/submissions", json=GOOD, headers={"authorization": f"Bearer {token}", "origin": ""})
    assert r.status_code == 200 and len(submissions.store.kept) == 1


def test_files_keep_and_remove_an_article(tmp_path):
    desk = Submissions(FileSubmissions(tmp_path))
    article = clean(**{k: v for k, v in GOOD.items() if k != "agree"}, agreed=True)
    made = desk.send({"id": "mh_abc", "email": "a@b.co", "name": "Ana", "provider": "password"}, article)
    assert (tmp_path / "mh_abc" / f"{made['id']}.json").exists() and desk.open
    assert [a["id"] for a in desk.mine("mh_abc")] == [made["id"]] and desk.mine("../mh_abc") == []
    assert desk.withdraw("mh_abc", made["id"]) and not desk.mine("mh_abc")


def test_the_message_names_the_place(submissions):
    doc = {**clean(**{k: v for k, v in GOOD.items() if k != "agree"}, agreed=True), "id": "abc123xyz", "user_id": "1001", "email": "a@gmail.com",
           "account_name": "Ana", "provider": "google", "received_utc": "2026-10-08T10:00:00+00:00"}
    subject, text = review_message(doc, MemorySubmissions().where(doc))
    assert "Ana <a@gmail.com> (Google, a verified address)" in text and "submissions/1001/abc123xyz.json" in text and GOOD["title"] in subject
