from sqlalchemy import select

from app.auth.models import User
from app.auth.password_reset import RECOVERY_KEY_HASH
from app.core.config import get_settings
from app.core.security import decode_session_token
from app.main import settings as app_settings
from app.settings.models import CoreSetting


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


def test_recovery_key_resets_password_through_the_site(authenticated_client, core_db):
    old_cookie = authenticated_client.cookies.get("mlib_session")
    issued = authenticated_client.post(
        "/api/auth/me/recovery-key",
        json={"current_password": "correct-horse-battery-staple"},
    )

    assert issued.status_code == 200
    assert issued.headers["cache-control"] == "no-store"
    recovery_key = issued.json()["recovery_key"]
    stored = core_db.get(CoreSetting, RECOVERY_KEY_HASH)
    assert stored is not None
    core_db.refresh(stored)
    assert stored.value != recovery_key
    assert recovery_key not in stored.value

    authenticated_client.cookies.clear()
    recovered = authenticated_client.post(
        "/api/auth/password/recover",
        json={
            "recovery_key": recovery_key.lower().replace("-", " "),
            "new_password": "моя новая надёжная парольная фраза",
            "new_password_confirmation": "моя новая надёжная парольная фраза",
        },
    )

    assert recovered.status_code == 200
    assert recovered.headers["cache-control"] == "no-store"
    assert recovered.json()["username"] == "owner"
    assert authenticated_client.get("/api/auth/me").status_code == 200

    authenticated_client.cookies.clear()
    authenticated_client.cookies.set("mlib_session", old_cookie)
    assert authenticated_client.get("/api/auth/me").status_code == 401
    authenticated_client.cookies.clear()
    assert authenticated_client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "correct-horse-battery-staple"},
    ).status_code == 401
    assert authenticated_client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "моя новая надёжная парольная фраза"},
    ).status_code == 200

    authenticated_client.post("/api/auth/logout")
    reused = authenticated_client.post(
        "/api/auth/password/recover",
        json={
            "recovery_key": recovery_key,
            "new_password": "ещё одна длинная парольная фраза",
            "new_password_confirmation": "ещё одна длинная парольная фраза",
        },
    )
    assert reused.status_code == 400
    assert reused.json()["detail"] == "Ключ восстановления недействителен"


def test_recovery_key_attempts_are_rate_limited(authenticated_client):
    authenticated_client.post(
        "/api/auth/me/recovery-key",
        json={"current_password": "correct-horse-battery-staple"},
    )
    authenticated_client.post("/api/auth/logout")
    payload = {
        "recovery_key": "MLIB-WRONG-RECOVERY-KEY",
        "new_password": "моя новая надёжная парольная фраза",
        "new_password_confirmation": "моя новая надёжная парольная фраза",
    }

    responses = [authenticated_client.post("/api/auth/password/recover", json=payload) for _ in range(5)]

    assert [response.status_code for response in responses] == [400, 400, 400, 400, 429]
    assert responses[-1].headers["retry-after"] == "900"


def test_desktop_password_reset_requires_the_private_desktop_channel(
    authenticated_client,
    monkeypatch,
):
    monkeypatch.setattr(app_settings, "app_mode", "desktop")
    monkeypatch.setattr(app_settings, "desktop_token", "private-desktop-token")
    old_cookie = authenticated_client.cookies.get("mlib_session")
    payload = {
        "new_password": "новый пароль только для приложения",
        "new_password_confirmation": "новый пароль только для приложения",
    }

    assert authenticated_client.post("/desktop/password-reset", json=payload).status_code == 403
    response = authenticated_client.post(
        "/desktop/password-reset",
        json=payload,
        headers={"X-mLib-Desktop-Token": "private-desktop-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"username": "owner"}
    authenticated_client.cookies.clear()
    authenticated_client.cookies.set("mlib_session", old_cookie)
    assert authenticated_client.get("/api/auth/me").status_code == 401
    authenticated_client.cookies.clear()
    assert authenticated_client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "новый пароль только для приложения"},
    ).status_code == 200


def test_desktop_password_reset_is_hidden_in_server_mode(authenticated_client):
    response = authenticated_client.post(
        "/desktop/password-reset",
        json={
            "new_password": "новый пароль только для приложения",
            "new_password_confirmation": "новый пароль только для приложения",
        },
        headers={"X-mLib-Desktop-Token": "anything"},
    )
    assert response.status_code == 404
