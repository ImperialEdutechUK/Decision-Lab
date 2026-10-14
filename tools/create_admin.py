"""Create or update the first administrator.

    python -m tools.create_admin                     # uses ADMIN_EMAIL / ADMIN_PASSWORD from .env
    python -m tools.create_admin admin@org.com pw "Name"
"""
import sys

from database.init_db import init_db
from services.admin_service import create_or_update_admin
from config import config


def main():
    init_db()
    email = sys.argv[1] if len(sys.argv) > 1 else config.ADMIN_EMAIL
    password = sys.argv[2] if len(sys.argv) > 2 else config.ADMIN_PASSWORD
    name = sys.argv[3] if len(sys.argv) > 3 else "Administrator"
    if not email or not password:
        print("Set ADMIN_EMAIL and ADMIN_PASSWORD in .env, or pass them as arguments.")
        sys.exit(1)
    admin = create_or_update_admin(email, password, name)
    print(f"Admin ready: {admin['email']} (id {admin['id']})")


if __name__ == "__main__":
    main()
