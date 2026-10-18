
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.models import RobotDevice, User
from backend.app.schemas.schemas import RobotStatusOut, RobotDispatchCommand
from backend.app.routers.ws import manager

router = APIRouter(prefix="/api/robot", tags=["robot"])

HEARTBEAT_INTERVAL = 30
OFFLINE_TIMEOUT = 90


class RobotHealthCheck(BaseModel):
    device_code: str = Field(min_length=1, max_length=50)
    battery_level: float | None = Field(default=None, ge=0, le=100)
    current_zone: str | None = Field(default=None, max_length=50)


@router.get("/status", response_model=RobotStatusOut)
async def get_robot_status(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RobotDevice))
    robot = result.scalars().first()

    if robot is None:
        raise HTTPException(
            status_code=404,
            detail="No robot has registered yet",
        )

    # Calculate connectivity from the last real heartbeat.
    if (
        robot.last_ping is None
        or datetime.utcnow() - robot.last_ping
        > timedelta(seconds=OFFLINE_TIMEOUT)
    ):
        return {
            "id": robot.id,
            "device_code": robot.device_code,
            "status": "offline",
            "battery_level": robot.battery_level,
            "current_zone": robot.current_zone,
            "last_ping": robot.last_ping,
        }

    return robot


@router.post("/healthcheck")
async def robot_healthcheck(
    payload: RobotHealthCheck,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RobotDevice).where(
            RobotDevice.device_code == payload.device_code
        )
    )
    robot = result.scalars().first()

    now = datetime.utcnow()

    if robot is None:
        # Register the device from its real heartbeat.
        robot = RobotDevice(
            device_code=payload.device_code,
            status="online",
            battery_level=payload.battery_level,
            current_zone=payload.current_zone,
            last_ping=now,
        )
        db.add(robot)
    else:
        robot.status = "online"
        robot.last_ping = now

        # Update optional values only when the ESP provides them.
        if payload.battery_level is not None:
            robot.battery_level = payload.battery_level

        if payload.current_zone is not None:
            robot.current_zone = payload.current_zone

    await db.commit()

    return {
        "ok": True,
        "status": "online",
        "device_code": robot.device_code,
        "last_ping": now,
    }


@router.post("/dispatch")
async def dispatch_robot(
    command: RobotDispatchCommand,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(RobotDevice))
    robot = result.scalars().first()

    if robot is None:
        raise HTTPException(
            status_code=404,
            detail="No registered robot",
        )

    if (
        robot.last_ping is None
        or datetime.utcnow() - robot.last_ping
        > timedelta(seconds=OFFLINE_TIMEOUT)
    ):
        raise HTTPException(
            status_code=409,
            detail="Robot is offline",
        )

    # This records the requested inspection; it does not move the robot.
    await manager.broadcast({
        "type": "robot_dispatched",
        "data": {
            "device_code": robot.device_code,
            "target_track_id": command.target_track_id,
            "reason": command.reason,
            "status": "requested",
        },
    })

    return {
        "ok": True,
        "status": "requested",
        "target": command.target_track_id,
    }
