from sqlalchemy import select

from interview_api.auth import token_hash
from interview_api.db import _session_factory
from interview_api.models import AuthSession, User

from .conftest import signup


def test_signup_sets_httponly_cookie_and_me_works(client, settings):
    r = client.post(
        "/api/auth/signup",
        json={"email": "Asha@Example.com", "password": "correct horse 1", "name": " Asha "},
    )
    assert r.status_code == 201
    assert r.json()["email"] == "asha@example.com"  # stored lower-cased
    assert r.json()["name"] == "Asha"
    cookie = r.headers["set-cookie"]
    assert settings.session_cookie_name in cookie
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["email"] == "asha@example.com"


def test_password_is_argon2_hashed_and_token_stored_hashed(client, settings):
    signup(client)
    token = client.cookies.get(settings.session_cookie_name)
    with _session_factory()() as db:
        u = db.execute(select(User)).scalar_one()
        assert u.password_hash.startswith("$argon2id$")
        assert "correct horse 1" not in u.password_hash
        s = db.execute(select(AuthSession)).scalar_one()
        assert s.token_hash == token_hash(token)
        assert token not in s.token_hash


def test_duplicate_email_is_409(client):
    signup(client)
    r = client.post(
        "/api/auth/signup",
        json={"email": "ASHA@example.com", "password": "another pass", "name": "A"},
    )
    assert r.status_code == 409


def test_validation(client):
    assert (
        client.post(
            "/api/auth/signup", json={"email": "x@example.com", "password": "short", "name": "X"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/signup",
            json={"email": "not-an-email", "password": "long enough", "name": "X"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/auth/signup",
            json={"email": "x@example.com", "password": "long enough", "name": "X", "admin": True},
        ).status_code
        == 422
    )


def test_login_logout(client):
    signup(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    bad = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope"})
    assert bad.status_code == 401
    unknown = client.post("/api/auth/login", json={"email": "who@example.com", "password": "nope"})
    assert unknown.status_code == 401
    assert bad.json() == unknown.json()  # no hint whether the email exists

    ok = client.post(
        "/api/auth/login", json={"email": "ASHA@example.com", "password": "correct horse 1"}
    )
    assert ok.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_logout_deletes_server_side_session(client, settings):
    signup(client)
    token = client.cookies.get(settings.session_cookie_name)
    client.post("/api/auth/logout")
    client.cookies.set(settings.session_cookie_name, token)  # replaying the old cookie
    assert client.get("/api/auth/me").status_code == 401


def test_unauthenticated_endpoints_are_401(client):
    for method, path in [
        ("get", "/api/auth/me"),
        ("get", "/api/interviews"),
        ("post", "/api/interviews"),
        ("get", "/api/progress"),
    ]:
        assert getattr(client, method)(path).status_code == 401, path


def test_login_rate_limit(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "rate_logins_per_15min", 3)
    for _ in range(3):
        client.post("/api/auth/login", json={"email": "a@example.com", "password": "x"})
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "x"})
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0
