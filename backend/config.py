"""
Configuration settings for the Deep Research Application.
Loads environment variables and defines constants for Temporal and task queues.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root (one level up from backend/)
ROOT_DIR = Path(__file__).parent.parent
env_path = ROOT_DIR / ".env"

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()  # Fallback

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
# Use a specific task queue for this application
TASK_QUEUE = "deep-research-queue"
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", 5))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

if not GEMINI_API_KEY:
    # Diagnostic logging
    print(f"DEBUG: Config loader - .env exists at {env_path}: {env_path.exists()}")
    print(
        f"DEBUG: Config loader - GEMINI_API_KEY present in env: {bool(os.getenv('GEMINI_API_KEY'))}"
    )
    print(
        f"DEBUG: Config loader - GOOGLE_API_KEY present in env: {bool(os.getenv('GOOGLE_API_KEY'))}"
    )
