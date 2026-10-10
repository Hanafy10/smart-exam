"""Basic smoke tests for Smart Exam Proctoring modules.

Run: python -m pytest tests/test_smoke.py -v
"""
import sys
import types

# Stub heavy deps BEFORE importing project modules
for name in ("cv2", "numpy", "ultralytics", "mediapipe"):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

sys.modules["cv2"].VideoCapture = lambda *a, **k: None
sys.modules["cv2"].imencode = lambda *a, **k: (True, b"")
sys.modules["cv2"].imwrite = lambda *a, **k: True
sys.modules["cv2"].convertScaleAbs = lambda *a, **k: None
sys.modules["cv2"].rectangle = lambda *a, **k: None
sys.modules["cv2"].putText = lambda *a, **k: None
sys.modules["cv2"].circle = lambda *a, **k: None
sys.modules["cv2"].FONT_HERSHEY_SIMPLEX = 0
sys.modules["cv2"].cvtColor = lambda *a, **k: None
sys.modules["cv2"].COLOR_BGR2RGB = 0

sys.modules["numpy"].array = lambda *a, **k: []
sys.modules["numpy"].linalg = types.SimpleNamespace(norm=lambda *a, **k: 0.0)
sys.modules["numpy"].degrees = lambda x: x
sys.modules["numpy"].clip = lambda *a, **k: 0
sys.modules["numpy"].float64 = float
sys.modules["numpy"].int64 = int
sys.modules["numpy"].zeros = lambda *a, **k: []
sys.modules["numpy"].sqrt = lambda x: x**0.5
sys.modules["numpy"].arctan2 = lambda *a, **k: 0

sys.modules["ultralytics"].YOLO = lambda *a, **k: types.SimpleNamespace(
    __call__=lambda *a, **k: [types.SimpleNamespace(
        boxes=[],
        verbose=False
    )]
)

sys.modules["mediapipe"].solutions = types.SimpleNamespace(
    face_mesh=types.SimpleNamespace(
        FaceMesh=lambda *a, **k: types.SimpleNamespace(
            process=lambda *a, **k: types.SimpleNamespace(
                multi_face_landmarks=[]
            ),
            close=lambda: None
        )
    ),
    face_detection=types.SimpleNamespace(
        FaceDetection=lambda *a, **k: types.SimpleNamespace(
            process=lambda *a, **k: types.SimpleNamespace(detections=[]),
            close=lambda: None
        )
    ),
    pose=types.SimpleNamespace(
        Pose=lambda *a, **k: types.SimpleNamespace(
            process=lambda *a, **k: types.SimpleNamespace(pose_landmarks=None),
            close=lambda: None
        )
    )
)

# Now import project modules
import pytest
from object_detector import ObjectDetector, PaperDetector
from robot_controller import RobotController
from scoring_system import ScoringRules, StudentScoringEngine, PresenceState


def test_object_detector_has_expected_classes():
    od = ObjectDetector.__new__(ObjectDetector)
    assert "cell phone" in od.COCO_CLASS_IDS
    assert od.COCO_CLASS_IDS["cell phone"] == 67


def test_paper_detector_exists():
    pd = PaperDetector.__new__(PaperDetector)
    assert "book" in pd.COCO_CLASS_IDS
    assert pd.COCO_CLASS_IDS["book"] == 84


def test_robot_controller_simulated_mode():
    r = RobotController(mode="simulated", sweep_seconds=0.01)
    assert r.mode == "simulated"
    assert r.pan_range == (0, 180)
    assert r.tilt_range == (30, 150)

    frames = []
    def capture(pan, tilt):
        frames.append((pan, tilt))
    r.start_sweep(on_frame=capture)
    import time; time.sleep(0.05)
    r.stop_sweep()
    assert len(frames) > 0


def test_scoring_rules_defaults():
    rules = ScoringRules()
    assert rules.looking_sideways == 1
    assert rules.mobile_detected == 5
    assert rules.another_face_detected == 5
    assert rules.suspicious_score_threshold == 10


def test_scoring_engine_basic():
    engine = StudentScoringEngine(ScoringRules())
    engine.update_presence(0, True)
    rec = engine.get_record(0)
    assert rec.presence_state == PresenceState.PRESENT
    assert rec.score == 0.0

    engine.report_mobile_detected(0)
    rec = engine.get_record(0)
    assert rec.score == 5

    engine.report_another_face(0)
    rec = engine.get_record(0)
    assert rec.score == 10
    assert rec.is_suspicious(10) is False  # strictly greater
    assert rec.is_suspicious(9) is True


def test_presence_state_machine():
    engine = StudentScoringEngine(ScoringRules())
    engine.update_presence(1, True)
    engine.update_presence(1, False)  # missing
    import time
    # Simulate time passing by directly setting timestamp
    rec = engine.get_record(1)
    rec.last_seen_timestamp = time.time() - 15
    engine.update_presence(1, False)
    rec = engine.get_record(1)
    assert rec.presence_state == PresenceState.WARNING_MISSING