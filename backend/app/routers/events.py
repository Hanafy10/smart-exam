import os
import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import EVIDENCE_DIR
from backend.app.core.database import get_db
from backend.app.models.models import (
    Camera,
    ExamRoom,
    ExamSession,
    ExamStatus,
    StudentTrack,
    ViolationEvent,
)
from backend.app.schemas.schemas import AIEventCreate, AIStatusSync, ViolationEventOut
from backend.app.routers.monitoring import _latest_tracks
from backend.app.routers.ws import manager

router = APIRouter(prefix="/api/events", tags=["events"])


async def get_or_create_active_session(db: AsyncSession, room: ExamRoom) -> ExamSession:
    query = (
        select(ExamSession)
        .where(
            ExamSession.room_id == room.id,
            ExamSession.status != ExamStatus.COMPLETED,
        )
        .order_by(ExamSession.created_at.desc())
    )
    session = (await db.execute(query)).scalars().first()
    if not session:
        session = ExamSession(
            room_id=room.id,
            title="Automated Exam Session",
            status=ExamStatus.RUNNING,
        )
        db.add(session)
        await db.flush()
    return session


async def resolve_room_camera_id(
    db: AsyncSession,
    room_id: int,
    requested_camera_id: Optional[int],
) -> Optional[int]:
    if requested_camera_id is not None:
        camera = (
            await db.execute(
                select(Camera).where(
                    Camera.id == requested_camera_id,
                    Camera.room_id == room_id,
                )
            )
        ).scalars().first()
        return camera.id if camera else None

    cameras = (
        await db.execute(select(Camera).where(Camera.room_id == room_id))
    ).scalars().all()
    if len(cameras) == 1:
        return cameras[0].id
    return None


@router.post("/ai", status_code=status.HTTP_201_CREATED)
async def ingest_ai_event(payload: AIEventCreate, db: AsyncSession = Depends(get_db)):
    room = (
        await db.execute(select(ExamRoom).where(ExamRoom.id == payload.room_id))
    ).scalars().first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam room {payload.room_id} not found",
        )

    evidence_filename = None
    saved_file_path: Optional[Path] = None

    try:
        session = await get_or_create_active_session(db, room)
        camera_id = await resolve_room_camera_id(db, room.id, payload.camera_id)

        st_query = select(StudentTrack).where(
            StudentTrack.exam_session_id == session.id,
            StudentTrack.track_id == payload.track_id,
        )
        student = (await db.execute(st_query)).scalars().first()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        if not student:
            student = StudentTrack(
                exam_session_id=session.id,
                track_id=payload.track_id,
                student_name=f"Student {payload.track_id}",
                score=0.0,
                last_seen=now,
                image_path="",  # Placeholder, will be updated if evidence is provided
            )
            db.add(student)
            await db.flush()

        if payload.evidence_base64:
            try:
                b64_data = payload.evidence_base64.split(",", 1)[-1].strip()
                image_bytes = base64.b64decode(b64_data, validate=True)
                if image_bytes:
                    os.makedirs(EVIDENCE_DIR, exist_ok=True)
                    ts_str = now.strftime("%Y%m%d_%H%M%S_%f")
                    candidate_name = (
                        f"room{room.id}_{payload.event_type}_track{payload.track_id}_{ts_str}.jpg"
                    )
                    file_path = Path(EVIDENCE_DIR) / candidate_name
                    if file_path.exists():
                        candidate_name = (
                            f"room{room.id}_{payload.event_type}_track{payload.track_id}_"
                            f"{ts_str}_{uuid.uuid4().hex[:6]}.jpg"
                        )
                        file_path = Path(EVIDENCE_DIR) / candidate_name
                    with open(file_path, "wb") as f:
                        f.write(image_bytes)
                    evidence_filename = candidate_name
                    saved_file_path = file_path
            except Exception as e:
                evidence_filename = None
                saved_file_path = None
                print(f"[Event Router] Failed to save evidence base64: {e}")

        if payload.current_score is not None:
            student.score = payload.current_score
        else:
            student.score += payload.points

        student.is_suspicious = student.score >= 10.0
        student.head_yaw = payload.head_yaw if payload.head_yaw is not None else 0.0
        student.head_pitch = payload.head_pitch if payload.head_pitch is not None else 0.0
        student.zone_status = payload.zone_status or "safe"
        student.presence_state = payload.presence_state or "present"
        student.last_seen = now
        student.image_path = evidence_filename or student.image_path

        event = ViolationEvent(
            room_id=room.id,
            camera_id=camera_id,
            exam_session_id=session.id,
            student_track_id=student.id,
            track_id=payload.track_id,
            event_type=payload.event_type,
            points=payload.points,
            severity=payload.severity or "medium",
            is_violence=bool(payload.is_violence),
            evidence_path=evidence_filename,
            timestamp=now,
        )
        db.add(event)
        await db.commit()
        await db.refresh(event)
    except Exception:
        await db.rollback()
        if saved_file_path and saved_file_path.exists():
            try:
                saved_file_path.unlink()
            except OSError:
                pass
        raise

    evidence_url = f"/api/events/evidence/{evidence_filename}" if evidence_filename else None
    ws_payload = {
        "type": "violation_event",
        "data": {
            "id": event.id,
            "room_id": room.id,
            "camera_id": event.camera_id,
            "track_id": student.track_id,
            "student_name": student.student_name,
            "student_college_id": student.student_college_id,
            "event_type": event.event_type,
            "points": event.points,
            "severity": event.severity,
            "is_violence": event.is_violence,
            "total_score": student.score,
            "is_suspicious": student.is_suspicious,
            "evidence_url": evidence_url,
            "timestamp": now.strftime("%H:%M:%S"),
            "image_path": student.image_path,
        },
    }
    await manager.broadcast_to_room(room.id, ws_payload)
    await manager.broadcast(ws_payload)

    return {"ok": True, "event_id": event.id, "student_score": student.score}


@router.post("/sync")
async def sync_ai_status(payload: AIStatusSync, db: AsyncSession = Depends(get_db)):
    room = (
        await db.execute(select(ExamRoom).where(ExamRoom.id == payload.room_id))
    ).scalars().first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam room {payload.room_id} not found",
        )

    try:
        session = await get_or_create_active_session(db, room)
        session.student_count = payload.live_student_count
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    tracks_data = [t.model_dump() for t in payload.tracks]
    _latest_tracks[room.id] = tracks_data

    ws_payload = {
        "type": "status_sync",
        "data": {
            "room_id": room.id,
            "live_student_count": payload.live_student_count,
            "fps": payload.fps,
            "tracks": tracks_data,
        },
    }
    await manager.broadcast_to_room(room.id, ws_payload)
    await manager.broadcast(ws_payload)
    return {"ok": True}


@router.get("/recent", response_model=List[ViolationEventOut])
async def get_recent_events(limit: int = 50, db: AsyncSession = Depends(get_db)):
    query = select(ViolationEvent).order_by(ViolationEvent.timestamp.desc()).limit(limit)
    results = (await db.execute(query)).scalars().all()
    events_out = []
    for ev in results:
        ev_url = f"/api/events/evidence/{Path(ev.evidence_path).name}" if ev.evidence_path else None
        events_out.append(
            ViolationEventOut(
                id=ev.id,
                room_id=ev.room_id,
                camera_id=ev.camera_id,
                track_id=ev.track_id,
                event_type=ev.event_type,
                points=ev.points,
                is_violence=bool(ev.is_violence),
                severity=ev.severity or "medium",
                evidence_url=ev_url,
                timestamp=ev.timestamp,
            )
        )
    return events_out


@router.get("/evidence/{filename}")
async def get_evidence_image(filename: str):
    safe_name = Path(filename).name
    file_path = Path(EVIDENCE_DIR) / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Evidence image not found")
    return FileResponse(path=file_path, media_type="image/jpeg")
