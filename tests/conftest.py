"""Shared test fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_srt() -> str:
    """Return sample SRT content."""
    return """1
00:00:00,000 --> 00:00:02,000
Hello, world!

2
00:00:02,000 --> 00:00:04,000
This is a test."""


@pytest.fixture
def sample_segments() -> list[dict]:
    """Return sample Whisper segments."""
    return [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "Hello, world!"
        },
        {
            "start": 2.0,
            "end": 4.0,
            "text": "This is a test."
        }
    ]
