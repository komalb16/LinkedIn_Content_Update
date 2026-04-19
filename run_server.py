#!/usr/bin/env python
"""
Development server startup script for LinkedIn Content Generator SaaS Backend
Handles database initialization and runs FastAPI server
"""

import os
import sys
from pathlib import Path

# Set up environment
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load .env variables
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Ensure DATABASE_URL is set
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:///./linkedin_generator.db"
    print("[WARNING] DATABASE_URL not set, using SQLite: linkedin_generator.db")

# Initialize database
print("[INFO] Initializing database...")
from backend.database import init_db, is_database_healthy
try:
    init_db()
    print("[SUCCESS] Database initialized")
except Exception as e:
    print(f"[ERROR] Database init failed: {e}")
    sys.exit(1)

# Verify database
if not is_database_healthy():
    print("[ERROR] Database health check failed")
    sys.exit(1)

print("[SUCCESS] Database is healthy")

# Start FastAPI server
print("\n[INFO] Starting FastAPI server...")
print("[INFO] Swagger UI: http://localhost:8000/docs")
print("[INFO] ReDoc: http://localhost:8000/redoc")

import uvicorn
from backend.main import app

port = int(os.getenv("PORT", 8000))
uvicorn.run(
    app,
    host="0.0.0.0",
    port=port,
    log_level="info"
)
