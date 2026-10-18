"""
admin_db.py — SQLite database + REST API for the Smart Exam admin/doctor dashboard.

Tables: colleges, departments, students, rooms, exams, exam_students,
        alert_reviews, audit.
Seed data is SAMPLE data for the prototype (delete smart_exam.db to reset).

Usage in dashboard.py:
    from admin_db import init_db, create_blueprint
    init_db()
    app.register_blueprint(create_blueprint(requires_auth, requires_role,
                                            get_user, EVIDENCE_DIR, list_accounts))
"""
import csv
import glob
import io
import os
import re
import sqlite3
from datetime import datetime, timedelta

from flask import Blueprint, Response, jsonify, request

DB_PATH = os.getenv("DB_PATH", "smart_exam.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS colleges(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS departments(
  id INTEGER PRIMARY KEY, college TEXT NOT NULL, name TEXT NOT NULL,
  UNIQUE(college, name));
CREATE TABLE IF NOT EXISTS students(
  id INTEGER PRIMARY KEY, student_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  college TEXT NOT NULL, department TEXT NOT NULL DEFAULT '', year INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS rooms(
  id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, building TEXT NOT NULL,
  college TEXT NOT NULL, capacity INTEGER NOT NULL, cameras INTEGER NOT NULL DEFAULT 0,
  robot TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Online');
CREATE TABLE IF NOT EXISTS exams(
  id INTEGER PRIMARY KEY, subject TEXT NOT NULL, college TEXT NOT NULL,
  room TEXT NOT NULL, doctor TEXT NOT NULL, starts_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Scheduled');
CREATE TABLE IF NOT EXISTS exam_students(
  exam_id INTEGER NOT NULL, student_id TEXT NOT NULL, PRIMARY KEY(exam_id, student_id));
CREATE TABLE IF NOT EXISTS alert_reviews(
  file TEXT PRIMARY KEY, reviewed_by TEXT NOT NULL, reviewed_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, user TEXT NOT NULL, action TEXT NOT NULL);
"""

EXAM_STATUSES = ("Scheduled", "Active", "Completed", "Cancelled")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _seed(db):
    if db.execute("SELECT COUNT(*) FROM colleges").fetchone()[0]:
        return
    tree = {
        "Information Technology": ["Computer Science", "Information Systems", "Artificial Intelligence"],
        "Engineering": ["Communications", "Mechatronics"],
        "Pharmacy": ["Pharmaceutics"],
        "Medicine": ["General Medicine"],
        "Business": ["Marketing"],
    }
    for c, deps in tree.items():
        db.execute("INSERT INTO colleges(name) VALUES(?)", (c,))
        for d in deps:
            db.execute("INSERT INTO departments(college,name) VALUES(?,?)", (c, d))
    rooms = [
        ("B-204", "Building B", "Information Technology", 40, 2, "Robot-01", "Online"),
        ("B-101", "Building B", "Information Technology", 60, 2, "Robot-02", "Online"),
        ("C-310", "Building C", "Pharmacy", 80, 1, "", "Camera weak"),
        ("A-020", "Building A", "Medicine", 120, 3, "Robot-03", "Offline"),
    ]
    db.executemany("INSERT INTO rooms(code,building,college,capacity,cameras,robot,status) VALUES(?,?,?,?,?,?,?)", rooms)
    first = ["Ahmed", "Mona", "Omar", "Salma", "Youssef", "Nour", "Hana", "Karim", "Laila", "Tamer"]
    last = ["Samir", "Khaled", "Nabil", "Adel", "Hany", "Tarek", "Fathy", "Mostafa"]
    cols = list(tree.items())
    for i in range(40):
        col, deps = cols[i % len(cols)]
        year = 1 + i % 4
        db.execute(
            "INSERT INTO students(student_id,name,college,department,year) VALUES(?,?,?,?,?)",
            (f"{2020 + year}/{10000 + i}", f"{first[i % 10]} {last[i % 8]}", col, deps[i % len(deps)], year),
        )
    exams = [
        ("Machine Learning", "Information Technology", "B-204", "Dr. Hassan", "2026-10-20T10:00", "Scheduled"),
        ("Data Structures", "Information Technology", "B-101", "Dr. Mervat", "2026-10-17T09:00", "Active"),
        ("Pharmacology", "Pharmacy", "C-310", "Dr. Amr", "2026-10-14T12:00", "Completed"),
        ("Anatomy II", "Medicine", "A-020", "Dr. Laila", "2026-10-22T11:00", "Scheduled"),
    ]
    for e in exams:
        cur = db.execute("INSERT INTO exams(subject,college,room,doctor,starts_at,status) VALUES(?,?,?,?,?,?)", e)
        db.execute(
            "INSERT INTO exam_students SELECT ?, student_id FROM students WHERE college=?",
            (cur.lastrowid, e[1]),
        )


def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)
        _seed(db)


def _csv_safe(v):
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@") else s  # block CSV/Excel formula injection


_EV = re.compile(r"^(.+)_(\d{8})_(\d{6})_\d{3}\.jpg$")


def create_blueprint(requires_auth, requires_role, get_user, evidence_dir, list_accounts):
    bp = Blueprint("admin_db", __name__)

    def audit(action):
        u = get_user()
        with get_db() as db:
            db.execute("INSERT INTO audit(at,user,action) VALUES(?,?,?)", (_now(), u["username"] if u else "?", action))

    def evidence_items():
        files = sorted(glob.glob(os.path.join(evidence_dir, "*.jpg")), key=os.path.getmtime, reverse=True)
        with get_db() as db:
            reviewed = {r["file"] for r in db.execute("SELECT file FROM alert_reviews")}
        out = []
        for f in files:
            name = os.path.basename(f)
            m = _EV.match(name)
            if m:
                ts = datetime.strptime(m.group(2) + m.group(3), "%Y%m%d%H%M%S")
                event = m.group(1).replace("_", " ")
            else:
                ts = datetime.fromtimestamp(os.path.getmtime(f))
                event = name
            out.append({"file": name, "event": event, "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "day": ts.strftime("%Y-%m-%d"), "url": "/evidence/" + name, "reviewed": name in reviewed})
        return out

    # ── shared (doctor + admin) ───────────────────────────────────────────────
    @bp.route("/api/me")
    @requires_auth
    def me():
        u = get_user()
        return jsonify({"username": u["username"], "role": u["role"], "display": u["display"]})

    @bp.route("/api/alerts")
    @requires_auth
    def alerts():
        return jsonify({"alerts": evidence_items()[:50]})

    @bp.route("/api/alerts/<path:filename>/review", methods=["POST"])
    @requires_auth
    def review_alert(filename):
        name = os.path.basename(filename)
        if not os.path.isfile(os.path.join(evidence_dir, name)):
            return jsonify({"ok": False, "error": "unknown snapshot"}), 404
        with get_db() as db:
            db.execute("INSERT OR REPLACE INTO alert_reviews VALUES(?,?,?)", (name, get_user()["username"], _now()))
        audit(f"Reviewed incident {name}")
        return jsonify({"ok": True})

    @bp.route("/api/exams")
    @requires_auth
    def exams():
        with get_db() as db:
            rows = db.execute(
                "SELECT e.*, (SELECT COUNT(*) FROM exam_students s WHERE s.exam_id=e.id) AS students "
                "FROM exams e ORDER BY starts_at").fetchall()
        return jsonify({"items": [dict(r) for r in rows]})

    # ── admin only ────────────────────────────────────────────────────────────
    @bp.route("/api/admin/overview")
    @requires_role("admin")
    def overview():
        with get_db() as db:
            q = lambda s: db.execute(s).fetchone()[0]
            cams = q("SELECT COALESCE(SUM(cameras),0) FROM rooms")
            robots = q("SELECT COUNT(*) FROM rooms WHERE robot!=''")
            on_c = q("SELECT COALESCE(SUM(cameras),0) FROM rooms WHERE status='Online'")
            on_r = q("SELECT COUNT(*) FROM rooms WHERE robot!='' AND status='Online'")
            data = {
                "colleges": q("SELECT COUNT(*) FROM colleges"),
                "departments": q("SELECT COUNT(*) FROM departments"),
                "rooms": q("SELECT COUNT(*) FROM rooms"),
                "students": q("SELECT COUNT(*) FROM students"),
                "exams_scheduled": q("SELECT COUNT(*) FROM exams WHERE status='Scheduled'"),
                "devices_total": cams + robots,
                "devices_online": on_c + on_r,
            }
        data["incidents"] = len(evidence_items())
        return jsonify(data)

    @bp.route("/api/admin/students", methods=["GET"])
    @requires_role("admin")
    def students():
        q = request.args.get("q", "").strip()
        college = request.args.get("college", "").strip()
        page = max(1, int(request.args.get("page", 1) or 1))
        per = min(100, max(1, int(request.args.get("per", 10) or 10)))
        where, args = ["1=1"], []
        if q:
            where.append("(name LIKE ? OR student_id LIKE ?)")
            args += [f"%{q}%", f"%{q}%"]
        if college:
            where.append("college=?")
            args.append(college)
        w = " AND ".join(where)
        with get_db() as db:
            total = db.execute(f"SELECT COUNT(*) FROM students WHERE {w}", args).fetchone()[0]
            rows = db.execute(
                f"SELECT student_id,name,college,department,year FROM students WHERE {w} "
                "ORDER BY name LIMIT ? OFFSET ?", args + [per, (page - 1) * per]).fetchall()
        return jsonify({"items": [dict(r) for r in rows], "total": total, "page": page, "per": per})

    @bp.route("/api/admin/students", methods=["POST"])
    @requires_role("admin")
    def add_student():
        d = request.get_json(silent=True) or {}
        name, sid, college = (str(d.get(k, "")).strip() for k in ("name", "student_id", "college"))
        dept = str(d.get("department", "")).strip()
        try:
            year = int(d.get("year", 1))
        except (TypeError, ValueError):
            year = 0
        if not (name and sid and college) or not 1 <= year <= 7:
            return jsonify({"ok": False, "error": "name, student_id, college and a valid year are required"}), 400
        try:
            with get_db() as db:
                db.execute("INSERT INTO students(student_id,name,college,department,year) VALUES(?,?,?,?,?)",
                           (sid, name, college, dept, year))
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "student ID already exists"}), 409
        audit(f"Added student {sid}")
        return jsonify({"ok": True})

    @bp.route("/api/admin/exams", methods=["POST"])
    @requires_role("admin")
    def add_exam():
        d = request.get_json(silent=True) or {}
        subject, college, room, doctor, starts = (str(d.get(k, "")).strip()
                                                  for k in ("subject", "college", "room", "doctor", "starts_at"))
        if not all((subject, college, room, doctor, starts)):
            return jsonify({"ok": False, "error": "subject, college, room, doctor and date/time are required"}), 400
        year = str(d.get("year", "")).strip()
        with get_db() as db:
            r = db.execute("SELECT capacity FROM rooms WHERE code=?", (room,)).fetchone()
            if not r:
                return jsonify({"ok": False, "error": "unknown room"}), 400
            cur = db.execute("INSERT INTO exams(subject,college,room,doctor,starts_at) VALUES(?,?,?,?,?)",
                             (subject, college, room, doctor, starts))
            sql = "INSERT INTO exam_students SELECT ?, student_id FROM students WHERE college=?"
            args = [cur.lastrowid, college]
            if year.isdigit():
                sql += " AND year=?"
                args.append(int(year))
            db.execute(sql, args)
            n = db.execute("SELECT COUNT(*) FROM exam_students WHERE exam_id=?", (cur.lastrowid,)).fetchone()[0]
        audit(f"Scheduled exam '{subject}' in {room}")
        return jsonify({"ok": True, "id": cur.lastrowid, "students": n, "over_capacity": n > r["capacity"]})

    @bp.route("/api/admin/exams/<int:exam_id>/cancel", methods=["POST"])
    @requires_role("admin")
    def cancel_exam(exam_id):
        with get_db() as db:
            cur = db.execute("UPDATE exams SET status='Cancelled' WHERE id=? AND status IN ('Scheduled','Active')",
                             (exam_id,))
        if not cur.rowcount:
            return jsonify({"ok": False, "error": "exam not found or already finished"}), 404
        audit(f"Cancelled exam #{exam_id}")
        return jsonify({"ok": True})

    @bp.route("/api/admin/rooms")
    @requires_role("admin")
    def rooms():
        with get_db() as db:
            rows = db.execute("SELECT code,building,college,capacity,cameras,robot,status FROM rooms ORDER BY code").fetchall()
        return jsonify({"items": [dict(r) for r in rows]})

    @bp.route("/api/admin/colleges", methods=["GET"])
    @requires_role("admin")
    def colleges():
        with get_db() as db:
            rows = db.execute(
                "SELECT c.name, (SELECT COUNT(*) FROM departments d WHERE d.college=c.name) AS departments, "
                "(SELECT COUNT(*) FROM rooms r WHERE r.college=c.name) AS rooms, "
                "(SELECT COUNT(*) FROM students s WHERE s.college=c.name) AS students "
                "FROM colleges c ORDER BY c.name").fetchall()
        return jsonify({"items": [dict(r) for r in rows]})

    @bp.route("/api/admin/colleges", methods=["POST"])
    @requires_role("admin")
    def add_college():
        name = str((request.get_json(silent=True) or {}).get("name", "")).strip()
        if not name:
            return jsonify({"ok": False, "error": "name required"}), 400
        try:
            with get_db() as db:
                db.execute("INSERT INTO colleges(name) VALUES(?)", (name,))
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "college already exists"}), 409
        audit(f"Added college {name}")
        return jsonify({"ok": True})

    @bp.route("/api/admin/departments", methods=["POST"])
    @requires_role("admin")
    def add_department():
        d = request.get_json(silent=True) or {}
        college, name = str(d.get("college", "")).strip(), str(d.get("name", "")).strip()
        with get_db() as db:
            if not (college and name) or not db.execute("SELECT 1 FROM colleges WHERE name=?", (college,)).fetchone():
                return jsonify({"ok": False, "error": "valid college and department name required"}), 400
            try:
                db.execute("INSERT INTO departments(college,name) VALUES(?,?)", (college, name))
            except sqlite3.IntegrityError:
                return jsonify({"ok": False, "error": "department already exists"}), 409
        audit(f"Added department {name} to {college}")
        return jsonify({"ok": True})

    @bp.route("/api/admin/users")
    @requires_role("admin")
    def users():
        return jsonify({"items": list_accounts()})

    @bp.route("/api/admin/reports")
    @requires_role("admin")
    def reports():
        days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
        counts = {d: 0 for d in days}
        for e in evidence_items():
            if e["day"] in counts:
                counts[e["day"]] += 1
        with get_db() as db:
            status = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) n FROM exams GROUP BY status")}
            log = [dict(r) for r in db.execute("SELECT at,user,action FROM audit ORDER BY id DESC LIMIT 10")]
        return jsonify({"incidents_by_day": [{"day": d, "count": counts[d]} for d in days],
                        "exam_status": status, "audit": log})

    @bp.route("/api/admin/export/<kind>.csv")
    @requires_role("admin")
    def export(kind):
        if kind == "exams":
            sql, head = ("SELECT subject,college,room,doctor,starts_at,status FROM exams ORDER BY starts_at",
                         ["subject", "college", "room", "doctor", "starts_at", "status"])
            rows = [list(r) for r in get_db().execute(sql)]
        elif kind == "incidents":
            head = ["time", "event", "file", "reviewed"]
            rows = [[e["time"], e["event"], e["file"], "yes" if e["reviewed"] else "no"] for e in evidence_items()]
        else:
            return jsonify({"ok": False, "error": "unknown export"}), 404
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(head)
        for r in rows:
            w.writerow([_csv_safe(c) for c in r])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={kind}.csv"})

    return bp
