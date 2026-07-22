"""Rotating JSONL logger for "Chat with TrailBuddy" interactions.

Each chat turn is written as a single JSON object per line so logs are easy to
append, rotate, and parse without introducing a new database table or
dependencies. The raw user prompt is never stored; only a SHA-256 hash and the
character length are kept for privacy.
"""
import hashlib
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config


# Default max size per rotated log file (5 MB) and number of backups to keep.
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_BACKUP_COUNT = 3

_logger: logging.Logger | None = None


def _get_logger(
    log_path: Path | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
) -> logging.Logger:
    """Return a configured JSONL logger, creating the file/directory if needed."""
    global _logger
    if _logger is not None:
        return _logger

    path = Path(log_path) if log_path else Path(config.CHAT_LOG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("trailbuddy_chat_logger")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # avoid double logging to root handlers

    handler = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)

    _logger = logger
    return _logger


def _hash_prompt(prompt: str) -> str:
    """Return a stable SHA-256 hash of the prompt for correlation without
    storing the raw text.
    """
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def log_chat_interaction(
    *,
    question: str,
    input_tokens: int,
    output_tokens: int,
    tools_called: bool,
    tool_names: list[str],
    latency_ms: int,
    model: str = "unknown",
    extra: dict[str, Any] | None = None,
) -> None:
    """Write a single chat interaction record to the rotating JSONL log.

    Args:
        question: The user's raw chat input. Only a hash and length are stored.
        input_tokens: Total input tokens consumed across all LLM invocations.
        output_tokens: Total output tokens generated across all LLM invocations.
        tools_called: Whether any tool was invoked during the turn.
        tool_names: Ordered list of unique tool names that were called.
        latency_ms: End-to-end latency from user input to final response, in ms.
        model: Name of the LLM model used (defaults to "unknown").
        extra: Optional additional fields to include in the log record.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_hash": _hash_prompt(question),
        "prompt_length": len(question),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "tools_called": tools_called,
        "tools": tool_names,
        "latency_ms": latency_ms,
        "model": model,
    }
    if extra:
        record.update(extra)

    logger = _get_logger()
    logger.info(json.dumps(record, ensure_ascii=True, sort_keys=True))


def reset_logger() -> None:
    """Close and reset the singleton logger. Useful in tests."""
    global _logger
    if _logger is not None:
        for handler in _logger.handlers[:]:
            handler.close()
            _logger.removeHandler(handler)
        _logger = None
