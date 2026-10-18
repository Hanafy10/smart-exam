
import cv2


# Built-in camera
CAMERA_INDEX = 0


class CameraCapture:
    """Wrapper class for reading frames from the built-in camera."""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        fps: int = 30
    ):
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None

    def start(self):
        """Open the camera and configure resolution + FPS."""
        self.cap = cv2.VideoCapture(CAMERA_INDEX)

        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            raise RuntimeError(
                f"Could not open camera at index {CAMERA_INDEX}. "
                "Check camera permissions and Docker device access."
            )

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

        print(
            f"[CameraCapture] Connected to built-in camera — "
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

