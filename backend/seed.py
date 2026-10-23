import asyncio
from sqlalchemy import select
from backend.app.core.config import (
    DEFAULT_ADMIN_USERNAME,
    DEFAULT_ADMIN_EMAIL,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ROOM_NAME,
    DEFAULT_ROOM_BUILDING,
    DEFAULT_ROOM_CAPACITY,
    DEFAULT_CAMERA_NAME,
    DEFAULT_CAMERA_DEVICE,
)
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.core.security import get_password_hash
from backend.app.models.models import User, UserRole, ExamRoom, Camera

async def seed_default_admin():
    async with AsyncSessionLocal() as session:
        # 1. Seed initial admin
        query = select(User).where(User.username == DEFAULT_ADMIN_USERNAME)
        existing = (await session.execute(query)).scalars().first()
        if not existing:
            admin_user = User(
                username=DEFAULT_ADMIN_USERNAME,
                email=DEFAULT_ADMIN_EMAIL,
                hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin_user)
            await session.commit()
            print(f"[Seed] Created default admin account: {DEFAULT_ADMIN_USERNAME}")
        else:
            print("[Seed] Admin user already exists.")

        # 2. Seed initial exam room if none exist
        room_query = select(ExamRoom)
        first_room = (await session.execute(room_query)).scalars().first()
        if not first_room:
            default_room = ExamRoom(
                name=DEFAULT_ROOM_NAME,
                building=DEFAULT_ROOM_BUILDING,
                capacity=DEFAULT_ROOM_CAPACITY,
            )
            session.add(default_room)
            await session.commit()
            await session.refresh(default_room)

            default_camera = Camera(
                room_id=default_room.id,
                name=DEFAULT_CAMERA_NAME,
                device_index_or_url=DEFAULT_CAMERA_DEVICE,
                is_online=True,
            )
            session.add(default_camera)
            await session.commit()
            print(f"[Seed] Created default exam room: {default_room.name} with camera {default_camera.name}")

if __name__ == "__main__":
    async def main():
        await init_db()
        await seed_default_admin()
    asyncio.run(main())
