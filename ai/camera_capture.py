import os
from pathlib import Path
from typing import Union
import cv2

ROOT_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

_raw_camera_index = os.environ.get("CAMERA_INDEX", "0")
CAMERA_INDEX: Union[int, str] = int(_raw_camera_index) if _raw_camera_index.isdigit() else _raw_camera_index
CAMERA_WIDTH = int(os.environ.get("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.environ.get("CAMERA_HEIGHT", "720"))
CAMERA_FPS = int(os.environ.get("CAMERA_FPS", "30"))


class CameraCapture:
    """Wrapper class for reading frames from the configured camera or stream."""

    def __init__(
        self,
        camera_index: Union[int, str] = CAMERA_INDEX,
        width: int = CAMERA_WIDTH,
        height: int = CAMERA_HEIGHT,
        fps: int = CAMERA_FPS,
    ):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None

    def start(self):
        """Open the camera and configure resolution + FPS."""
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            raise RuntimeError(
                f"Could not open camera at index/source {self.camera_index}. "
                "Check camera permissions and Docker device access."
            )

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

        print(
            f"[CameraCapture] Connected to camera ({self.camera_index}) — "
            f"{actual_w}x{actual_h} @ {actual_fps:.1f}fps"
        )

        return self

    def read(self):
        """Return (success, frame)."""
        if self.cap is None:
            raise RuntimeError("Camera not started. Call start() first.")

        return self.cap.read()

    def is_opened(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def release(self):
        """Release the camera resource."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
