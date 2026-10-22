"""Day 3 tests: the public GET /{slug} redirect and click logging."""
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.click import Click
from app.services.device import classify_device


def _count_clicks(slug: str) -> list[Click]:
    db = SessionLocal()
    try:
        from app.models.link import Link

        link = db.scalars(select(Link).where(Link.slug == slug)).first()
        if link is None:
            return []
        return list(db.scalars(select(Click).where(Click.link_id == link.id)))
    finally:
        db.close()


def test_redirect_302_with_location(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links",
        json={"target_url": "https://example.com/target"},
        headers=headers,
    ).json()
    resp = client.get(f"/{link['slug']}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/target"


def test_redirect_unknown_slug_404(client):
    resp = client.get("/no-such-slug-here", follow_redirects=False)
    assert resp.status_code == 404


def test_redirect_unknown_slug_same_error_as_deactivated(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/a"}, headers=headers).json()
    client.patch(f"/links/{link['id']}", json={"is_active": False}, headers=headers)
    absent = client.get("/never-existed", follow_redirects=False).json()
    inactive = client.get(f"/{link['slug']}", follow_redirects=False).json()
    assert absent == inactive  # consistent 404 body, no existence leak


def test_redirect_deactivated_link_404(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/b"}, headers=headers).json()
    client.patch(f"/links/{link['id']}", json={"is_active": False}, headers=headers)
    assert client.get(f"/{link['slug']}", follow_redirects=False).status_code == 404


def test_redirect_logs_click(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/logged"}, headers=headers
    ).json()
    client.get(f"/{link['slug']}", follow_redirects=False)  # visitors only GET
    clicks = _count_clicks(link["slug"])
    assert len(clicks) == 1
    assert clicks[0].referrer is None  # TestClient sends no referer
    assert clicks[0].device_type in ("desktop", "mobile", "tablet", "other")


def test_redirect_records_referrer(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/r"}, headers=headers).json()
    client.get(
        f"/{link['slug']}",
        follow_redirects=False,
        headers={"referer": "https://news.ycombinator.com/item?id=1"},
    )
    clicks = _count_clicks(link["slug"])
    assert clicks[0].referrer == "https://news.ycombinator.com/item?id=1"


def test_redirect_mobile_traffic_logged_as_mobile(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/m"}, headers=headers).json()
    client.get(
        f"/{link['slug']}",
        follow_redirects=False,
        headers={
            "user-agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Safari/604.1"
            )
        },
    )
    assert _count_clicks(link["slug"])[0].device_type == "mobile"


def test_redirect_two_visits_two_click_rows(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/2"}, headers=headers).json()
    for _ in range(2):
        client.get(f"/{link['slug']}", follow_redirects=False)
    assert len(_count_clicks(link["slug"])) == 2


# --- device classifier (unit) --------------------------------------------------

def test_classify_device_variants():
    cases = {
        "Mozilla/5.0 (iPad; CPU OS 16) AppleWebKit": "tablet",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) Chrome Mobile": "mobile",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/122.0": "desktop",
        "curl/8.4.0": "other",
        None: "other",
        "": "other",
        "Googlebot/2.1 (+http://www.google.com/bot.html)": "other",
    }
    for ua, expected in cases.items():
        assert classify_device(ua) == expected, ua
