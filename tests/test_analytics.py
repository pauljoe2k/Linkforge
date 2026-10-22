"""Day 5 tests: analytics endpoints over seeded click rows (via factories)."""

def test_summary_totals_and_device_breakdown(make_auth, client, factories):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/s1"}, headers=headers).json()
    factories.clicks(
        link["id"],
        [
            (factories.utc(2026, 10, 1), "https://news.ycombinator.com", "desktop"),
            (factories.utc(2026, 10, 1), None, "mobile"),
            (factories.utc(2026, 10, 2), "https://twitter.com/xyz", "tablet"),
            (factories.utc(2026, 10, 2), None, "other"),
            (factories.utc(2026, 10, 3), None, "desktop"),
        ],
    )
    resp = client.get(f"/links/{link['id']}/analytics/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_clicks"] == 5
    assert body["devices"] == {"desktop": 2, "mobile": 1, "tablet": 1, "other": 1}


def test_summary_zero_clicks(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/s0"}, headers=headers).json()
    body = client.get(f"/links/{link['id']}/analytics/summary", headers=headers).json()
    assert body["total_clicks"] == 0
    assert body["devices"] == {"desktop": 0, "mobile": 0, "tablet": 0, "other": 0}


def test_daily_grouped_in_sql_with_date_range(make_auth, client, factories):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/d"}, headers=headers).json()
    factories.clicks(
        link["id"],
        [
            (factories.utc(2026, 10, 1, 9), "r", "mobile"),
            (factories.utc(2026, 10, 1, 21), None, "desktop"),
            (factories.utc(2026, 10, 3), None, "desktop"),
            (factories.utc(2026, 10, 4), None, "desktop"),  # outside range
        ],
    )
    resp = client.get(
        f"/links/{link['id']}/analytics/daily",
        params={"start": "2026-10-01", "end": "2026-10-03"},
        headers=headers,
    )
    assert resp.status_code == 200
    days = resp.json()["days"]
    assert days == [
        {"day": "2026-10-01", "clicks": 2},  # two clicks same day -> grouped
        {"day": "2026-10-03", "clicks": 1},
    ]


def test_daily_start_after_end_422(make_auth, client):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/dx"}, headers=headers).json()
    resp = client.get(
        f"/links/{link['id']}/analytics/daily",
        params={"start": "2026-10-08", "end": "2026-10-01"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_referrers_top_n_with_direct_bucket(make_auth, client, factories):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/r"}, headers=headers).json()
    factories.clicks(
        link["id"],
        [
            (factories.utc(2026, 10, 1), "https://news.ycombinator.com", "desktop"),
            (factories.utc(2026, 10, 1), "https://news.ycombinator.com", "mobile"),
            (factories.utc(2026, 10, 1), "https://news.ycombinator.com", "other"),
            (factories.utc(2026, 10, 1), "https://twitter.com/xyz", "mobile"),
            (factories.utc(2026, 10, 2), None, "desktop"),
            (factories.utc(2026, 10, 2), None, "mobile"),
        ],
    )
    resp = client.get(
        f"/links/{link['id']}/analytics/referrers", params={"limit": 5}, headers=headers
    )
    body = resp.json()["referrers"]
    assert body == [
        {"referrer": "https://news.ycombinator.com", "clicks": 3},
        {"referrer": "direct", "clicks": 2},       # NULL referrer bucketed
        {"referrer": "https://twitter.com/xyz", "clicks": 1},
    ]


def test_referrers_limit_caps_results(make_auth, client, factories):
    headers = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/rl"}, headers=headers).json()
    factories.clicks(
        link["id"],
        [(factories.utc(2026, 10, 1), f"https://src{i}.example.com", "desktop") for i in range(5)],
    )
    body = client.get(
        f"/links/{link['id']}/analytics/referrers", params={"limit": 2}, headers=headers
    ).json()
    assert len(body["referrers"]) == 2
    assert body["referrers"][0]["clicks"] == 1


def test_foreign_user_sees_404_on_all_analytics(make_auth, client, factories):
    owner = make_auth()
    link = client.post("/links", json={"target_url": "https://x.com/o"}, headers=owner).json()
    factories.clicks(link["id"], [(factories.utc(2026, 10, 1), "https://hacker.io", "desktop")])
    stranger = make_auth("sneaky@example.com")

    summary = client.get(f"/links/{link['id']}/analytics/summary", headers=stranger)
    daily = client.get(
        f"/links/{link['id']}/analytics/daily",
        params={"start": "2026-01-01", "end": "2026-01-31"},
        headers=stranger,
    )
    referrers = client.get(f"/links/{link['id']}/analytics/referrers", headers=stranger)
    assert summary.status_code == daily.status_code == referrers.status_code == 404
    oracle = client.get(
        "/links/999999/analytics/summary", headers=make_auth("otheruser@example.com")
    ).json()
    # Absent link body must be identical to the foreign-link body.
    assert summary.json() == oracle


def test_nonexistent_link_404(make_auth, client):
    resp = client.get("/links/424242/analytics/summary", headers=make_auth())
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Link not found"}


def test_analytics_service_raises_keyerror_on_missing(make_auth, client):
    from app.core.db import SessionLocal
    from app.services import analytics_service

    db = SessionLocal()
    try:
        import pytest as pytest_module

        pytest_module.raises(KeyError, analytics_service.get_summary, db, 0, 1)
    finally:
        db.close()


def test_analytics_requires_auth(client):
    resp = client.get("/links/1/analytics/summary")
    assert resp.status_code == 401
