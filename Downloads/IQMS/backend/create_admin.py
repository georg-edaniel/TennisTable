import asyncio, sys, os
os.environ["USE_SQLITE"] = "true"
sys.path.insert(0, ".")

from core.database import get_db, create_tables
from core.security import hash_password
from models.user import User
from sqlalchemy import select

async def main():
    await create_tables()
    async for db in get_db():
        result = await db.execute(select(User).where(User.username == "admin"))
        existing = result.scalar_one_or_none()
        if existing:
            existing.hashed_password = hash_password("Admin1234!")
            existing.is_admin = True
            existing.is_active = True
            await db.commit()
            print(f"Mot de passe admin réinitialisé (id={existing.id})")
            break
        user = User(
            username="admin",
            email="admin@aqims.local",
            hashed_password=hash_password("Admin1234!"),
            is_admin=True,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"Admin créé : {user.username} (id={user.id})")
        break

asyncio.run(main())
