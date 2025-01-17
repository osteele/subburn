"""Common types used across subburn modules."""

from typing import TypedDict


class TranscriptionSegment(TypedDict):
    """A segment of transcribed text with timing information."""

    start: float
    end: float
    text: str


# This is the same as TranscriptionSegment, just aliased for historical reasons
Segment = TranscriptionSegment
