"""
Run inside the api container to create an admin user:
  docker compose exec api python scripts/create_admin.py admin@example.com secretpassword
"""
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User


async def main(email: str, password: str) -> None:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        existing = await db.scalar(select(User).where(User.email == email))
        if existing:
            existing.is_admin = True
            existing.hashed_password = hash_password(password)
            await db.commit()
            print(f"Updated existing user {email} → admin=True")
        else:
            user = User(email=email, hashed_password=hash_password(password), is_admin=True)
            db.add(user)
            await db.commit()
            print(f"Created admin user: {email}")
    await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/create_admin.py <email> <password>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
