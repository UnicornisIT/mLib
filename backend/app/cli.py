import argparse
import getpass

from sqlalchemy import func, select

from app.auth.models import User
from app.auth.password_reset import PasswordResetError, reset_user_password
from app.database.session import CoreSessionLocal


def reset_password() -> int:
    with CoreSessionLocal() as db:
        users = list(
            db.scalars(
                select(User)
                .where(User.is_admin.is_(True), User.is_active.is_(True))
                .order_by(User.created_at.asc())
            )
        )
        if not users:
            print("Профиль администратора ещё не создан.")
            return 1

        user = users[0]
        if len(users) > 1:
            username = input("Имя пользователя: ").strip()
            user = db.scalar(
                select(User).where(
                    func.lower(User.username) == username.casefold(),
                    User.is_admin.is_(True),
                    User.is_active.is_(True),
                )
            )
            if user is None:
                print("Активный администратор с таким именем не найден.")
                return 1

        print(f"Сброс пароля для {user.username}")
        new_password = getpass.getpass("Новый пароль: ")
        confirmation = getpass.getpass("Повторите новый пароль: ")
        try:
            reset_user_password(db, user, new_password, confirmation)
        except PasswordResetError as exc:
            print(str(exc))
            return 1

    print("Пароль изменён. Все прежние сеансы завершены.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("reset-password", help="безопасно сбросить пароль администратора")
    arguments = parser.parse_args()
    if arguments.command == "reset-password":
        return reset_password()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
