import argparse
import getpass
import json
import os
import re

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User, UserRole
from app.schemas.user import USERNAME_PATTERN


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the initial blue-music super administrator."
    )
    parser.add_argument(
        "--username",
        help="Login username. Defaults to INITIAL_SUPERADMIN_USERNAME or a prompt.",
    )
    return parser.parse_args()


def _username(argument: str | None) -> str:
    username = (
        argument
        or os.getenv("INITIAL_SUPERADMIN_USERNAME")
        or input("Super administrator username: ")
    ).strip().lower()
    if not 3 <= len(username) <= 50 or re.fullmatch(
        USERNAME_PATTERN, username
    ) is None:
        raise ValueError(
            "Username must be 3-50 characters using letters, numbers, "
            "dot, underscore, or hyphen"
        )
    return username


def _password() -> str:
    environment_password = os.getenv("INITIAL_SUPERADMIN_PASSWORD")
    if environment_password:
        password = environment_password
    else:
        password = getpass.getpass("Super administrator password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise ValueError("Password confirmation does not match")

    if not 8 <= len(password) <= 128:
        raise ValueError("Password must contain 8-128 characters")
    return password


def create_superadmin(username: str, password: str) -> dict[str, object]:
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.username == username))
        if existing is not None:
            if existing.role == UserRole.SUPER_ADMIN:
                return {
                    "status": "exists",
                    "user_id": existing.id,
                    "username": existing.username,
                }
            raise ValueError(
                "Username already belongs to a member account; refusing to elevate it"
            )

        user = User(
            username=username,
            password_hash=hash_password(password),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            "status": "created",
            "user_id": user.id,
            "username": user.username,
        }


def main() -> int:
    try:
        result = create_superadmin(_username(_arguments().username), _password())
    except ValueError as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
