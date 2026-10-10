import json
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from jose import jwt
from sqlalchemy import select

from backend.app.core.config import SECRET_KEY, ALGORITHM
from backend.app.core.database import AsyncSessionLocal
from backend.app.models.models import User, UserRole, ExamRoom

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websockets"])

class ConnectionManager:
    def __init__(self):
        # Maps room_id -> list of active WebSockets
        self.room_connections: Dict[int, List[WebSocket]] = {}
        # Fallback / global connections
        self.active_connections: List[WebSocket] = []

    async def connect_room(self, websocket: WebSocket, room_id: int):
        await websocket.accept()
        if room_id not in self.room_connections:
            self.room_connections[room_id] = []
        self.room_connections[room_id].append(websocket)
        logger.info(f"WebSocket client connected to room {room_id}. Total room listeners: {len(self.room_connections[room_id])}")

    def disconnect_room(self, websocket: WebSocket, room_id: int):
        if room_id in self.room_connections and websocket in self.room_connections[room_id]:
            self.room_connections[room_id].remove(websocket)
            logger.info(f"WebSocket client disconnected from room {room_id}. Remaining: {len(self.room_connections[room_id])}")

    async def broadcast_to_room(self, room_id: int, message: dict):
        """Strictly broadcasts event only to connections in room_id."""
        if room_id not in self.room_connections:
            return
        payload = json.dumps(message)
        for connection in list(self.room_connections[room_id]):
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Error broadcasting to room {room_id} client: {e}")
                self.disconnect_room(connection, room_id)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        payload = json.dumps(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception as e:
                self.disconnect(connection)

manager = ConnectionManager()

async def authenticate_ws_token(token: str) -> Optional[User]:
    """Validates JWT token for WebSocket connection."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        return None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        return user

@router.websocket("/ws/monitoring")
async def monitoring_ws_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Authenticated WebSocket strictly for invigilators monitoring their assigned room.
    Admins and unassigned/inactive invigilators are rejected.
    """
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication token required")
        return

    user = await authenticate_ws_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return

    if not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Account deactivated")
        return

    if user.role == UserRole.ADMIN:
        # User requirement: Admin uses REST only, no monitoring WebSocket
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Admin accounts cannot connect to monitoring WebSocket")
        return

    if not user.assigned_room_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No exam room assigned to invigilator")
        return

    room_id = user.assigned_room_id
    await manager.connect_room(websocket, room_id)
    try:
        await websocket.send_text(json.dumps({
            "type": "connected",
            "message": f"Connected to Exam Room {room_id} Monitoring",
            "room_id": room_id,
            "username": user.username,
        }))
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect_room(websocket, room_id)
    except Exception as e:
        logger.warning(f"Room {room_id} WebSocket error: {e}")
        manager.disconnect_room(websocket, room_id)

@router.websocket("/ws/dashboard")
async def legacy_dashboard_ws(websocket: WebSocket):
    """Legacy endpoint for backward compatibility."""
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"type": "connected", "message": "Connected to Exam Dashboard"}))
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
