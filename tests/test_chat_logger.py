"""Unit tests for the chat interaction JSONL logger."""
import json
import tempfile
from pathlib import Path

import pytest

import services.chat_logger as chat_logger
from services.chat_logger import log_chat_interaction


@pytest.fixture
def temp_log_path():
    """Provide a temporary log file and ensure the logger is reset afterwards."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "chat_logs.jsonl"
        chat_logger._logger = None
        yield path
        chat_logger.reset_logger()


def test_log_chat_interaction_writes_valid_json(temp_log_path):
    """A logged interaction should be valid JSON with all expected fields."""
    chat_logger._get_logger(log_path=temp_log_path)

    log_chat_interaction(
        question="How many hikes did I do this year?",
        input_tokens=512,
        output_tokens=128,
        tools_called=True,
        tool_names=["query_hikes_db"],
        latency_ms=1234,
        model="mistral-nemo:12b",
    )

    lines = temp_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["prompt_length"] == len("How many hikes did I do this year?")
    assert record["input_tokens"] == 512
    assert record["output_tokens"] == 128
    assert record["tools_called"] is True
    assert record["tools"] == ["query_hikes_db"]
    assert record["latency_ms"] == 1234
    assert record["model"] == "mistral-nemo:12b"
    assert "timestamp" in record
    assert "prompt_hash" in record
    # Raw prompt should never appear in the log.
    assert "How many hikes" not in lines[0]


def test_prompt_hash_is_stable(temp_log_path):
    """The same question must always produce the same hash."""
    chat_logger._get_logger(log_path=temp_log_path)

    log_chat_interaction(
        question="What was my longest hike?",
        input_tokens=10,
        output_tokens=5,
        tools_called=False,
        tool_names=[],
        latency_ms=100,
    )
    log_chat_interaction(
        question="What was my longest hike?",
        input_tokens=10,
        output_tokens=5,
        tools_called=False,
        tool_names=[],
        latency_ms=100,
    )

    lines = temp_log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["prompt_hash"] == second["prompt_hash"]


def test_extra_fields_are_included(temp_log_path):
    """Optional extra fields should be serialized into the record."""
    chat_logger._get_logger(log_path=temp_log_path)

    log_chat_interaction(
        question="Hello",
        input_tokens=1,
        output_tokens=1,
        tools_called=False,
        tool_names=[],
        latency_ms=50,
        extra={"grounded": True, "retry_count": 0},
    )

    record = json.loads(temp_log_path.read_text(encoding="utf-8").strip().splitlines()[0])
    assert record["grounded"] is True
    assert record["retry_count"] == 0
