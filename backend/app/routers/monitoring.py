import asyncio
import base64
import os
import cv2
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from jose import jwt
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import SECRET_KEY, ALGORITHM, EVIDENCE_DIR
from backend.app.core.database import get_db, AsyncSessionLocal
from backend.app.core.security import require_invigilator, get_assigned_room, get_current_user
from backend.app.models.models import User, UserRole, ExamRoom, Camera, ViolationEvent, ExamSession, ExamStatus, StudentTrack
from backend.app.schemas.schemas import (
    ExamRoomOut,
    CameraOut,
    ViolationEventOut,
    RoomMonitoringSummary,
    AIEventCreate,
    AIStatusSync,
)
from backend.app.routers.ws import manager

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# In-memory store of latest frames per room
_latest_frames: Dict[int, bytes] = {}
_latest_tracks: Dict[int, list] = {}

def get_standby_frame(room_name: str) -> bytes:
    """Generate a clean placeholder frame when camera stream is idle or waiting."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (24, 24, 34)  # Dark slate background
    # Header box
    cv2.rectangle(img, (0, 0), (640, 60), (35, 35, 50), -1)
    cv2.putText(img, f"SMART EXAM - {room_name.upper()}", (30, 40), cv2.FONT_HERSHEY_DUPLEX, 0.75, (0, 200, 255), 2)
    
    # Body text
    cv2.putText(img, "Camera feed standby", (160, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 220, 220), 2)
    cv2.putText(img, "Waiting for video input from AI pipeline...", (110, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
    
    # Timestamp footer
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    cv2.putText(img, now_str, (30, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 120), 1)
    
    ret, jpeg = cv2.imencode(".jpg", img)
    return jpeg.tobytes()

@router.get("/my-room", response_model=ExamRoomOut)
async def get_my_room(
    room: ExamRoom = Depends(get_assigned_room),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details of the room assigned to the current invigilator."""
    result = await db.execute(
        select(ExamRoom)
        .options(selectinload(ExamRoom.cameras), selectinload(ExamRoom.invigilators))
        .where(ExamRoom.id == room.id)
    )
    full_room = result.scalars().first()
    cameras = [CameraOut.model_validate(c) for c in full_room.cameras]
    return ExamRoomOut(
        id=full_room.id,
        name=full_room.name,
        building=full_room.building,
        capacity=full_room.capacity or 30,
        cameras=cameras,
        invigilator_count=len(full_room.invigilators)
    )

@router.get("/cameras", response_model=List[CameraOut])
async def get_my_room_cameras(
    room: ExamRoom = Depends(get_assigned_room),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve cameras strictly belonging to the assigned room."""
    result = await db.execute(select(Camera).where(Camera.room_id == room.id))
    cameras = result.scalars().all()
    return [CameraOut.model_validate(c) for c in cameras]

@router.get("/events", response_model=List[ViolationEventOut])
async def get_my_room_events(
    limit: int = 50,
    room: ExamRoom = Depends(get_assigned_room),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve violation events strictly belonging to the assigned room."""
    result = await db.execute(
        select(ViolationEvent)
        .where(ViolationEvent.room_id == room.id)
        .order_by(ViolationEvent.timestamp.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    outs = []
    for ev in events:
        evidence_url = f"/api/events/evidence/{ev.evidence_path}" if ev.evidence_path else None
        outs.append(ViolationEventOut(
            id=ev.id,
            room_id=ev.room_id,
            camera_id=ev.camera_id,
            track_id=ev.track_id,
            event_type=ev.event_type,
            points=ev.points,
            is_violence=ev.is_violence,
            severity=ev.severity or "medium",
            evidence_url=evidence_url,
            timestamp=ev.timestamp
        ))
    return outs

@router.get("/summary", response_model=RoomMonitoringSummary)
async def get_my_room_summary(
    room: ExamRoom = Depends(get_assigned_room),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate real database aggregates strictly for the assigned exam room.
    No mock data. Honest status for violence detection.
    """
    # 1. Total violations count
    total_violations = (await db.execute(
        select(func.count(ViolationEvent.id)).where(ViolationEvent.room_id == room.id)
    )).scalar() or 0

    # 2. Distinct suspicious students count (students with violations in this room)
    suspicious_count = (await db.execute(
        select(func.count(distinct(ViolationEvent.track_id)))
        .where(ViolationEvent.room_id == room.id, ViolationEvent.track_id != None)
    )).scalar() or 0

    # 3. Total students: check active AI tracks or distinct students
    active_tracks = _latest_tracks.get(room.id, [])
    active_track_count = len(active_tracks)
    # If no active live tracks, use distinct tracks from events
    total_students = active_track_count if active_track_count > 0 else suspicious_count

    # 4. Check if any camera in room is online
    camera_online_count = (await db.execute(
        select(func.count(Camera.id)).where(Camera.room_id == room.id, Camera.is_online == True)
    )).scalar() or 0
    camera_online = camera_online_count > 0 or (room.id in _latest_frames)

    # 5. Check if active session is paused
    session = (await db.execute(
        select(ExamSession)
        .where(ExamSession.room_id == room.id, ExamSession.status != ExamStatus.COMPLETED)
        .order_by(ExamSession.created_at.desc())
    )).scalars().first()
    is_paused = (session.status == ExamStatus.PAUSED) if session else False

    return RoomMonitoringSummary(
        room_id=room.id,
        room_name=room.name,
        building=room.building,
        total_students=total_students,
        suspicious_students=suspicious_count,
        total_violations=total_violations,
        violence_detection_status="unavailable",  # Honest status: not implemented
        camera_online=camera_online,
        is_paused=is_paused,
    )

async def _authenticate_feed_token(token: Optional[str]) -> ExamRoom:
    """Validate token from query parameter or header for video feed."""
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required for video feed")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid video feed token")

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalars().first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
        if user.role != UserRole.INVIGILATOR or not user.assigned_room_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No room assigned or unauthorized role")
        
        room = (await db.execute(select(ExamRoom).where(ExamRoom.id == user.assigned_room_id))).scalars().first()
        if not room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
        return room

@router.get("/video-feed")
async def video_feed(token: Optional[str] = Query(None)):
    """
    Authenticated MJPEG video stream strictly for the invigilator's assigned room.
    """
    room = await _authenticate_feed_token(token)
    room_id = room.id
    room_name = room.name

    async def frame_stream():
        while True:
            frame_bytes = _latest_frames.get(room_id)
            if not frame_bytes:
                frame_bytes = get_standby_frame(room_name)
            boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
            yield boundary + frame_bytes + b"\r\n"
            await asyncio.sleep(0.08)  # ~12 FPS

    return StreamingResponse(
        frame_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

# Endpoints for AI pipeline to feed live data
@router.post("/ai/frame", status_code=status.HTTP_200_OK)
async def push_ai_frame(
    request: Request,
    room_id: int = Query(...),
):
    """Endpoint for AI pipeline to push annotated JPEG frame for an exam room."""
    body = await request.body()
    if body:
        _latest_frames[room_id] = body
    return {"ok": True, "room_id": room_id}

@router.post("/ai/event", status_code=status.HTTP_201_CREATED)
async def push_ai_event(
    payload: AIEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint for AI pipeline to record violation event and broadcast to assigned room WebSocket."""
    # Ensure room exists
    room = (await db.execute(select(ExamRoom).where(ExamRoom.id == payload.room_id))).scalars().first()
    if not room:
        raise HTTPException(status_code=400, detail=f"Exam room {payload.room_id} not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    evidence_filename = None

    if payload.evidence_base64:
        try:
            ts_str = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
            evidence_filename = f"room{payload.room_id}_{payload.event_type}_track{payload.track_id}_{ts_str}.jpg"
            file_path = Path(EVIDENCE_DIR) / evidence_filename
            with open(file_path, "wb") as f:
                f.write(base64.b64decode(payload.evidence_base64))
        except Exception as e:
            pass

    event = ViolationEvent(
        room_id=payload.room_id,
        camera_id=payload.camera_id,
        track_id=payload.track_id,
        event_type=payload.event_type,
        points=payload.points,
        severity=payload.severity or "medium",
        is_violence=payload.is_violence or False,
        evidence_path=evidence_filename,
        timestamp=now
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    evidence_url = f"/api/events/evidence/{evidence_filename}" if evidence_filename else None
    
    # Broadcast strictly to room listeners
    ws_payload = {
        "type": "violation_event",
        "data": {
            "id": event.id,
            "room_id": payload.room_id,
            "track_id": payload.track_id,
            "event_type": event.event_type,
            "points": event.points,
            "severity": event.severity,
            "is_violence": event.is_violence,
            "evidence_url": evidence_url,
            "timestamp": now.strftime("%H:%M:%S"),
        }
    }
    await manager.broadcast_to_room(payload.room_id, ws_payload)

    return {"ok": True, "event_id": event.id}

@router.post("/ai/sync")
async def push_ai_sync(payload: AIStatusSync):
    """AI pushes live tracking states (boxes, head yaw/pitch, gaze direction)."""
    _latest_tracks[payload.room_id] = [t.model_dump() for t in payload.tracks]
    
    ws_payload = {
        "type": "status_sync",
        "data": {
            "room_id": payload.room_id,
            "live_student_count": payload.live_student_count,
            "fps": payload.fps,
            "tracks": _latest_tracks[payload.room_id]
        }
    }
    await manager.broadcast_to_room(payload.room_id, ws_payload)
    return {"ok": True}
