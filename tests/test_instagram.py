"""What the account posted on Instagram: read from the store, never from Instagram."""

import json

from markethub.instagram import FilePosts, Posts

JPEG = b"\xff\xd8\xff\xe0 a cover"
FRONT = {
    "handle": "the_market_hub_app", "read_utc": "2026-10-13T19:30:00+00:00",
    "posts": [
        {"id": "17877498573650605", "code": "DecgX7djfrr", "url": "https://www.instagram.com/reel/DecgX7djfrr/", "kind": "reel",
         "text": "The whole market, on one page.", "posted_utc": "2026-10-13T18:58:35+00:00", "cover": {"v": "aaaa1111bbbb", "upright": True}},
        {"id": "17868380742659104", "code": "DebrDiaAm18", "url": "https://www.instagram.com/p/DebrDiaAm18/", "kind": "photo",
         "text": "Market Hub, in one minute.", "posted_utc": "2026-10-13T11:12:47+00:00", "cover": {"v": "cccc2222dddd", "upright": False}},
    ],
}


def test_with_nothing_published_the_page_gets_no_posts(client):
    answer = client.get("/api/public/instagram")
    assert answer.status_code == 200
    assert answer.json() == {"posts": [], "handle": "", "read_utc": None}


def test_the_posts_come_newest_first_whatever_they_are_and_need_no_sign_in(client, posts):
    posts.kept = FRONT
    answer = client.get("/api/public/instagram").json()
    assert [p["kind"] for p in answer["posts"]] == ["reel", "photo"]
    assert answer["handle"] == "the_market_hub_app" and answer["read_utc"] == FRONT["read_utc"]
    assert [p["code"] for p in client.get("/api/public/instagram?limit=1").json()["posts"]] == ["DecgX7djfrr"]
    assert client.get("/api/public/instagram?limit=500").status_code == 422


def test_a_cover_is_served_as_a_picture_and_kept_for_good_by_its_version(client, posts):
    posts.covers["17877498573650605"] = JPEG
    named = client.get("/api/public/instagram/cover?id=17877498573650605&v=aaaa1111bbbb")
    assert named.status_code == 200 and named.content == JPEG and named.headers["content-type"] == "image/jpeg"
    assert "immutable" in named.headers["cache-control"]
    assert "immutable" not in client.get("/api/public/instagram/cover?id=17877498573650605").headers["cache-control"]


def test_a_cover_that_is_not_there_or_is_no_post_is_not_found(client, posts):
    posts.covers["17877498573650605"] = JPEG
    assert client.get("/api/public/instagram/cover?id=17868380742659104").status_code == 404
    assert client.get("/api/public/instagram/cover?id=../front").status_code == 404
    assert client.get("/api/public/instagram/cover").status_code == 422


def test_a_cover_is_read_from_the_store_once(posts):
    asked = []
    posts.covers["17877498573650605"] = JPEG
    read = posts.cover
    posts.cover = lambda id_: asked.append(id_) or read(id_)
    desk = Posts(posts)
    assert desk.cover("17877498573650605", "aaaa1111bbbb") == desk.cover("17877498573650605", "aaaa1111bbbb") == JPEG
    assert asked == ["17877498573650605"]
    assert desk.cover("17877498573650605", "another") == JPEG and len(asked) == 2   # made again: read again


def test_a_local_portal_reads_the_folder_the_media_repo_writes(tmp_path):
    (tmp_path / "covers").mkdir()
    (tmp_path / "front.json").write_text(json.dumps(FRONT), encoding="utf-8")
    (tmp_path / "covers" / "17877498573650605.jpg").write_bytes(JPEG)
    desk = Posts(FilePosts(tmp_path))
    assert [p["code"] for p in desk.latest()["posts"]] == ["DecgX7djfrr", "DebrDiaAm18"]
    assert desk.cover("17877498573650605") == JPEG and desk.cover("17868380742659104") is None
    assert Posts(FilePosts(tmp_path / "nothing")).latest() == {"posts": [], "handle": "", "read_utc": None}
