import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = BASE_DIR.parent

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

# Security & JWT
SECRET_KEY = os.environ.get("SECRET_KEY", "smart-exam-super-secret-key-graduation-project-2026")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_HOURS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_HOURS", "2"))  # 2 hours per requirement

# Rate Limiting & Account Lockout
MAX_LOGIN_ATTEMPTS = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
LOCK_MINUTES = int(os.environ.get("LOCK_MINUTES", "15"))
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "10"))
RATE_LIMIT_WINDOW_MINUTES = int(os.environ.get("RATE_LIMIT_WINDOW_MINUTES", "1"))

# CORS
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

# Database & Storage
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+aiomysql://smart_exam_user:SmartExam@123@localhost:3306/smart_exam",
)
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", str(ROOT_DIR / "evidence"))
os.makedirs(EVIDENCE_DIR, exist_ok=True)

# Default Seed Data
DEFAULT_ADMIN_USERNAME = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@smartexam.edu")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "Admin@12345678")
DEFAULT_ROOM_NAME = os.environ.get("DEFAULT_ROOM_NAME", "Hall 101")
DEFAULT_ROOM_BUILDING = os.environ.get("DEFAULT_ROOM_BUILDING", "Engineering Complex A")
DEFAULT_ROOM_CAPACITY = int(os.environ.get("DEFAULT_ROOM_CAPACITY", "40"))
DEFAULT_CAMERA_NAME = os.environ.get("DEFAULT_CAMERA_NAME", "Ceiling Overhead Cam 1")
DEFAULT_CAMERA_DEVICE = os.environ.get("DEFAULT_CAMERA_DEVICE", "0")

# Robot Configuration
ROBOT_HEARTBEAT_INTERVAL = int(os.environ.get("ROBOT_HEARTBEAT_INTERVAL", "30"))
ROBOT_OFFLINE_TIMEOUT = int(os.environ.get("ROBOT_OFFLINE_TIMEOUT", "90"))

