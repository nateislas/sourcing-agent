"""
Configuration settings for the Deep Research Application.
Loads environment variables and defines constants for Temporal and task queues.
"""

import os
from dotenv import load_dotenv

load_dotenv()

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
# Use a specific task queue for this application
TASK_QUEUE = "deep-research-queue"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
