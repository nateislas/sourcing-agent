import logging
import os
import json
from datetime import datetime
from typing import Any


def get_session_logger(research_id: str) -> logging.Logger:
    """
    Returns a logger configured to write to a session-specific file.
    Creates the logs directory if it doesn't exist.
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger_name = f"research_{research_id}"
    logger = logging.getLogger(logger_name)

    # Avoid adding multiple handlers if the logger already has them
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        log_file = os.path.join(log_dir, f"{logger_name}.log")

        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Also log to console for visibility
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def log_api_call(
    logger: logging.Logger, provider: str, method: str, payload: Any, response: Any
):
    """
    Utility to log API requests and responses in a structured way.
    """
    timestamp = datetime.now().isoformat()

    # Try to serialize payload/response if they are dicts or objects
    def serialize(obj):
        try:
            if hasattr(obj, "model_dump"):  # Pydantic v2
                return obj.model_dump()
            if hasattr(obj, "dict"):  # Pydantic v1
                return obj.dict()
            return str(obj)
        except Exception:
            return str(obj)

    log_entry = {
        "timestamp": timestamp,
        "provider": provider,
        "method": method,
        "request": serialize(payload),
        "response": serialize(response),
    }

    logger.info(f"API_CALL: {json.dumps(log_entry, indent=2)}")
