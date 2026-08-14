from sqlalchemy import select

from app.auth.models import User
from app.core.config import get_settings
from app.core.security import decode_session_token


def test_first_run_setup_and_cookie_auth(client, core_db):
    assert client.get("/api/auth/status").json() == {"setup_required": True, "authenticated": False}

    response = client.post("/api/auth/setup", json={"username": "owner", "password": "a-strong-password"})
    assert response.status_code == 201
    assert response.json()["username"] == "owner"
    assert "mlib_session" in response.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    user = core_db.scalar(select(User).where(User.username == "owner"))
    assert user is not None
    assert user.password_hash != "a-strong-password"
    assert user.password_hash.startswith("$argon2")


def test_login_rejects_wrong_password(client):
    client.post("/api/auth/setup", json={"username": "owner", "password": "a-strong-password"})
    client.post("/api/auth/logout")
    response = client.post("/api/auth/login", json={"username": "owner", "password": "wrong-password"})
    assert response.status_code == 401


def test_user_can_update_shared_profile(authenticated_client, core_db):
    response = authenticated_client.patch(
        "/api/auth/me",
        json={
            "display_name": "  Алексей  ",
            "bio": "Музыка, кино и хорошие истории.",
            "location": "Москва",
            "birth_date": "1990-05-12",
            "avatar_color": "#5b6ee1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        **response.json(),
        "display_name": "Алексей",
        "bio": "Музыка, кино и хорошие истории.",
        "location": "Москва",
        "birth_date": "1990-05-12",
        "avatar_color": "#5b6ee1",
    }
    user = core_db.scalar(select(User).where(User.username == "owner"))
    assert user is not None
    core_db.refresh(user)
    assert user.display_name == "Алексей"


def test_user_can_clear_optional_profile_fields(authenticated_client):
    authenticated_client.patch("/api/auth/me", json={"display_name": "Алексей", "bio": "Описание"})
    response = authenticated_client.patch("/api/auth/me", json={"display_name": "  ", "bio": ""})

    assert response.status_code == 200
    assert response.json()["display_name"] is None
    assert response.json()["bio"] is None


def test_password_change_requires_current_password(authenticated_client, core_db):
    response = authenticated_client.put(
        "/api/auth/me/password",
        json={
            "current_password": "incorrect-current-password",
            "new_password": "a-new-secure-passphrase",
            "new_password_confirmation": "a-new-secure-passphrase",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Текущий пароль указан неверно"
    user = core_db.scalar(select(User).where(User.username == "owner"))
    assert user is not None
    core_db.refresh(user)
    assert user.password_change_failures == 1


def test_password_change_enforces_modern_policy(authenticated_client):
    mismatched = authenticated_client.put(
        "/api/auth/me/password",
        json={
            "current_password": "correct-horse-battery-staple",
            "new_password": "a-long-enough-password",
            "new_password_confirmation": "a-different-password",
        },
    )
    assert mismatched.status_code == 422
    assert mismatched.json()["detail"] == "Новые пароли не совпадают"

    common = authenticated_client.put(
        "/api/auth/me/password",
        json={
            "current_password": "correct-horse-battery-staple",
            "new_password": "passwordpassword",
            "new_password_confirmation": "passwordpassword",
        },
    )
    assert common.status_code == 422
    assert "легко угадывается" in common.json()["detail"]


def test_password_change_revokes_old_sessions_and_renews_current_one(authenticated_client):
    old_cookie = authenticated_client.cookies.get("mlib_session")
    assert old_cookie

    response = authenticated_client.put(
        "/api/auth/me/password",
        json={
            "current_password": "correct-horse-battery-staple",
            "new_password": "моя новая длинная парольная фраза",
            "new_password_confirmation": "моя новая длинная парольная фраза",
        },
    )

    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    new_cookie = authenticated_client.cookies.get("mlib_session")
    assert new_cookie and new_cookie != old_cookie
    settings = get_settings()
    old_identity = decode_session_token(old_cookie, settings.secret_key)
    new_identity = decode_session_token(new_cookie, settings.secret_key)
    assert old_identity and new_identity
    assert new_identity.version == old_identity.version + 1
    assert authenticated_client.get("/api/auth/me").status_code == 200

    authenticated_client.cookies.clear()
    authenticated_client.cookies.set("mlib_session", old_cookie)
    assert authenticated_client.get("/api/auth/me").status_code == 401
    authenticated_client.cookies.clear()
    authenticated_client.cookies.set("mlib_session", new_cookie)
    assert authenticated_client.get("/api/auth/me").status_code == 200

    authenticated_client.post("/api/auth/logout")
    old_login = authenticated_client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "correct-horse-battery-staple"},
    )
    assert old_login.status_code == 401
    new_login = authenticated_client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "моя новая длинная парольная фраза"},
    )
    assert new_login.status_code == 200


def test_password_change_is_rate_limited(authenticated_client):
    payload = {
        "current_password": "wrong-current-password",
        "new_password": "a-new-secure-passphrase",
        "new_password_confirmation": "a-new-secure-passphrase",
    }
    responses = [authenticated_client.put("/api/auth/me/password", json=payload) for _ in range(5)]

    assert [response.status_code for response in responses] == [400, 400, 400, 400, 429]
    assert responses[-1].headers["retry-after"] == "900"
