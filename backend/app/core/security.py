import base64
import hashlib
import hmac
import json
import secrets
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_password_hasher = PasswordHasher()


@dataclass(frozen=True)
class SessionIdentity:
    user_id: str
    version: int


def normalize_password(password: str) -> str:
    return unicodedata.normalize("NFC", password)


def hash_password(password: str) -> str:
    return _password_hasher.hash(normalize_password(password))


def verify_password(password: str, encoded: str) -> bool:
    normalized = normalize_password(password)
    try:
        return _password_hasher.verify(encoded, normalized)
    except (VerifyMismatchError, InvalidHashError):
        if normalized == password:
            return False
        try:
            # Compatibility for passwords stored before Unicode NFC normalization was introduced.
            return _password_hasher.verify(encoded, password)
        except (VerifyMismatchError, InvalidHashError):
            return False


def password_needs_rehash(encoded: str) -> bool:
    try:
        return _password_hasher.check_needs_rehash(encoded)
    except InvalidHashError:
        return True


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode_b64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_session_token(user_id: str, secret_key: str, ttl_hours: int, version: int = 0) -> str:
    now = datetime.now(UTC)
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {
                "sub": user_id,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
                "jti": secrets.token_urlsafe(12),
                "ver": version,
            },
            separators=(",", ":"),
        ).encode()
    )
    signature = _b64url(hmac.new(secret_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_session_token(token: str, secret_key: str) -> SessionIdentity | None:
    try:
        encoded_header, payload, signature = token.split(".")
        header = json.loads(_decode_b64url(encoded_header))
        if header != {"alg": "HS256", "typ": "JWT"}:
            return None
        expected = _b64url(
            hmac.new(secret_key.encode(), f"{encoded_header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_decode_b64url(payload))
        now = int(time.time())
        if int(claims["exp"]) <= now or int(claims["iat"]) > now + 60:
            return None
        user_id = str(claims["sub"])
        if not user_id:
            return None
        return SessionIdentity(user_id=user_id, version=int(claims.get("ver", 0)))
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def utcnow() -> datetime:
    return datetime.now(UTC)
