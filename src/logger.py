# logger.py
"""Centralized logging for Foam-Agent workflow.

Provides:
- XML-tagged output to stdout for structured parsing
- workflow.log: captures ALL print output (via stdout tee)
- review.log: captures only reviewer-related output (errors, review analysis, rewrite plans)

Usage:
    from logger import setup_logging, close_logging, log_review

    setup_logging("/path/to/case_dir")   # call once case_dir is known
    # ... all subsequent print() calls are captured in workflow.log ...
    log_review(error_text, "error_logs")  # also writes to review.log
    close_logging()                       # restore stdout, close files
"""

import os
import sys
from typing import Optional, TextIO


class _TeeWriter:
    """Write to both the original stream and a log file."""

    def __init__(self, original: TextIO, log_file: TextIO):
        self._original = original
        self._log_file = log_file

    def write(self, text: str):
        self._original.write(text)
        if self._log_file and not self._log_file.closed:
            self._log_file.write(text)
            self._log_file.flush()

    def flush(self):
        self._original.flush()
        if self._log_file and not self._log_file.closed:
            self._log_file.flush()

    def __getattr__(self, name):
        return getattr(self._original, name)


class FoamAgentLogger:
    """Singleton logger that tees stdout to workflow.log and provides review.log."""

    _instance: Optional["FoamAgentLogger"] = None

    def __init__(self):
        self._workflow_file: Optional[TextIO] = None
        self._review_file: Optional[TextIO] = None
        self._original_stdout: Optional[TextIO] = None
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "FoamAgentLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def initialized(self) -> bool:
        return self._initialized

    def setup(self, output_dir: str) -> None:
        """Initialize log files and redirect stdout to tee."""
        if self._initialized:
            return
        os.makedirs(output_dir, exist_ok=True)

        self._workflow_file = open(os.path.join(output_dir, "workflow.log"), "w")
        self._review_file = open(os.path.join(output_dir, "review.log"), "w")

        self._original_stdout = sys.stdout
        sys.stdout = _TeeWriter(self._original_stdout, self._workflow_file)
        self._initialized = True

    def close(self) -> None:
        """Close log files and restore stdout."""
        if self._original_stdout is not None:
            sys.stdout = self._original_stdout
            self._original_stdout = None
        if self._workflow_file and not self._workflow_file.closed:
            self._workflow_file.close()
            self._workflow_file = None
        if self._review_file and not self._review_file.closed:
            self._review_file.close()
            self._review_file = None
        self._initialized = False

    def log_review(self, message: str, tag: str) -> None:
        """Log a message with XML tag to stdout (→ workflow.log via tee) AND review.log."""
        output = f"<{tag}>\n{message}\n</{tag}>"
        print(output)
        if self._review_file and not self._review_file.closed:
            self._review_file.write(output + "\n")
            self._review_file.flush()


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

def setup_logging(output_dir: str) -> None:
    """Initialize logging to output_dir. Call once after case_dir is created."""
    FoamAgentLogger.get_instance().setup(output_dir)


def close_logging() -> None:
    """Close log files and restore stdout."""
    FoamAgentLogger.get_instance().close()


def log_review(message: str, tag: str) -> None:
    """Log to stdout + workflow.log + review.log, wrapped in <tag>...</tag>."""
    FoamAgentLogger.get_instance().log_review(message, tag)
