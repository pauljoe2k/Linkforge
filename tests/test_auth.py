"""Day 2 auth endpoint tests: registration, login and /auth/me."""


def register(client, email, password="super-secret-pass-9"):
    return client.post(
        "/auth/register", json={"email": email, "password": password}
    )


def login(client, email, password="super-secret-pass-9"):
    return client.post("/auth/login", json={"email": email, "password": password})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# --- registration ----------------------------------------------------------


def test_register_happy_path(client):
    resp = register(client, "alice@example.com")
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "alice@example.com"
    assert body["id"] > 0
    assert "password" not in body          # never echo secrets
    assert "password_hash" not in body
    assert "created_at" in body


def test_register_email_is_normalized_to_lowercase(client):
    resp = register(client, "MiXeD@Example.COM")
    assert resp.status_code == 201
    assert resp.json()["email"] == "mixed@example.com"


def test_register_duplicate_email_409(client):
    assert register(client, "dup@example.com").status_code == 201
    resp = register(client, "dup@example.com")
    assert resp.status_code == 409
    assert "registered" in resp.json()["detail"].lower()


def test_register_duplicate_email_ignores_case(client):
    assert register(client, "caps@example.com").status_code == 201
    resp = register(client, "CAPS@EXAMPLE.COM")
    assert resp.status_code == 409


def test_register_four22_on_invalid_email(client):
    resp = register(client, "not-an-email", "long-enough-password-1")
    assert resp.status_code == 422


def test_register_four22_on_short_password(client):
    resp = register(client, "shortpw@example.com", "1234567")
    assert resp.status_code == 422


# --- login ------------------------------------------------------------------


def test_login_happy_path_returns_bearer_token(client):
    register(client, "login@example.com")
    resp = login(client, "login@example.com")
    body = resp.json()
    assert resp.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["access_token"].count(".") == 2   # header.payload.signature
    assert body["expires_in"] > 0


def test_login_is_case_insensitive_on_email(client):
    register(client, "upper@example.com")
    resp = login(client, "UPPER@EXAMPLE.COM")
    assert resp.status_code == 200


def test_login_wrong_password_401(client):
    register(client, "wp@example.com")
    resp = login(client, "wp@example.com", "definitely-wrong-pass-2")
    assert resp.status_code == 401


def test_login_unknown_email_401(client):
    resp = login(client, "ghost@example.com", "whatever-pass-12345")
    assert resp.status_code == 401


def test_login_error_identical_for_unknown_email_and_wrong_password(client):
    """Unknown email and wrong password must be indistinguishable."""
    register(client, "known@example.com")
    unknown = client.post(
        "/auth/login",
        json={"email": "unknown@example.com", "password": "whatever-pass-12345"},
    ).json()
    known = client.post(
        "/auth/login",
        json={"email": "known@example.com", "password": "whatever-pass-12345"},
    ).json()
    assert unknown == known


def test_login_four22_on_malformed_body(client):
    resp = client.post("/auth/login", json={"email": "bad"})
    assert resp.status_code == 422


# --- session identity (/auth/me) --------------------------------------------


def test_me_requires_bearer_token(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


def test_me_rejects_garbage_token(client):
    resp = client.get("/auth/me", headers=auth_header("not-a-jwt"))
    assert resp.status_code == 401


def test_me_rejects_forged_token(client):
    # Valid header/payload, bogus signature → signature check must fail.
    token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxIiwidHlwZSI6ImFjY2VzcyJ9.face!"
    )
    resp = client.get("/auth/me", headers=auth_header(token))
    assert resp.status_code == 401


def test_me_returns_current_user(client):
    register(client, "me-user@example.com")
    token = login(client, "me-user@example.com").json()["access_token"]
    resp = client.get("/auth/me", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["email"] == "me-user@example.com"
