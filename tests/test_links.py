"""Day 3 tests: link CRUD, ownership scoping, URL/slug validation, and
slug generation (unit)."""
from urllib.parse import urlparse

from app.services import slugs as slug_service

TEST_URL = "https://example.com/very/long"


# --- create ------------------------------------------------------------------


def test_create_with_random_slug(make_auth, client):
    resp = client.post("/links", json={"target_url": TEST_URL}, headers=make_auth())
    body = resp.json()
    assert resp.status_code == 201
    assert len(body["slug"]) == slug_service.RANDOM_SLUG_LENGTH
    assert set(body["slug"]) <= set(slug_service.ALPHABET)
    assert body["target_url"] == TEST_URL
    assert body["is_active"] is True


def test_create_with_custom_slug(make_auth, client):
    resp = client.post(
        "/links",
        json={"target_url": TEST_URL, "custom_slug": "My-Page_42"},
        headers=make_auth(),
    )
    body = resp.json()
    assert resp.status_code == 201
    assert body["slug"] == "my-page_42"  # normalized to lowercase


def test_create_requires_auth(client):
    resp = client.post("/links", json={"target_url": TEST_URL})
    assert resp.status_code == 401


def test_create_rejects_javascript_scheme(make_auth, client):
    resp = client.post(
        "/links", json={"target_url": "javascript:alert(1)"}, headers=make_auth()
    )
    assert resp.status_code == 422
    assert "scheme" in resp.json()["detail"][0]["msg"].lower()


def test_create_rejects_non_http_schemes(make_auth, client):
    for bad in ("ftp://example.com/file", "data:text/html,<h1>hi</h1>", "file:///etc/passwd"):
        resp = client.post("/links", json={"target_url": bad}, headers=make_auth())
        assert resp.status_code == 422, bad


def test_create_rejects_url_without_host(make_auth, client):
    resp = client.post("/links", json={"target_url": "https://"}, headers=make_auth())
    assert resp.status_code == 422


def test_create_rejects_invalid_custom_slug(make_auth, client):
    for bad in ("no", "has space", "under_score only!", "-startsdash", "@"):
        resp = client.post(
            "/links",
            json={"target_url": TEST_URL, "custom_slug": bad},
            headers=make_auth(),
        )
        assert resp.status_code == 422, bad


def test_create_rejects_reserved_slug(make_auth, client):
    resp = client.post(
        "/links",
        json={"target_url": TEST_URL, "custom_slug": "docs"},
        headers=make_auth(),
    )
    assert resp.status_code == 422


def test_create_duplicate_custom_slug_409(make_auth, client):
    headers = make_auth()
    first = client.post(
        "/links", json={"target_url": TEST_URL, "custom_slug": "taken"}, headers=headers
    )
    assert first.status_code == 201
    second = client.post(
        "/links", json={"target_url": TEST_URL, "custom_slug": "taken"}, headers=headers
    )
    assert second.status_code == 409


# --- list --------------------------------------------------------------------


def test_list_paginates_newest_first(make_auth, client):
    headers = make_auth()
    created = [
        client.post(
            "/links", json={"target_url": f"{TEST_URL}/{i}"}, headers=headers
        ).json()
        for i in range(5)
    ]
    page1 = client.get("/links", params={"limit": 2, "offset": 0}, headers=headers).json()
    page2 = client.get("/links", params={"limit": 2, "offset": 2}, headers=headers).json()

    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert page2["items"][0]["id"] == created[-3]["id"]  # newest first ordering
    all_ids = [i["id"] for i in page1["items"] + page2["items"]]
    assert len(set(all_ids)) == 4  # no overlap between pages


def test_list_is_scoped_to_owner(make_auth, client):
    make_auth()  # alice: has no links
    bob_headers = make_auth("bob@example.com")
    client.post("/links", json={"target_url": TEST_URL}, headers=bob_headers)

    empty = client.get("/links", headers=make_auth("alice2@example.com")).json()
    bobs = client.get("/links", headers=bob_headers).json()
    assert empty["total"] == 0
    assert bobs["total"] == 1


# --- get / patch / delete ---------------------------------------------------


def test_get_owned_link(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": TEST_URL}, headers=headers).json()
    resp = client.get(f"/links/{link['id']}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["slug"] == link["slug"]


def test_get_someone_elses_link_is_404(make_auth, client):
    owner_headers = make_auth()
    link = client.post("/links", json={"target_url": TEST_URL}, headers=owner_headers).json()
    stranger = make_auth("stranger@example.com")
    resp = client.get(f"/links/{link['id']}", headers=stranger)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Link not found"


def test_patch_updates_target_url_and_slug(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": TEST_URL}, headers=headers).json()
    resp = client.patch(
        f"/links/{link['id']}",
        json={"target_url": "https://new.example.com/x", "custom_slug": "renamed"},
        headers=headers,
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["target_url"] == "https://new.example.com/x"
    assert body["slug"] == "renamed"


def test_patch_to_taken_slug_409(make_auth, client):
    headers = make_auth()
    client.post("/links", json={"target_url": TEST_URL, "custom_slug": "one"}, headers=headers)
    other = client.post("/links", json={"target_url": TEST_URL, "custom_slug": "two"}, headers=headers).json()
    resp = client.patch(
        f"/links/{other['id']}", json={"custom_slug": "one"}, headers=headers
    )
    assert resp.status_code == 409


def test_patch_deactivates(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": TEST_URL}, headers=headers).json()
    resp = client.patch(f"/links/{link['id']}", json={"is_active": False}, headers=headers)
    assert resp.json()["is_active"] is False


def test_patch_someone_elses_link_404(make_auth, client):
    owner = make_auth()
    link = client.post("/links", json={"target_url": TEST_URL}, headers=owner).json()
    resp = client.patch(
        f"/links/{link['id']}",
        json={"is_active": False},
        headers=make_auth("marauder@example.com"),
    )
    assert resp.status_code == 404


def test_delete_removes_link(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": TEST_URL}, headers=headers).json()
    assert client.delete(f"/links/{link['id']}", headers=headers).status_code == 204
    assert client.get(f"/links/{link['id']}", headers=headers).status_code == 404


def test_delete_someone_elses_link_404(make_auth, client):
    owner = make_auth()
    link = client.post("/links", json={"target_url": TEST_URL}, headers=owner).json()
    resp = client.delete(f"/links/{link['id']}", headers=make_auth("voldemort@example.com"))
    assert resp.status_code == 404
    # and it really was not deleted
    assert client.get(f"/links/{link['id']}", headers=owner).status_code == 200


# --- slug generation (unit) ---------------------------------------------------


def test_random_slug_length_and_charset():
    for _ in range(50):
        s = slug_service.random_slug(7)
        assert len(s) == 7
        assert set(s) <= set(slug_service.ALPHABET)


def test_generate_unique_slug_retries_on_collision(monkeypatch):
    """Seed real collisions, then force the generator to hit them: it must
    retry past them and return something genuinely free."""
    from app.core.db import SessionLocal
    from app.models.user import User
    from app.services import link_service as ls

    db = SessionLocal()
    try:
        user = User(email="slug-collision-test@example.com", password_hash="x")
        db.add(user)
        db.commit()
        for slug in ("AAAAAAA", "BBBBBBB"):
            ls.create_link(db, user.id, TEST_URL, custom_slug=slug)

        responses = iter(["AAAAAAA", "BBBBBBB", "CCRRCCT"])
        monkeypatch.setattr(
            slug_service, "random_slug", lambda length: next(responses)
        )
        result = slug_service.generate_unique_slug(db)
        assert result not in ("AAAAAAA", "BBBBBBB")
        assert slug_service.slug_exists(db, result) is False
    finally:
        db.close()


def test_redirect_location_parses(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/leaving"}, headers=headers
    ).json()
    resp = client.get(f"/{link['slug']}", follow_redirects=False)
    assert urlparse(resp.headers["location"]).scheme == "https"
