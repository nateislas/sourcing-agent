"""
Link filtering utilities for intelligent URL queue management.
Implements fast rejection patterns and queue size management.
"""

from urllib.parse import urlparse
import re


class LinkFilter:
    """Fast link filtering using heuristic rejection patterns."""

    # Domains to always reject
    REJECTED_DOMAINS = {
        # Social media
        "twitter.com",
        "x.com",
        "linkedin.com",
        "facebook.com",
        "instagram.com",
        "youtube.com",
        # Search engines & aggregators
        "google.com",
        "bing.com",
        "yahoo.com",
        "duckduckgo.com",
        # Generic navigation
        "wikipedia.org",  # Too generic for specific drug discovery
    }

    # Path patterns to reject (regex)
    REJECTED_PATH_PATTERNS = [
        r"/login",
        r"/signin",
        r"/signup",
        r"/register",
        r"/contact",
        r"/about-us",
        r"/careers",
        r"/privacy",
        r"/terms",
        r"/cookie",
        r"/support",
        r"/help",
        r"/faq",
        # Search result pages (not actual content)
        r"/search\?",
        r"/results\?",
    ]

    # File extensions to reject
    REJECTED_EXTENSIONS = {
        ".zip",
        ".exe",
        ".dmg",
        ".pkg",
        ".deb",
        ".rpm",
        ".tar",
        ".gz",
        ".rar",
        ".7z",
        # Media files (unlikely to contain text data)
        ".mp4",
        ".avi",
        ".mov",
        ".mp3",
        ".wav",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
    }

    # Queue size limit per worker
    MAX_QUEUE_SIZE = 100

    def __init__(self):
        # Compile regex patterns for performance
        self._path_patterns = [re.compile(p, re.IGNORECASE) for p in self.REJECTED_PATH_PATTERNS]

    def should_reject_fast(self, url: str) -> tuple[bool, str]:
        """
        Fast rejection check using heuristics.

        Returns:
            (should_reject: bool, reason: str)
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()

            # Check rejected domains
            for rejected_domain in self.REJECTED_DOMAINS:
                if domain.endswith(rejected_domain):
                    return True, f"Rejected domain: {rejected_domain}"

            # Check rejected path patterns
            for pattern in self._path_patterns:
                if pattern.search(path):
                    return True, f"Rejected path pattern: {pattern.pattern}"

            # Check file extensions
            for ext in self.REJECTED_EXTENSIONS:
                if path.endswith(ext):
                    return True, f"Rejected file extension: {ext}"

            # Passed all fast rejection checks
            return False, ""

        except Exception as e:
            # If URL parsing fails, reject it
            return True, f"Invalid URL: {e}"

    def can_add_to_queue(self, current_queue_size: int) -> bool:
        """Check if queue has space for new links."""
        return current_queue_size < self.MAX_QUEUE_SIZE

    def get_queue_pressure(self, current_queue_size: int) -> float:
        """
        Calculate queue pressure (0.0 = empty, 1.0 = full).
        Used to decide when to enable LLM scoring.
        """
        return min(current_queue_size / self.MAX_QUEUE_SIZE, 1.0)
