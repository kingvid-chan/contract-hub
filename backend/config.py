"""Application configuration."""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

# Base path for deployment under /projects/contract-hub/
BASE_PATH = "/projects/contract-hub"
API_PREFIX = f"{BASE_PATH}/api"

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/contract_hub.db")

# JWT Authentication
SECRET_KEY = os.getenv("SECRET_KEY", "contract-hub-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

# File uploads
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
ALLOWED_CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "19007"))

# Version token for static assets
VERSION_TOKEN = "0.0.2"
