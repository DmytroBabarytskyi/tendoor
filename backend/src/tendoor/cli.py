"""Адміністративні команди.

  python -m tendoor.cli create-user --email admin@example.com --name "Адміністратор" --role admin

Пароль запитується інтерактивно (або береться з TENDOOR_NEW_PASSWORD), щоб не лишатися в історії shell.
"""

import argparse
import asyncio
import getpass
import os
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError

from tendoor.config import get_settings
from tendoor.infra.container import Container
from tendoor.services.users import ROLES, UserError


async def create_user(email: str, name: str, role: str, password: str) -> int:
    try:
        email = TypeAdapter(EmailStr).validate_python(email)  # та сама перевірка, що й в API
    except ValidationError:
        print(f"Помилка: некоректний email {email!r}", file=sys.stderr)
        return 1
    c = Container.build(get_settings())
    try:
        user = await c.user_service.create(None, email, name, role, password)
        print(f"Створено користувача #{user.id} {user.email} з роллю {user.role}")
        return 0
    except UserError as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 1
    finally:
        await c.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="tendoor.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    cu = sub.add_parser("create-user", help="створити користувача")
    cu.add_argument("--email", required=True)
    cu.add_argument("--name", required=True)
    cu.add_argument("--role", choices=ROLES, default="admin")
    args = parser.parse_args()

    password = os.environ.get("TENDOOR_NEW_PASSWORD") or getpass.getpass("Пароль: ")
    sys.exit(asyncio.run(create_user(args.email, args.name, args.role, password)))


if __name__ == "__main__":
    main()
