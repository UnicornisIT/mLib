import re

from app.core.security import normalize_password

MIN_PASSWORD_LENGTH = 15
MAX_PASSWORD_LENGTH = 200

_COMMON_PASSWORDS = {
    "111111111111111",
    "123456789012345",
    "adminadminadmin",
    "administrator",
    "changemechangeme",
    "iloveyouiloveyou",
    "letmeinletmein",
    "passwordpassword",
    "password1234567",
    "qwertyqwertyqwerty",
    "qwertyuiopasdfg",
    "welcome123456789",
}


def password_policy_error(password: str, username: str | None = None) -> str | None:
    normalized = normalize_password(password)
    if len(normalized) < MIN_PASSWORD_LENGTH:
        return f"Новый пароль должен содержать не менее {MIN_PASSWORD_LENGTH} символов"
    if len(normalized) > MAX_PASSWORD_LENGTH:
        return f"Новый пароль не должен превышать {MAX_PASSWORD_LENGTH} символов"

    folded = normalized.casefold()
    context_passwords = {"mlib", "musiclib", "movielib"}
    if username:
        context_passwords.add(username.casefold())
    if folded in _COMMON_PASSWORDS or folded in context_passwords:
        return "Этот пароль слишком распространён или легко угадывается"
    if len(set(folded)) == 1:
        return "Пароль из одного повторяющегося символа слишком легко угадывается"
    if folded.isdigit() and (
        all(int(right) == (int(left) + 1) % 10 for left, right in zip(folded, folded[1:], strict=False))
        or all(int(right) == (int(left) - 1) % 10 for left, right in zip(folded, folded[1:], strict=False))
    ):
        return "Последовательность цифр слишком легко угадывается"
    if re.fullmatch(r"(.{1,5})\1{2,}", folded):
        return "Повторяющийся шаблон слишком легко угадывается"
    return None
