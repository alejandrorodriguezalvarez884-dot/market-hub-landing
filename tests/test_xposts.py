"""What the account posted on X: read from the store, never from X."""

from markethub.xposts import FileX, XPosts

FRONT = {
    "handle": "themarkethub", "read_utc": "2026-10-14T21:05:00+00:00",
    "posts": [
        {"id": "1845000000000000002", "url": "https://x.com/themarkethub/status/1845000000000000002",
         "text": "The S&P 500 ended 0.8% higher.\n\nhttps://themarkethub.app/today/", "posted_utc": "2026-10-14T21:00:00+00:00"},
        {"id": "1845000000000000001", "url": "https://x.com/themarkethub/status/1845000000000000001",
         "text": "A new episode: what debt costs.", "posted_utc": "2026-10-13T18:00:00+00:00"},
    ],
}


def test_with_nothing_posted_the_page_gets_no_posts(client):
    answer = client.get("/api/public/x")
    assert answer.status_code == 200
    assert answer.json() == {"posts": [], "handle": "", "read_utc": None}


def test_the_posts_come_newest_first_and_need_no_sign_in(client, x_posts):
    x_posts.kept = FRONT
    answer = client.get("/api/public/x").json()
    assert [p["id"] for p in answer["posts"]] == ["1845000000000000002", "1845000000000000001"]
    assert answer["handle"] == "themarkethub" and answer["read_utc"] == FRONT["read_utc"]
    assert len(client.get("/api/public/x?limit=1").json()["posts"]) == 1
    assert client.get("/api/public/x?limit=500").status_code == 422


def test_the_front_is_read_once_a_minute(x_posts):
    asked = []
    x_posts.front = lambda: asked.append(1) or FRONT
    shown = XPosts(x_posts)
    shown.latest()
    shown.latest()
    assert len(asked) == 1


def test_a_local_portal_reads_the_folder_media_leaves(tmp_path):
    import json

    (tmp_path / "front.json").write_text(json.dumps(FRONT), encoding="utf-8")
    assert XPosts(FileX(tmp_path)).latest()["handle"] == "themarkethub"
    assert XPosts(FileX(tmp_path / "none")).latest()["posts"] == []
