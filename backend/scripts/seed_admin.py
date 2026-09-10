"""Seed the first admin user.

Usage: venv/bin/python scripts/seed_admin.py <email> <password>
"""

import asyncio
import sys

sys.path.insert(0, ".")

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.modules.admin_auth.service import admin_auth_service  # noqa: E402


async def main(email: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = await admin_auth_service.get_by_email(db, email)
        if existing is not None:
            print(f"Admin '{email}' already exists (id={existing.id}) — nothing to do.")
            return
        admin = await admin_auth_service.create_admin(db, email, password)
        print(f"Created admin '{admin.email}' (id={admin.id})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: seed_admin.py <email> <password>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
