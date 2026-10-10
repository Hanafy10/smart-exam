from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import require_admin, get_password_hash, validate_password_strength
from backend.app.models.models import User, UserRole, ExamRoom, Camera
from backend.app.schemas.schemas import (
    ExamRoomCreate,
    ExamRoomOut,
    InvigilatorCreate,
    InvigilatorUpdate,
    InvigilatorOut,
    CameraCreate,
    CameraOut,
)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

@router.get("/rooms", response_model=List[ExamRoomOut])
async def list_rooms(db: AsyncSession = Depends(get_db)):
    """List all exam rooms with camera count and assigned invigilator count."""
    result = await db.execute(
        select(ExamRoom).options(selectinload(ExamRoom.cameras), selectinload(ExamRoom.invigilators))
    )
    rooms = result.scalars().all()
    
    room_outs = []
    for r in rooms:
        c_outs = [CameraOut.model_validate(c) for c in r.cameras]
        room_outs.append(ExamRoomOut(
            id=r.id,
            name=r.name,
            building=r.building,
            capacity=r.capacity or 30,
            cameras=c_outs,
            invigilator_count=len(r.invigilators)
        ))
    return room_outs

@router.post("/rooms", response_model=ExamRoomOut, status_code=status.HTTP_201_CREATED)
async def create_room(payload: ExamRoomCreate, db: AsyncSession = Depends(get_db)):
    """Create a new exam room."""
    existing = (await db.execute(select(ExamRoom).where(ExamRoom.name == payload.name))).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="Exam room with this name already exists")
    
    room = ExamRoom(
        name=payload.name,
        building=payload.building,
        capacity=payload.capacity or 30
    )
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return ExamRoomOut(
        id=room.id,
        name=room.name,
        building=room.building,
        capacity=room.capacity,
        cameras=[],
        invigilator_count=0
    )

@router.post("/rooms/{room_id}/cameras", response_model=CameraOut, status_code=status.HTTP_201_CREATED)
async def create_camera_for_room(room_id: int, payload: CameraCreate, db: AsyncSession = Depends(get_db)):
    """Attach a camera to an exam room."""
    room = (await db.execute(select(ExamRoom).where(ExamRoom.id == room_id))).scalars().first()
    if not room:
        raise HTTPException(status_code=404, detail="Exam room not found")
    
    camera = Camera(
        room_id=room_id,
        name=payload.name,
        device_index_or_url=payload.device_index_or_url,
        is_online=True
    )
    db.add(camera)
    await db.commit()
    await db.refresh(camera)
    return CameraOut.model_validate(camera)

@router.get("/invigilators", response_model=List[InvigilatorOut])
async def list_invigilators(db: AsyncSession = Depends(get_db)):
    """List all invigilator accounts and their assigned room."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.assigned_room))
        .where(User.role == UserRole.INVIGILATOR)
        .order_by(User.created_at.desc())
    )
    invigilators = result.scalars().all()
    
    res = []
    for inv in invigilators:
        res.append(InvigilatorOut(
            id=inv.id,
            username=inv.username,
            email=inv.email,
            role=inv.role.value if hasattr(inv.role, "value") else str(inv.role),
            is_active=inv.is_active,
            assigned_room_id=inv.assigned_room_id,
            assigned_room_name=inv.assigned_room.name if inv.assigned_room else None,
            created_at=inv.created_at
        ))
    return res

@router.post("/invigilators", response_model=InvigilatorOut, status_code=status.HTTP_201_CREATED)
async def create_invigilator(payload: InvigilatorCreate, db: AsyncSession = Depends(get_db)):
    """Create a new invigilator account strictly assigned to an exam room."""
    try:
        validate_password_strength(payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Check if username exists
    existing_user = (await db.execute(select(User).where(User.username == payload.username))).scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Check if room exists
    room = (await db.execute(select(ExamRoom).where(ExamRoom.id == payload.assigned_room_id))).scalars().first()
    if not room:
        raise HTTPException(status_code=400, detail="Assigned exam room does not exist")
    
    hashed_password = get_password_hash(payload.password)
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hashed_password,
        role=UserRole.INVIGILATOR,
        is_active=True,
        assigned_room_id=payload.assigned_room_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return InvigilatorOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_active=user.is_active,
        assigned_room_id=user.assigned_room_id,
        assigned_room_name=room.name,
        created_at=user.created_at
    )

@router.get("/invigilators/{invigilator_id}", response_model=InvigilatorOut)
async def get_invigilator(invigilator_id: int, db: AsyncSession = Depends(get_db)):
    """Get single invigilator details."""
    result = await db.execute(
        select(User).options(selectinload(User.assigned_room)).where(User.id == invigilator_id, User.role == UserRole.INVIGILATOR)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Invigilator not found")
    
    return InvigilatorOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_active=user.is_active,
        assigned_room_id=user.assigned_room_id,
        assigned_room_name=user.assigned_room.name if user.assigned_room else None,
        created_at=user.created_at
    )

@router.patch("/invigilators/{invigilator_id}", response_model=InvigilatorOut)
async def update_invigilator(invigilator_id: int, payload: InvigilatorUpdate, db: AsyncSession = Depends(get_db)):
    """Update invigilator: activate/deactivate, reassign room, reset password."""
    result = await db.execute(
        select(User).options(selectinload(User.assigned_room)).where(User.id == invigilator_id, User.role == UserRole.INVIGILATOR)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Invigilator not found")
    
    if payload.is_active is not None:
        user.is_active = payload.is_active
    
    if payload.assigned_room_id is not None:
        room = (await db.execute(select(ExamRoom).where(ExamRoom.id == payload.assigned_room_id))).scalars().first()
        if not room:
            raise HTTPException(status_code=400, detail="Target exam room does not exist")
        user.assigned_room_id = payload.assigned_room_id
    
    if payload.password:
        try:
            validate_password_strength(payload.password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        user.hashed_password = get_password_hash(payload.password)
        user.refresh_token = None
        user.refresh_token_expires = None
        user.failed_login_attempts = 0
        user.locked_until = None
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    room_name = None
    if user.assigned_room_id:
        room = (await db.execute(select(ExamRoom).where(ExamRoom.id == user.assigned_room_id))).scalars().first()
        if room:
            room_name = room.name
            
    return InvigilatorOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        is_active=user.is_active,
        assigned_room_id=user.assigned_room_id,
        assigned_room_name=room_name,
        created_at=user.created_at
    )

@router.delete("/invigilators/{invigilator_id}")
async def delete_invigilator(invigilator_id: int, db: AsyncSession = Depends(get_db)):
    """Delete invigilator account."""
    result = await db.execute(
        select(User).where(User.id == invigilator_id, User.role == UserRole.INVIGILATOR)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="Invigilator not found")
    
    await db.delete(user)
    await db.commit()
    return {"message": "Invigilator deleted successfully"}
