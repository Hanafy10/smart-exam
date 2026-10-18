import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Float,
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    INVIGILATOR = "invigilator"


class ExamStatus(str, enum.Enum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class ExamRoom(Base):
    __tablename__ = "exam_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    building = Column(String(100), nullable=True)
    capacity = Column(Integer, default=30)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    invigilators = relationship("User", back_populates="assigned_room")
    cameras = relationship(
        "Camera",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    sessions = relationship(
        "ExamSession",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    events = relationship(
        "ViolationEvent",
        back_populates="room",
        cascade="all, delete-orphan",
    )


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("exam_rooms.id"),
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    device_index_or_url = Column(String(255), default="0")
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    room = relationship("ExamRoom", back_populates="cameras")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        Enum(UserRole),
        default=UserRole.INVIGILATOR,
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_room_id = Column(
        Integer,
        ForeignKey("exam_rooms.id"),
        nullable=True,
    )
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    refresh_token = Column(String(512), nullable=True, index=True)
    refresh_token_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    assigned_room = relationship("ExamRoom", back_populates="invigilators")


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("exam_rooms.id"),
        nullable=False,
    )
    title = Column(String(100), default="Exam Session")
    status = Column(
        Enum(ExamStatus),
        default=ExamStatus.RUNNING,
    )
    pause_reason = Column(String(100), nullable=True)
    student_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    room = relationship("ExamRoom", back_populates="sessions")
    students = relationship(
        "StudentTrack",
        back_populates="exam_session",
        cascade="all, delete-orphan",
    )
    events = relationship(
        "ViolationEvent",
        back_populates="exam_session",
        cascade="all, delete-orphan",
    )


class StudentTrack(Base):
    __tablename__ = "student_tracks"

    id = Column(Integer, primary_key=True, index=True)
    exam_session_id = Column(
        Integer,
        ForeignKey("exam_sessions.id"),
        nullable=False,
    )
    track_id = Column(Integer, index=True, nullable=False)
    student_college_id = Column(String(50), nullable=True)
    student_name = Column(String(100), nullable=True)
    score = Column(Float, default=0.0)
    is_suspicious = Column(Boolean, default=False)
    presence_state = Column(String(50), default="present")
    head_yaw = Column(Float, default=0.0)
    head_pitch = Column(Float, default=0.0)
    gaze_direction = Column(String(50), default="Eyes Center")
    zone_status = Column(String(50), default="safe")
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    exam_session = relationship("ExamSession", back_populates="students")
    events = relationship(
        "ViolationEvent",
        back_populates="student_track",
        cascade="all, delete-orphan",
    )


class ViolationEvent(Base):
    __tablename__ = "violation_events"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(
        Integer,
        ForeignKey("exam_rooms.id"),
        nullable=False,
    )
    camera_id = Column(
        Integer,
        ForeignKey("cameras.id"),
        nullable=True,
    )
    exam_session_id = Column(
        Integer,
        ForeignKey("exam_sessions.id"),
        nullable=True,
    )
    student_track_id = Column(
        Integer,
        ForeignKey("student_tracks.id"),
        nullable=True,
    )
    track_id = Column(Integer, nullable=True)
    event_type = Column(String(100), nullable=False)
    points = Column(Float, default=0.0)
    severity = Column(String(50), default="medium")
    is_violence = Column(Boolean, default=False)
    evidence_path = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    room = relationship("ExamRoom", back_populates="events")
    exam_session = relationship("ExamSession", back_populates="events")
    student_track = relationship("StudentTrack", back_populates="events")


class RobotDevice(Base):
    __tablename__ = "robot_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_code = Column(String(50), unique=True, nullable=False)
    status = Column(String(50), default="offline")
    battery_level = Column(Float, nullable=True)
    current_zone = Column(String(50), nullable=True)
    last_ping = Column(DateTime, nullable=True)
