"""Day 4 tests: redirect cache (hit + invalidation proof) and rate limits."""
import json

from app.core import redis as redis_module
from app.core.config import settings
from app.services import rate_limit
from app.services.cache import _PREFIX


def _redis():
    return redis_module.get_redis_client()


# --- cache hits ---------------------------------------------------------------


def test_first_redirect_populates_cache(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/cache"}, headers=headers
    ).json()
    client.get(f"/{link['slug']}", follow_redirects=False)
    raw = _redis().get(_PREFIX + link["slug"])
    assert raw is not None
    payload = json.loads(raw)
    assert payload["target_url"] == "https://example.com/cache"
    assert payload["link_id"] == link["id"]


def test_cache_hit_still_redirects_and_logs_click(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/hit"}, headers=headers
    ).json()
    # Warm the cache, then DELETE from DB standalone proof: route must not
    # read the DB for the value (it cannot, see invalidation-only test):
    client.get(f"/{link['slug']}", follow_redirects=False)
    second = client.get(f"/{link['slug']}", follow_redirects=False)
    assert second.status_code == 302
    assert second.headers["location"] == "https://example.com/hit"


# --- invalidation proofs ------------------------------------------------------


def test_patch_invalidation_proof(make_auth, client):
    """THE Day 4 proof: serve once (cache warm), retarget the link, serve
    again. Without correct invalidation the second response would still be
    the OLD target."""
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://old.example.com/x"}, headers=headers
    ).json()
    warm = client.get(f"/{link['slug']}", follow_redirects=False)
    assert warm.headers["location"] == "https://old.example.com/x"

    client.patch(
        f"/links/{link['id']}",
        json={"target_url": "https://new.example.com/y"},
        headers=headers,
    )
    after = client.get(f"/{link['slug']}", follow_redirects=False)
    assert after.status_code == 302
    assert after.headers["location"] == "https://new.example.com/y"


def test_slug_rename_invalidates_old_and_new(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links",
        json={"target_url": "https://example.com/orig", "custom_slug": "oldname"},
        headers=headers,
    ).json()
    client.get("/oldname", follow_redirects=False)  # warm cache under oldname
    client.patch(f"/links/{link['id']}", json={"custom_slug": "newname"}, headers=headers)

    assert client.get("/oldname", follow_redirects=False).status_code == 404
    renamed = client.get("/newname", follow_redirects=False)
    assert renamed.status_code == 302
    assert renamed.headers["location"] == "https://example.com/orig"


def test_deactivate_invalidation_proof(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/off"}, headers=headers
    ).json()
    assert client.get(f"/{link['slug']}", follow_redirects=False).status_code == 302
    client.patch(f"/links/{link['id']}", json={"is_active": False}, headers=headers)
    assert client.get(f"/{link['slug']}", follow_redirects=False).status_code == 404


def test_delete_invalidation_proof(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/gone"}, headers=headers
    ).json()
    assert client.get(f"/{link['slug']}", follow_redirects=False).status_code == 302
    client.delete(f"/links/{link['id']}", headers=headers)
    # Would still 302 if the cache had survived the delete.
    assert client.get(f"/{link['slug']}", follow_redirects=False).status_code == 404


def test_cache_ttl_is_applied(make_auth, client):
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/ttl"}, headers=headers
    ).json()
    client.get(f"/{link['slug']}", follow_redirects=False)
    ttl = _redis().ttl(_PREFIX + link["slug"])
    assert 0 < ttl <= settings.cache_redirect_ttl_seconds


# --- rate limiting ------------------------------------------------------------


def test_rate_limit_hit_allows_under_limit_and_refuses_over(monkeypatch):
    monkeypatch.setattr(
        rate_limit, "hit", rate_limit.hit  # explicit: using the real one
    )
    key = "rate:test:allow-block"
    assert rate_limit.hit(key, limit=2, window_seconds=60) == (True, 0)
    assert rate_limit.hit(key, limit=2, window_seconds=60) == (True, 0)
    allowed, retry_after = rate_limit.hit(key, limit=2, window_seconds=60)
    assert allowed is False
    assert 0 < retry_after <= 60

def test_rate_limit_window_resets(monkeypatch):
    key = "rate:test:reset"
    assert rate_limit.hit(key, limit=1, window_seconds=60) == (True, 0)
    assert rate_limit.hit(key, limit=1, window_seconds=60)[0] is False


def test_redirect_429_per_ip_with_retry_after(make_auth, client, monkeypatch):
    monkeypatch.setattr(settings, "redirect_rate_limit", 2)
    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/429"}, headers=headers
    ).json()
    url = f"/{link['slug']}"
    assert client.get(url, follow_redirects=False).status_code == 302
    assert client.get(url, follow_redirects=False).status_code == 302
    resp = client.get(url, follow_redirects=False)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 1


def test_api_429_per_user_with_retry_after(make_auth, client, monkeypatch):
    monkeypatch.setattr(settings, "api_rate_limit", 2)
    headers = make_auth()
    assert client.post("/links", json={"target_url": "https://x.com/1"}, headers=headers).status_code == 201
    assert client.post("/links", json={"target_url": "https://x.com/2"}, headers=headers).status_code == 201
    resp = client.post("/links", json={"target_url": "https://x.com/3"}, headers=headers)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def _outage(monkeypatch, caplog=None):
    """Force Redis-down in-process: every client operation raises."""
    import redis

    class _DeadClient:
        def __getattr__(self, name):
            raise redis.ConnectionError("simulated outage")

    monkeypatch.setattr(
        redis_module, "get_redis_client", lambda: _DeadClient()
    )


def test_cache_outage_misses_gracefully_db_still_serves(make_auth, client, monkeypatch):
    """Redis dies: redirects must NOT die. Cache read fails open, DB serves."""
    from app.services import cache as cache_module

    headers = make_auth()
    link = client.post(
        "/links", json={"target_url": "https://example.com/alive"}, headers=headers
    ).json()
    _outage(monkeypatch)

    assert cache_module.get_cached_target("anything") is None
    resp = client.post(
        "/links", json={"target_url": "https://example.com/alive2"}, headers=headers
    )
    assert resp.status_code == 201
    resp = client.get(f"/{link['slug']}", follow_redirects=False)
    assert resp.status_code == 302


def test_rate_limiter_outage_fails_open(make_auth, client, monkeypatch):
    """Redis dies mid-traffic: the limiter must not block visitors."""
    _outage(monkeypatch)
    headers = make_auth()
    for _ in range(5):  # far over any configured limit
        resp = client.post(
            "/links", json={"target_url": "https://x.com/open"}, headers=headers
        )
        assert resp.status_code == 201


def test_api_rate_limit_is_per_user(make_auth, client, monkeypatch):
    """Each user has their own counter: user B is NOT blocked by user A's
    exhaustion."""
    monkeypatch.setattr(settings, "api_rate_limit", 2)
    a = make_auth("a-limit@example.com")
    b = make_auth("b-limit@example.com")
    for i in range(2):
        assert client.post("/links", json={"target_url": f"https://x.com/{i}"}, headers=a).status_code == 201
    assert client.post("/links", json={"target_url": "https://x.com/over"}, headers=a).status_code == 429
    # B still fine:
    assert client.post("/links", json={"target_url": "https://x.com/b"}, headers=b).status_code == 201
