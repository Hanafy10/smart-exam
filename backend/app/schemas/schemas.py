from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# Authentication

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    assigned_room_id: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    assigned_room_id: Optional[int] = None
    assigned_room_name: Optional[str] = None


# Invigilator management

class InvigilatorCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    email: Optional[str] = None
    assigned_room_id: int


class InvigilatorUpdate(BaseModel):
    is_active: Optional[bool] = None
    assigned_room_id: Optional[int] = None
    password: Optional[str] = None


class InvigilatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    assigned_room_id: Optional[int] = None
    assigned_room_name: Optional[str] = None
    created_at: datetime


# Exam rooms and cameras

class ExamRoomCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    building: Optional[str] = None
    capacity: Optional[int] = 30


class CameraCreate(BaseModel):
    name: str
    device_index_or_url: str = "0"


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    name: str
    is_online: bool
    last_seen: Optional[datetime] = None


class ExamRoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    building: Optional[str] = None
    capacity: int
    cameras: List[CameraOut] = Field(default_factory=list)
    invigilator_count: Optional[int] = 0


# Monitoring

class RoomMonitoringSummary(BaseModel):
    room_id: int
    room_name: str
    building: Optional[str] = None
    total_students: int
    suspicious_students: int
    total_violations: int
    violence_detection_status: str = "unavailable"
    camera_online: bool
    is_paused: bool


# Events from the AI pipeline

class AIEventCreate(BaseModel):
    room_id: int
    camera_id: Optional[int] = None
    track_id: int
    event_type: str
    points: float
    evidence_base64: Optional[str] = None
    head_yaw: Optional[float] = 0.0
    head_pitch: Optional[float] = 0.0
    gaze_direction: Optional[str] = "Eyes Center"
    zone_status: Optional[str] = "safe"
    presence_state: Optional[str] = "present"
    current_score: Optional[float] = None
    is_violence: Optional[bool] = False
    severity: Optional[str] = "medium"


class AITrackState(BaseModel):
    track_id: int
    head_yaw: float = 0.0
    head_pitch: float = 0.0
    gaze_direction: str = "Eyes Center"
    gaze_baseline_h: float = 0.5
    zone_status: str = "safe"
    score: float = 0.0
    presence_state: str = "present"


class AIStatusSync(BaseModel):
    room_id: int
    live_student_count: int
    fps: int
    tracks: List[AITrackState] = Field(default_factory=list)


class ViolationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    camera_id: Optional[int] = None
    track_id: Optional[int] = None
    event_type: str
    points: float
    is_violence: bool = False
    severity: str = "medium"
    evidence_url: Optional[str] = None
    timestamp: datetime


class StudentAssignRequest(BaseModel):
    track_id: int
    student_college_id: str
    student_name: str


class StudentTrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    track_id: int
    student_college_id: Optional[str] = None
    student_name: Optional[str] = None
    score: float
    is_suspicious: bool
    presence_state: str
    head_yaw: float
    head_pitch: float
    gaze_direction: str
    zone_status: str
    events: List[ViolationEventOut] = Field(default_factory=list)


# Exam status

class ExamStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    title: str
    room_name: str
    status: str
    pause_reason: Optional[str] = None
    student_count: int


# Robot status and dispatch

class RobotStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_code: str
    status: str
    battery_level: Optional[float] = None
    current_zone: Optional[str] = None
    last_ping: Optional[datetime] = None


class RobotDispatchCommand(BaseModel):
    target_track_id: int
    reason: str = "Proctor manual dispatch"
