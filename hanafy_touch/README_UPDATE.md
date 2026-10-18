# Smart Exam — MUST dashboard update

## Copy these files into ~/Downloads/smart-exam/
| File | Where | What changed |
|---|---|---|
| dashboard.py | project root | replaces old file: session login, 2 roles, new routes, SQLite API |
| admin_db.py | project root | NEW: database + admin/doctor REST API |
| templates/must_dashboard.html | templates/ | NEW: final MUST-branded dashboard (doctor + admin) |
| templates/login.html | templates/ | NEW: MUST login page |
| templates/index.html | templates/ | replaces old: MUST colors + logo (operator console) |
| templates/monitor.html | templates/ | replaces old: MUST colors + logo, avatar CSS bug fixed (height:40 → 40px) |
| static/must_logo.png | static/ (create folder) | NEW: MUST seal |
| .env.example | project root | copy to .env and set real passwords |

No new pip packages are needed (sqlite3 is built into Python).

## Run
    cd ~/Downloads/smart-exam && source venv/bin/activate && python dashboard.py
Open http://127.0.0.1:5001 → sign in.
- admin account → Overview, Students, Examinations, Rooms, Colleges, Users, Reports
- doctor account → Dashboard, Live Monitoring, Incidents, Robot, Students

## Pages
/login, /logout, /app (final dashboard), /console (old operator console), /monitor (light monitor)

## Notes
- Seed data (colleges, rooms, 40 students, 4 exams) is SAMPLE data. Delete smart_exam.db to reset.
- Old PROCTOR_USERNAME / PROCTOR_PASSWORD still work as the doctor account.
- Every API route now needs a login; /api/assign_student and WebSocket connections are protected too.
- Use HTTPS (or a trusted network) if the dashboard is reachable outside your laptop.
