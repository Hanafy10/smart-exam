
import os
import time
import threading
import traceback
from datetime import datetime

import cv2
import numpy as np
from flask import Flask, Response, render_template, jsonify, request, send_from_directory

from camera_capture import VideoCapture, list_available_cameras
from face_detector import FaceDetector, HeadPoseEstimator
from eye_gaze import EyeGazeEstimator
from person_detector import PersonDetector, PoseEstimator
from boundary_zones import DeskZoneManager, BoundaryZoneAnalyzer, ZoneThresholds
from object_detector import ObjectDetector
from scoring_system import StudentScoringEngine, ScoringRules

# ── Configuration ─────────────────────────────────────────────────────────────
# Change to 1 or 2 for iPhone Continuity Camera.
# Run: python3 -c "from camera_capture import list_available_cameras; print(list_available_cameras())"
CAMERA_INDEX     = 0
EVIDENCE_DIR     = "evidence"
BRIGHTNESS_ALPHA = 1.3
BRIGHTNESS_BETA  = 20

os.makedirs(EVIDENCE_DIR, exist_ok=True)
app = Flask(__name__)

# ── Student registry (optional cosmetic relabeling of auto-assigned IDs) ──────
student_registry: dict[int, dict] = {}
registry_lock = threading.Lock()


def get_label(track_id: int) -> tuple[str, str]:
    """Auto-ID is the default label; registry entry overrides it if set."""
    with registry_lock:
        info = student_registry.get(track_id)
    if info:
        return info["student_id"], info["name"]
    return f"AUTO-{track_id}", f"Student {track_id}"


# ── Pause / Resume + count-change alert state ─────────────────────────────────

class ExamControl:
    """
    Tracks whether scoring is currently paused, and why.
    - manual pause: proctor clicked Pause.
    - auto pause: triggered automatically when the detected student count
      changes from the last stable count. Requires the proctor to click
      Resume to acknowledge before scoring continues.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.paused = False
        self.pause_reason = None          # "manual" | "count_change" | None
        self.alert_message = None         # human-readable banner text
        self.last_stable_count = None     # last count.html confirmed by proctor
        self.pending_count = None         # the new count that triggered the alert

    def manual_pause(self):
        with self.lock:
            self.paused = True
            self.pause_reason = "manual"
            self.alert_message = "Exam paused by proctor."

    def manual_resume(self):
        with self.lock:
            self.paused = False
            self.pause_reason = None
            self.alert_message = None
            # Manual resume also re-confirms whatever count is on screen now.
            if self.pending_count is not None:
                self.last_stable_count = self.pending_count
                self.pending_count = None

    def check_count(self, current_count: int):
        """
        Call every frame with the live detected-student count.
        Auto-pauses (and sets an alert) the first time the count changes
        from the last stable value. Does nothing while already paused.
        """
        with self.lock:
            if self.last_stable_count is None:
                self.last_stable_count = current_count
                return
            if self.paused:
                return
            if current_count != self.last_stable_count:
                self.paused = True
                self.pause_reason = "count_change"
                self.pending_count = current_count
                self.alert_message = (
                    f"Student count changed: {self.last_stable_count} → {current_count}. "
                    f"Click Resume to confirm and continue."
                )

    def snapshot(self):
        with self.lock:
            return {
                "paused": self.paused,
                "pause_reason": self.pause_reason,
                "alert_message": self.alert_message,
                "last_stable_count": self.last_stable_count,
            }


exam_control = ExamControl()


# ── Shared state ───────────────────────────────────────────────────────────────

class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.latest_frame = None
        self.fps = 0
        self.is_setup_complete = False
        self.setup_progress = (0, 30)
        self.tracks: dict[int, dict] = {}
        self.live_count = 0

    def update_frame(self, frame, fps, is_setup_complete, setup_progress, live_count):
        with self.lock:
            self.latest_frame = frame.copy()
            self.fps = fps
            self.is_setup_complete = is_setup_complete
            self.setup_progress = setup_progress
            self.live_count = live_count

    def update_track(self, track_id, record, yaw, pitch,
                     gaze_dir, gaze_baseline_h, gaze_baseline_samples,
                     head_pose_ok, zone_status):
        sid, name = get_label(track_id)
        with self.lock:
            self.tracks[track_id] = {
                "track_id": track_id,
                "student_id": sid,
                "name": name,
                "score": round(record.score, 0),
                "is_suspicious": record.score >= 10,
                "presence_state": record.presence_state.value,
                "yaw": round(yaw, 1),
                "pitch": round(pitch, 1),
                "gaze_dir": gaze_dir or "N/A",
                "gaze_baseline_h": round(gaze_baseline_h, 3),
                "gaze_baseline_samples": gaze_baseline_samples,
                "head_pose_ok": head_pose_ok,
                "zone_status": zone_status or "unknown",
                "events": [
                    {
                        "time": datetime.fromtimestamp(ts).strftime("%H:%M:%S"),
                        "name": evt.replace("_", " ").title(),
                        "points": pts,
                        "evidence": ev_path,
                    }
                    for ts, evt, pts, ev_path in reversed(record.event_log[-20:])
                ],
            }

    def remove_stale_tracks(self, active_ids: set):
        """Drop tracks from the dashboard view once they've fully disappeared."""
        with self.lock:
            for tid in list(self.tracks.keys()):
                if tid not in active_ids:
                    # keep them visible but mark as gone — handled via presence_state
                    pass

    def get_frame_jpeg(self):
        with self.lock:
            if self.latest_frame is None:
                return None
            ok, buf = cv2.imencode(".jpg", self.latest_frame)
            return buf.tobytes() if ok else None

    def get_snapshot(self):
        with self.lock:
            return {
                "fps": self.fps,
                "is_setup_complete": self.is_setup_complete,
                "setup_progress": self.setup_progress,
                "tracks": list(self.tracks.values()),
                "live_count": self.live_count,
            }


shared_state = SharedState()


def save_evidence(frame, event_name: str) -> str:
    """
    Saves a compressed and resized screenshot to EVIDENCE_DIR.
    Resizing and JPEG compression significantly reduce disk I/O and make
    the web dashboard much faster to load.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"{event_name}_{ts}.jpg"
    filepath = os.path.join(EVIDENCE_DIR, filename)

    # Resize to a reasonable width (e.g. 640px) to save space and write-time.
    h, w = frame.shape[:2]
    max_w = 640
    if w > max_w:
        nh = int(h * (max_w / w))
        small_frame = cv2.resize(frame, (max_w, nh), interpolation=cv2.INTER_AREA)
    else:
        small_frame = frame

    # Save with JPEG compression (quality 70 is a good balance).
    cv2.imwrite(filepath, small_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return filepath



# ── Centroid Tracker (this IS the auto-ID system) ─────────────────────────────
# Every new bounding box that can't be matched to an existing track gets
# self.next_id automatically (0, 1, 2, 3, ...) — that's the auto-ID assignment.
# No manual input is required for a track to exist and be scored.

class CentroidTracker:
    def __init__(self, max_disappeared: int = 30):
        self.next_id = 0
        self.tracks: dict[int, np.ndarray] = {}
        self.disappeared: dict[int, int] = {}
        self.max_disappeared = max_disappeared

    def _centroid(self, bbox):
        x1, y1, x2, y2 = bbox
        return np.array([(x1+x2)/2, (y1+y2)/2], dtype=float)

    def update(self, bboxes: list) -> dict[int, tuple]:
        if not bboxes:
            for tid in list(self.disappeared):
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    del self.tracks[tid]
                    del self.disappeared[tid]
            return {}

        new_cents = [self._centroid(b) for b in bboxes]

        if not self.tracks:
            for c, b in zip(new_cents, bboxes):
                self.tracks[self.next_id] = c          # <- auto-ID assigned here
                self.disappeared[self.next_id] = 0
                self.next_id += 1
            return {tid: bboxes[i] for i, tid in enumerate(self.tracks)}

        track_ids = list(self.tracks.keys())
        old_cents = [self.tracks[tid] for tid in track_ids]

        D = np.linalg.norm(
            np.array(old_cents)[:, None] - np.array(new_cents)[None, :], axis=2
        )

        matched_old, matched_new, assignments = set(), set(), {}
        for row in D.min(axis=1).argsort():
            col = D[row].argmin()
            if row in matched_old or col in matched_new:
                continue
            if D[row, col] > 150:
                continue
            tid = track_ids[row]
            assignments[tid] = col
            self.tracks[tid] = new_cents[col]
            self.disappeared[tid] = 0
            matched_old.add(row)
            matched_new.add(col)

        for i, tid in enumerate(track_ids):
            if i not in matched_old:
                self.disappeared[tid] += 1
                if self.disappeared[tid] > self.max_disappeared:
                    del self.tracks[tid]
                    del self.disappeared[tid]

        for j, (c, b) in enumerate(zip(new_cents, bboxes)):
            if j not in matched_new:
                self.tracks[self.next_id] = c            # <- auto-ID assigned here too
                self.disappeared[self.next_id] = 0
                assignments[self.next_id] = j
                self.next_id += 1

        return {
            tid: bboxes[col]
            for tid, col in assignments.items()
            if tid in self.tracks
        }


# ── Detection loop ─────────────────────────────────────────────────────────────

def detection_loop():
    try:
        print("[detection_loop] Initializing models...")
        face_detector    = FaceDetector()
        head_pose_est    = HeadPoseEstimator()
        gaze_est         = EyeGazeEstimator()
        person_detector  = PersonDetector(confidence_threshold=0.5)
        body_pose_est    = PoseEstimator()
        object_detector  = ObjectDetector(confidence_threshold=0.4)
        thresholds       = ZoneThresholds()
        zone_manager     = DeskZoneManager(thresholds=thresholds, setup_frames=30)
        leaning_analyzer = BoundaryZoneAnalyzer(thresholds=thresholds)
        scoring_engine   = StudentScoringEngine(ScoringRules())
        tracker          = CentroidTracker(max_disappeared=30)

        last_event_counts: dict[int, int] = {}
        fps_counter, fps_timer, current_fps, frame_count = 0, time.time(), 0, 0

        print(f"[detection_loop] Available cameras: {list_available_cameras()}")
        print(f"[detection_loop] Opening camera index {CAMERA_INDEX}...")

        with VideoCapture(camera_index=CAMERA_INDEX) as camera:
            print("[detection_loop] Camera ready.")

            while True:
                success, frame = camera.read()
                if not success:
                    time.sleep(0.05)
                    continue

                frame = cv2.convertScaleAbs(frame, alpha=BRIGHTNESS_ALPHA, beta=BRIGHTNESS_BETA)
                frame_count += 1
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    current_fps = fps_counter
                    fps_counter = 0
                    fps_timer   = time.time()

                if frame_count % 60 == 0:
                    print(f"[detection_loop] Frame {frame_count} | FPS:{current_fps} | "
                          f"Setup:{zone_manager.is_setup_complete} | "
                          f"Tracks:{len(tracker.tracks)}")

                # Person detection + tracking (auto-ID happens inside tracker.update)
                people  = person_detector.detect(frame)
                bboxes  = [p["bbox"] for p in people]
                id_to_bbox = tracker.update(bboxes)
                live_count = len(id_to_bbox)

                people_with_pose = []
                for tid, bbox in id_to_bbox.items():
                    pose = body_pose_est.estimate_in_region(frame, bbox)
                    people_with_pose.append({"id": tid, "bbox": bbox, "pose": pose})

                # Setup phase (zone calibration) — runs regardless of pause state
                if not zone_manager.is_setup_complete:
                    zone_manager.setup_frame(people_with_pose)
                    progress = (
                        min(zone_manager._frames_seen, zone_manager.setup_frames),
                        zone_manager.setup_frames,
                    )
                    display = frame.copy()
                    cv2.putText(display,
                                f"SETTING UP ZONES... {progress[0]}/{progress[1]}",
                                (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,255,255), 2)
                    cv2.putText(display, f"Detected: {len(people_with_pose)} people",
                                (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180,180,180), 1)
                    shared_state.update_frame(display, current_fps, False, progress, live_count)
                    continue

                # Check for student-count change -> may auto-pause
                exam_control.check_count(live_count)
                control_state = exam_control.snapshot()
                is_paused = control_state["paused"]

                # Zone check (visual only while paused; still useful context)
                zone_results = zone_manager.check_zones(people_with_pose)
                zone_by_id: dict[int, str] = {}
                for zr in zone_results:
                    if zr["current_center"] is None:
                        continue
                    zrx, zry = zr["current_center"]
                    best_tid, best_dist = None, float("inf")
                    for p in people_with_pose:
                        if p["pose"] is None:
                            continue
                        sc = p["pose"]["shoulder_center"]
                        d  = ((sc[0]-zrx)**2 + (sc[1]-zry)**2)**0.5
                        if d < best_dist:
                            best_dist, best_tid = d, p["id"]
                    if best_tid is not None:
                        zone_by_id[best_tid] = zr["status"]

                # Full-frame detections
                faces      = face_detector.detect(frame)
                head_poses = head_pose_est.estimate(frame)
                gazes      = gaze_est.estimate(frame)
                objects    = object_detector.detect(frame)

                # Per-track scoring — SKIPPED while paused (no new violations counted)
                for p in people_with_pose:
                    tid  = p["id"]
                    bbox = p["bbox"]
                    bx1, by1, bx2, by2 = bbox
                    person_cx = (bx1 + bx2) / 2
                    person_cy = (by1 + by2) / 2

                    scoring_engine.update_presence(tid, is_detected=True)

                    # Head pose nearest to this person
                    yaw, pitch, head_pose_ok = 0.0, 0.0, False
                    if head_poses:
                        best_hp = min(
                            head_poses,
                            key=lambda hp: (
                                (hp["nose_2d"][0]-person_cx)**2 +
                                (hp["nose_2d"][1]-person_cy)**2
                            )
                        )
                        dist = ((best_hp["nose_2d"][0]-person_cx)**2 +
                                (best_hp["nose_2d"][1]-person_cy)**2)**0.5
                        if dist < 300:
                            yaw, pitch, head_pose_ok = best_hp["yaw"], best_hp["pitch"], True

                    faces_here = [
                        f for f in faces
                        if bx1 <= (f["bbox"][0]+f["bbox"][2])/2 <= bx2
                        and by1 <= (f["bbox"][1]+f["bbox"][3])/2 <= by2
                    ]

                    gaze_dir, gaze_h_ratio = None, None
                    if gazes:
                        gaze_dir     = gazes[0]["gaze_direction"]
                        gaze_h_ratio = gazes[0]["horizontal_ratio"]

                    if not is_paused:
                        if len(faces_here) > 1:
                            scoring_engine.report_another_face(tid)
                        elif not head_pose_ok and len(faces_here) > 0:
                            scoring_engine.report_detection_failure(tid)

                        scoring_engine.update_head_pose(tid, yaw, pitch, gaze_dir, gaze_h_ratio)

                        for obj in objects:
                            ox1, oy1, ox2, oy2 = obj["bbox"]
                            obj_cx = (ox1+ox2)/2
                            obj_cy = (oy1+oy2)/2
                            if bx1 <= obj_cx <= bx2 and by1 <= obj_cy <= by2:
                                scoring_engine.report_mobile_detected(tid)

                        for lr in leaning_analyzer.analyze_leaning([p]):
                            if lr["leaning_status"] == "violation":
                                scoring_engine.report_leaning_violation(tid)

                        zone_status = zone_by_id.get(tid)
                        if zone_status == "violation":
                            scoring_engine.report_desk_zone_violation(tid)
                    else:
                        # Still track gaze baseline passively so calibration
                        # isn't lost, but don't score violations.
                        zone_status = zone_by_id.get(tid)

                    # Evidence (only generated for events scored above, so
                    # naturally skipped while paused since no new events appear)
                    record = scoring_engine.get_record(tid)
                    last_n = last_event_counts.get(tid, 0)
                    if len(record.event_log) > last_n:
                        if not is_paused:
                            for i, (ts, evt, pts, ev_path) in enumerate(record.event_log[last_n:]):
                                if ev_path is None:
                                    ep = save_evidence(frame, evt)
                                    record.event_log[last_n + i] = (ts, evt, pts, ep)
                        last_event_counts[tid] = len(record.event_log)

                    shared_state.update_track(
                        tid, record, yaw, pitch,
                        gaze_dir or "N/A",
                        record.gaze_baseline_h,
                        record.gaze_baseline_samples,
                        head_pose_ok, zone_status,
                    )

                # Absent tracks
                detected_ids = set(id_to_bbox.keys())
                if not is_paused:
                    for tid in list(scoring_engine.students.keys()):
                        if tid not in detected_ids:
                            scoring_engine.update_presence(tid, is_detected=False)

                # Draw overlays
                display = frame.copy()
                STATUS_COLORS = {"safe":(0,255,0),"warning":(0,255,255),"violation":(0,0,255)}

                for zone_id, zone in zone_manager.zones.items():
                    cx, cy = map(int, zone["center"])
                    cv2.circle(display,(cx,cy),int(zone["safe_radius"]),(0,180,0),1)
                    cv2.circle(display,(cx,cy),int(zone["violation_radius"]),(0,0,180),1)

                for p in people_with_pose:
                    tid = p["id"]
                    x1, y1, x2, y2 = p["bbox"]
                    sid, name = get_label(tid)
                    rec   = scoring_engine.get_record(tid)
                    zs    = zone_by_id.get(tid, "safe")
                    color = (0,0,255) if rec.score >= 10 else STATUS_COLORS.get(zs,(0,255,0))
                    cv2.rectangle(display,(x1,y1),(x2,y2),color,2)
                    cv2.putText(display,f"{name} | {rec.score:.0f}pts",
                                (x1,y1-10),cv2.FONT_HERSHEY_SIMPLEX,0.6,color,2)

                for f in faces:
                    fx1,fy1,fx2,fy2 = f["bbox"]
                    cv2.rectangle(display,(fx1,fy1),(fx2,fy2),(0,255,0),1)

                for obj in objects:
                    ox1,oy1,ox2,oy2 = obj["bbox"]
                    cv2.rectangle(display,(ox1,oy1),(ox2,oy2),(0,0,255),2)
                    cv2.putText(display,obj["label"],(ox1,oy1-6),
                                cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,0,255),2)

                fps_c = (0,255,0) if current_fps>=15 else (0,165,255)
                cv2.putText(display,f"FPS:{current_fps} | Students:{live_count}",
                            (display.shape[1]-300,30),cv2.FONT_HERSHEY_SIMPLEX,0.65,fps_c,2)

                if is_paused:
                    overlay = display.copy()
                    cv2.rectangle(overlay, (0,0), (display.shape[1], 70), (0,0,0), -1)
                    display = cv2.addWeighted(overlay, 0.55, display, 0.45, 0)
                    reason_text = ("PAUSED — Student count changed"
                                   if control_state["pause_reason"] == "count_change"
                                   else "PAUSED by proctor")
                    cv2.putText(display, f"⏸ {reason_text}", (10, 45),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 215, 255), 2)

                shared_state.update_frame(display, current_fps, True, (30,30), live_count)
                time.sleep(0.01)

    except Exception:
        print("\n"+"="*60)
        print("[detection_loop] CRASHED:")
        traceback.print_exc()
        print("="*60)


# ── Flask routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/video_feed")
def video_feed():
    def generate():
        while True:
            data = shared_state.get_frame_jpeg()
            if data:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"
            time.sleep(0.033)
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/status")
def api_status():
    snap = shared_state.get_snapshot()
    snap["exam_control"] = exam_control.snapshot()
    return jsonify(snap)

@app.route("/api/assign_student", methods=["POST"])
def assign_student():
    """
    Optional cosmetic relabel of an auto-assigned track.
    Body: { "track_id": 0, "student_id": "2021001", "name": "Ahmed Ali" }
    """
    data       = request.get_json()
    track_id   = int(data.get("track_id", -1))
    student_id = str(data.get("student_id", "")).strip()
    name       = str(data.get("name", f"Student {track_id}")).strip()
    if track_id < 0 or not student_id:
        return jsonify({"ok": False, "error": "track_id and student_id required"}), 400
    with registry_lock:
        student_registry[track_id] = {"student_id": student_id, "name": name}
    return jsonify({"ok": True, "track_id": track_id,
                    "student_id": student_id, "name": name})

@app.route("/api/pause", methods=["POST"])
def api_pause():
    exam_control.manual_pause()
    return jsonify({"ok": True, **exam_control.snapshot()})

@app.route("/api/resume", methods=["POST"])
def api_resume():
    exam_control.manual_resume()
    return jsonify({"ok": True, **exam_control.snapshot()})

@app.route("/api/cameras")
def api_cameras():
    return jsonify({"cameras": list_available_cameras()})

@app.route("/evidence/<filename>")
def evidence_file(filename):
    return send_from_directory(EVIDENCE_DIR, filename)


if __name__ == "__main__":
    t = threading.Thread(target=detection_loop, daemon=True)
    t.start()
    print(f"Dashboard → http://127.0.0.1:5001")
    print(f"Camera index: {CAMERA_INDEX}")
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)
