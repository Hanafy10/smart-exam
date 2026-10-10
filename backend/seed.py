import asyncio
from sqlalchemy import select
from backend.app.core.database import AsyncSessionLocal, init_db
from backend.app.core.security import get_password_hash
from backend.app.models.models import User, UserRole, ExamRoom, Camera

async def seed_default_admin():
    async with AsyncSessionLocal() as session:
        # 1. Seed initial admin
        query = select(User).where(User.username == "admin")
        existing = (await session.execute(query)).scalars().first()
        if not existing:
            admin_user = User(
                username="admin",
                email="admin@smartexam.edu",
                hashed_password=get_password_hash("Admin@12345678"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin_user)
            await session.commit()
            print("[Seed] Created default admin account: admin / Admin@12345678")
        else:
            print("[Seed] Admin user already exists.")

        # 2. Seed initial exam room if none exist
        room_query = select(ExamRoom)
        first_room = (await session.execute(room_query)).scalars().first()
        if not first_room:
            default_room = ExamRoom(
                name="Hall 101",
                building="Engineering Complex A",
                capacity=40,
            )
            session.add(default_room)
            await session.commit()
            await session.refresh(default_room)

            default_camera = Camera(
                room_id=default_room.id,
                name="Ceiling Overhead Cam 1",
                device_index_or_url="0",
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
