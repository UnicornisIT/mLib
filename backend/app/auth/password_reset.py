import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.password_policy import password_policy_error
from app.core.security import hash_password, normalize_password, utcnow, verify_password
from app.settings.models import CoreSetting

RECOVERY_KEY_HASH = "password_recovery_key_hash"
RECOVERY_FAILURES = "password_recovery_failures"
RECOVERY_LOCKED_UNTIL = "password_recovery_locked_until"
RECOVERY_MAX_FAILURES = 5
RECOVERY_LOCK_MINUTES = 15


class PasswordResetError(ValueError):
    """A user-facing validation error raised while replacing a password."""


class PasswordRecoveryError(ValueError):
    def __init__(self, message: str, retry_after: int = 0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def _set_setting(db: Session, key: str, value: str) -> None:
    setting = db.get(CoreSetting, key)
    if setting is None:
        db.add(CoreSetting(key=key, value=value))
    else:
        setting.value = value
        db.add(setting)


def _delete_settings(db: Session, *keys: str) -> None:
    for key in keys:
        setting = db.get(CoreSetting, key)
        if setting is not None:
            db.delete(setting)


def _normalize_recovery_key(value: str) -> str:
    return "".join(character for character in value.upper() if character not in {"-", " ", "\t", "\r", "\n"})


def _recovery_digest(value: str, secret_key: str) -> str:
    return hmac.new(
        secret_key.encode("utf-8"),
        _normalize_recovery_key(value).encode("ascii", errors="ignore"),
        hashlib.sha256,
    ).hexdigest()


def _seconds_until(value: str | None) -> int:
    if not value:
        return 0
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return 0
    comparable = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return max(0, int((comparable - utcnow()).total_seconds()) + 1)


def create_recovery_key(db: Session, secret_key: str) -> str:
    raw_key = secrets.token_hex(24).upper()
    formatted_key = "MLIB-" + "-".join(raw_key[index : index + 4] for index in range(0, len(raw_key), 4))
    _set_setting(db, RECOVERY_KEY_HASH, _recovery_digest(formatted_key, secret_key))
    _delete_settings(db, RECOVERY_FAILURES, RECOVERY_LOCKED_UNTIL)
    db.commit()
    return formatted_key


def verify_recovery_key(db: Session, recovery_key: str, secret_key: str) -> None:
    locked_setting = db.get(CoreSetting, RECOVERY_LOCKED_UNTIL)
    retry_after = _seconds_until(locked_setting.value if locked_setting else None)
    if retry_after:
        raise PasswordRecoveryError("Слишком много неудачных попыток. Повторите позже", retry_after)
    if locked_setting is not None:
        _delete_settings(db, RECOVERY_FAILURES, RECOVERY_LOCKED_UNTIL)

    stored = db.get(CoreSetting, RECOVERY_KEY_HASH)
    candidate = _recovery_digest(recovery_key, secret_key)
    if stored is not None and hmac.compare_digest(stored.value, candidate):
        return

    failures_setting = db.get(CoreSetting, RECOVERY_FAILURES)
    try:
        failures = int(failures_setting.value) + 1 if failures_setting else 1
    except ValueError:
        failures = 1
    _set_setting(db, RECOVERY_FAILURES, str(failures))
    if failures >= RECOVERY_MAX_FAILURES:
        locked_until = utcnow() + timedelta(minutes=RECOVERY_LOCK_MINUTES)
        _set_setting(db, RECOVERY_LOCKED_UNTIL, locked_until.isoformat())
    db.commit()
    if failures >= RECOVERY_MAX_FAILURES:
        raise PasswordRecoveryError(
            "Слишком много неудачных попыток. Повторите позже",
            RECOVERY_LOCK_MINUTES * 60,
        )
    raise PasswordRecoveryError("Ключ восстановления недействителен")


def revoke_recovery_key(db: Session) -> None:
    _delete_settings(db, RECOVERY_KEY_HASH, RECOVERY_FAILURES, RECOVERY_LOCKED_UNTIL)


def reset_user_password(
    db: Session,
    user: User,
    new_password: str,
    confirmation: str,
) -> None:
    if normalize_password(new_password) != normalize_password(confirmation):
        raise PasswordResetError("Новые пароли не совпадают")
    if policy_error := password_policy_error(new_password, user.username):
        raise PasswordResetError(policy_error)
    if verify_password(new_password, user.password_hash):
        raise PasswordResetError("Новый пароль должен отличаться от текущего")

    user.password_hash = hash_password(new_password)
    user.password_changed_at = utcnow()
    user.password_change_failures = 0
    user.password_change_locked_until = None
    user.session_version += 1
    revoke_recovery_key(db)
    db.add(user)
    db.commit()
    db.refresh(user)
