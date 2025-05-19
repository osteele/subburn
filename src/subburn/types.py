"""Common types used across subburn modules."""

from dataclasses import dataclass


@dataclass
class Segment:
    """A segment of transcribed text with timing information."""

    start: float
    end: float
    text: str
    translation: str | None = None  # Optional English translation
