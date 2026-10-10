"""Robot camera controller (pan/tilt) for in-person paper-distribution checks."""
import math
import time
import threading

try:
    import serial  # type: ignore
except Exception:
    serial = None


class RobotController:
    """Drives a pan/tilt servo robot camera.

    Modes:
      - "simulated": pure software sweep, no hardware needed.
      - "serial": sends angle commands over a serial port (e.g. Arduino).

    The robot's job is to sweep the desk row and detect paper/materials
    (via PaperDetector) to catch in-person paper distribution.
    """

    def __init__(self, mode="simulated", port=None, baudrate=115200,
                 pan_range=(0, 180), tilt_range=(30, 150),
                 sweep_seconds=6.0, sweep_step_deg=6.0):
        self.mode = mode
        self.port = port
        self.baudrate = baudrate
        self.pan_range = pan_range
        self.tilt_range = tilt_range
        self.sweep_seconds = sweep_seconds
        self.sweep_step_deg = sweep_step_deg

        self._pan = (pan_range[0] + pan_range[1]) / 2.0
        self._tilt = (tilt_range[0] + tilt_range[1]) / 2.0
        self._ser = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        if mode == "serial" and port and serial is not None:
            try:
                self._ser = serial.Serial(port, baudrate, timeout=1)
                time.sleep(0.5)
            except Exception as e:
                print(f"[RobotController] Serial open failed: {e} -> falling back to simulated")
                self.mode = "simulated"

    def current_pan_tilt(self):
        with self._lock:
            return self._pan, self._tilt

    def set_pan_tilt(self, pan, tilt):
        pan = max(self.pan_range[0], min(self.pan_range[1], pan))
        tilt = max(self.tilt_range[0], min(self.tilt_range[1], tilt))
        with self._lock:
            self._pan = pan
            self._tilt = tilt
        self._send_command(pan, tilt)

    def _send_command(self, pan, tilt):
        if self.mode == "serial" and self._ser is not None:
            try:
                self._ser.write(f"P{int(round(pan))}T{int(round(tilt))}\n".encode())
            except Exception as e:
                print(f"[RobotController] Serial write failed: {e}")
        # simulated mode: nothing to send

    def start_sweep(self, on_frame=None):
        """Run a continuous sweep in a background thread.

        on_frame(pan, tilt) is called periodically so the detection loop
        can grab a frame at each position.
        """
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._sweep_loop,
                                         args=(on_frame,), daemon=True)
        self._thread.start()

    def stop_sweep(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _sweep_loop(self, on_frame):
        pan_min, pan_max = self.pan_range
        tilt_min, tilt_max = self.tilt_range
        step = self.sweep_step_deg

        while self._running:
            # Pan sweep left->right, tilt stays low (desk surface)
            pan = pan_min
            while pan <= pan_max and self._running:
                self.set_pan_tilt(pan, tilt_min)
                if on_frame:
                    on_frame(pan, tilt_min)
                pan += step
                time.sleep(self.sweep_seconds / ((pan_max - pan_min) / step + 1))

            # Pan sweep right->left, tilt higher (catch hands/papers raised)
            pan = pan_max
            while pan >= pan_min and self._running:
                self.set_pan_tilt(pan, tilt_max)
                if on_frame:
                    on_frame(pan, tilt_max)
                pan -= step
                time.sleep(self.sweep_seconds / ((pan_max - pan_min) / step + 1))

    def close(self):
        self.stop_sweep()
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass