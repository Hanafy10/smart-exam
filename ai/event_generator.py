import os
from pathlib import Path
import time
import base64
import requests
import cv2
from typing import Optional
from ai.helper.find_ip import get_private_ip
ROOT_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

private_ip = get_private_ip()

class EventGenerator:
    """
    Dispatches violation events, live frames, and periodic status heartbeats
    from the AI Pipeline to the Backend FastAPI server via room-scoped HTTP POST endpoints.
    """
    def __init__(
        self,
        backend_url: Optional[str] = None,
        room_id: Optional[int] = None,
        clear_seconds: Optional[float] = None,
        cooldown_seconds: Optional[float] = None,
        clear_frames: Optional[int] = None,
    ):
        resolved_url = backend_url or os.environ.get("BACKEND_URL", f"http://{private_ip}:8000")
        if not resolved_url.startswith(("http://", "https://")):
            resolved_url = f"http://{resolved_url}"
        self.backend_url = resolved_url.rstrip("/")
        self.room_id = room_id if room_id is not None else int(os.environ.get("ROOM_ID", "1"))
        self.events_endpoint = f"{self.backend_url}/api/events/ai"
        self.sync_endpoint = f"{self.backend_url}/api/events/sync"
        self.frame_endpoint = f"{self.backend_url}/api/monitoring/ai/frame?room_id={self.room_id}"
        self.last_sync_time = 0.0
        self.last_frame_time = 0.0
        self.clear_seconds = (
            float(clear_seconds)
            if clear_seconds is not None
            else float(os.environ.get("VIOLATION_CLEAR_SECONDS", "3.5"))
        )
        self.cooldown_seconds = (
            float(cooldown_seconds)
            if cooldown_seconds is not None
            else float(os.environ.get("VIOLATION_COOLDOWN_SECONDS", "0.0"))
        )
        self.clear_frames = (
            int(clear_frames)
            if clear_frames is not None
            else int(os.environ.get("VIOLATION_CLEAR_FRAMES", "5"))
        )
        # Active violations keyed by (room_id, track_id, event_type)
        self.active_violations: dict[tuple[int, int, str], dict] = {}

    def _is_key_active(self, key: tuple[int, int, str], now: Optional[float] = None) -> bool:
        if now is None:
            now = time.monotonic()
        state = self.active_violations.get(key)
        if state is None:
            return False
        if self.clear_seconds > 0 and (now - state["last_seen"]) >= self.clear_seconds:
            del self.active_violations[key]
            return False
        if self.cooldown_seconds > 0 and (now - state["last_sent"]) >= self.cooldown_seconds:
            del self.active_violations[key]
            return False
        return True

    def is_violation_active(
        self,
        track_id: int,
        event_type: str,
        room_id: Optional[int] = None,
    ) -> bool:
        target_room = self.room_id if room_id is None else room_id
        return self._is_key_active((target_room, track_id, event_type))

    def clear_violation(
        self,
        track_id: int,
        event_type: Optional[str] = None,
        room_id: Optional[int] = None,
    ) -> None:
        target_room = self.room_id if room_id is None else room_id
        if event_type is not None:
            self.active_violations.pop((target_room, track_id, event_type), None)
        else:
            for k in [
                k for k in self.active_violations
                if k[0] == target_room and k[1] == track_id
            ]:
                self.active_violations.pop(k, None)

    def record_frame_violations(
        self,
        track_id: int,
        active_event_types,
        room_id: Optional[int] = None,
    ) -> None:
        target_room = self.room_id if room_id is None else room_id
        active_set = set(active_event_types)
        now = time.monotonic()
        for k in list(self.active_violations.keys()):
            if k[0] != target_room or k[1] != track_id:
                continue
            evt = k[2]
            state = self.active_violations[k]
            if evt in active_set:
                state["last_seen"] = now
                state["inactive_frames"] = 0
            else:
                state["inactive_frames"] = state.get("inactive_frames", 0) + 1
                if state["inactive_frames"] >= self.clear_frames:
                    del self.active_violations[k]

    def push_frame(self, frame) -> bool:
        """
        Sends current frame to backend MJPEG stream buffer at ~10-15 fps.
        """
        now = time.time()
        if now - self.last_frame_time < 0.07:
            return False
        self.last_frame_time = now

        try:
            ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                resp = requests.post(self.frame_endpoint, data=buffer.tobytes(), timeout=0.5)
                return resp.status_code == 200
        except Exception:
            pass
        return False

    def send_violation(
        self,
        track_id: int,
        event_type: str,
        points: float,
        frame=None,
        head_yaw: float = 0.0,
        head_pitch: float = 0.0,
        zone_status: str = "safe",
        presence_state: str = "present",
        current_score: Optional[float] = None,
        severity: str = "medium",
        is_violence: bool = False,
        room_id: Optional[int] = None,
        camera_id: Optional[int] = None,
    ) -> bool:
        """
        Sends an alert event to the backend. Encodes the current frame as base64 JPEG evidence.
        Suppresses repeated submissions while the same (room_id, track_id, event_type) remains active.
        """
        target_room = self.room_id if room_id is None else room_id
        key = (target_room, track_id, event_type)
        now = time.monotonic()

        if self._is_key_active(key, now):
            self.active_violations[key]["last_seen"] = now
            self.active_violations[key]["inactive_frames"] = 0
            return False

        self.active_violations[key] = {
            "first_seen": now,
            "last_seen": now,
            "last_sent": now,
            "inactive_frames": 0,
        }

        evidence_b64 = None
        if frame is not None:
            try:
                success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if success:
                    evidence_b64 = base64.b64encode(buffer).decode("utf-8")
            except Exception as e:
                print(f"[EventGenerator] Failed to encode frame evidence: {e}")

        payload = {
            "room_id": target_room,
            "track_id": track_id,
            "event_type": event_type,
            "points": points,
            "evidence_base64": evidence_b64,
            "head_yaw": head_yaw,
            "head_pitch": head_pitch,
            "zone_status": zone_status,
            "presence_state": presence_state,
            "current_score": current_score,
            "severity": severity,
            "is_violence": is_violence,
        }
        if camera_id is not None:
            payload["camera_id"] = camera_id

        try:
            resp = requests.post(self.events_endpoint, json=payload, timeout=2.0)
            return resp.status_code == 201
        except Exception as e:
            print(f"[EventGenerator] Warning: Could not post event to backend: {e}")
            return False

    def sync_status(self, live_student_count: int, fps: int, tracks: list) -> bool:
        """
        Throttled status sync every 1 second.
        """
        now = time.time()
        if now - self.last_sync_time < 1.0:
            return False
        self.last_sync_time = now

        payload = {
            "room_id": self.room_id,
            "live_student_count": live_student_count,
            "fps": fps,
            "tracks": tracks,
        }

        try:
            resp = requests.post(self.sync_endpoint, json=payload, timeout=1.0)
            return resp.status_code == 200
        except Exception:
            return False
