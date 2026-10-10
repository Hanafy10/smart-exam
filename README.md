# Smart Exam Proctoring System

A Python computer-vision system that monitors students during an exam through a
webcam and flags suspicious behavior in real time — head turns, eye gaze away from
the screen, phone detection, multiple faces, leaning toward another student, and
leaving the desk zone. Built with **OpenCV**, **MediaPipe**, and **YOLOv8**, with
a live **Flask + SocketIO** web dashboard.

## Features

- 👤 Face detection + head pose estimation (yaw/pitch)
- 👁 Eye gaze tracking with a per-student calibrated baseline
- 🧍 Person detection, pose estimation, and desk-zone boundary checks
- 📱 Phone / object detection (YOLOv8)
- 🤖 **Robot camera sweep** — pan/tilt camera detects in-person paper distribution
- 🔢 Multi-student tracking — each detected person gets an automatic ID, no manual setup
- ⏸ Pause / Resume — manually pause, or auto-pause when student count changes
- 📊 Live web dashboard — per-student score, violation events, evidence screenshots
- ⚡ **WebSocket push** — real-time updates (no 1s polling lag)
- 📷 Works with a built-in webcam or an iPhone via Continuity Camera

## Requirements

- Python 3.10+
- A webcam (built-in, USB, or iPhone via Continuity Camera)
- Optional: pan/tilt servo kit for robot camera (Arduino + 2 servos)

## Setup

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd <repo-folder>

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the dashboard
python dashboard.py
```

Then open **http://127.0.0.1:5001** in your browser.

## Using an iPhone as the camera

```bash
python3 -c "from camera_capture import list_available_cameras; print(list_available_cameras())"
```

This prints the available camera indices. Update `STABLE_INDEX` and `ROBOT_INDEX` near the top of `dashboard.py` with the correct indices (usually `0` and `1` or `1` and `2`).

## Robot Camera (Paper Distribution Detection)

The system supports a second camera on a pan/tilt mount to detect in-person paper distribution between students:

- **Simulated mode** (default): sweeps virtually, useful for testing without hardware
- **Serial mode**: connects to Arduino over USB, sends `P<pan>T<tilt>\n` commands

Configure in `dashboard.py`:
```python
ROBOT_MODE  = "simulated"   # or "serial"
ROBOT_PORT  = None          # e.g. "/dev/tty.usbmodem14101" on macOS
ROBOT_INDEX = 1             # camera index for robot cam
```

## Project Structure

```
.
├── dashboard.py          # Main app: detection loop + Flask + SocketIO dashboard
├── camera_capture.py     # Webcam / iPhone camera wrapper
├── face_detector.py      # Face detection + head pose estimation
├── eye_gaze.py           # Eye gaze tracking
├── person_detector.py    # Person detection + pose estimation
├── boundary_zones.py     # Desk zone setup + leaning/boundary checks
├── object_detector.py    # Phone / object detection (YOLOv8) + PaperDetector
├── robot_controller.py   # Pan/tilt robot camera controller
├── scoring_system.py     # Per-student scoring engine
├── templates/
│   └── index.html        # Live dashboard UI (camera tabs, seat grid)
├── requirements.txt
└── yolov8n.pt            # YOLOv8 nano model weights
```

## Dashboard UI

- **Stable Camera** tab: full proctoring view (scoring, gaze, phone, zones)
- **Robot Camera** tab: pan/tilt sweep view with paper detection
- **Seat Grid**: per-student desk material count from robot camera
- **Pause/Resume**: manual or auto on student-count change
- **Evidence**: click thumbnails for full screenshots

## Testing & DevOps

### Smoke Tests (`tests/test_smoke.py`)

Unit-style smoke tests that validate core logic **without** requiring a camera, GPU, or the heavy ML models (ultralytics, mediapipe, OpenCV). They stub out external dependencies and test:

| Test | What it validates |
|------|-------------------|
| `test_object_detector_has_expected_classes` | `ObjectDetector` uses COCO class 67 for "cell phone" |
| `test_paper_detector_exists` | `PaperDetector` uses COCO class 84 ("book") as paper proxy |
| `test_robot_controller_simulated_mode` | `RobotController` sweeps pan/tilt and calls `on_frame` callback |
| `test_scoring_rules_defaults` | Default point values (phone=5, face=5, suspicious threshold=10) |
| `test_scoring_engine_basic` | Score accumulation, `is_suspicious()` threshold logic |
| `test_presence_state_machine` | Student presence states: PRESENT → TEMPORARILY_MISSING → WARNING_MISSING → EXITED |

Run locally:
```bash
make test          # syntax check + smoke tests
# or
python -m pytest tests/test_smoke.py -v
```

### CI Pipeline (`.github/workflows/ci.yml`)

Runs on every push and PR:
1. **Syntax check** — `python -m py_compile` on all modules
2. **Lint** — `ruff` (ignores line-length E501, blank-line W293)
3. **Type check** — `mypy` (optional, non-blocking)
4. **Docker build** — on `main` branch only, verifies container starts

### Docker

```bash
make docker-build   # builds smart-exam:latest
make docker-run     # runs on port 5001 with webcam access
```

### Pre-commit Hooks

```bash
pip install pre-commit && pre-commit install
# Runs ruff --fix, mypy, trailing-whitespace, large-file check on commit
```

### Git LFS for Model Weights

The `yolov8n.pt` (6.5 MB) should be tracked with Git LFS:
```bash
make lfs-track
```

## Notes

- On first run, the system spends ~30 frames calibrating desk zones — keep students seated still during this phase.
- This is a graduation project / proof of concept, not a production exam security tool. Detection accuracy depends heavily on camera angle and lighting.
