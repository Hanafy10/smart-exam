import os
from pathlib import Path
import time
import base64
import requests
import cv2
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass


class EventGenerator:
    """
    Dispatches violation events, live frames, and periodic status heartbeats
    from the AI Pipeline to the Backend FastAPI server via room-scoped HTTP POST endpoints.
    """
    def __init__(self, backend_url: Optional[str] = None, room_id: Optional[int] = None):
        resolved_url = backend_url or os.environ.get("BACKEND_URL", "http://192.168.1.9:8000")
        self.backend_url = resolved_url.rstrip("/")
        self.room_id = room_id if room_id is not None else int(os.environ.get("ROOM_ID", "1"))
        self.events_endpoint = f"{self.backend_url}/api/monitoring/ai/event"
        self.sync_endpoint = f"{self.backend_url}/api/monitoring/ai/sync"
        self.frame_endpoint = f"{self.backend_url}/api/monitoring/ai/frame?room_id={self.room_id}"
        self.last_sync_time = 0.0
        self.last_frame_time = 0.0

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
    ) -> bool:
        """
        Sends an alert event to the backend. Encodes the current frame as base64 JPEG evidence.
        """
        evidence_b64 = None
        if frame is not None:
            try:
                success, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if success:
                    evidence_b64 = base64.b64encode(buffer).decode("utf-8")
            except Exception as e:
                print(f"[EventGenerator] Failed to encode frame evidence: {e}")

        payload = {
            "room_id": self.room_id,
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
