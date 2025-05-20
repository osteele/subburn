"""Common types used across subburn modules."""

from dataclasses import dataclass

import click


@dataclass
class Segment:
    """A segment of transcribed text with timing information."""

    start: float
    end: float
    text: str
    translation: str | None = None  # Optional English translation


@dataclass
class SubtitleOptions:
    """Subtitle display and styling configuration."""

    # Display options
    show_pinyin: bool = False
    show_translation: bool = False

    # Font settings
    font_name: str | None = None
    original_font_size: int = 28
    pinyin_font_size: int = 22
    translation_font_size: int = 22

    # Color settings (hex format without # prefix)
    original_color: str = "FFFFFF"  # White
    pinyin_color: str = "00FFFF"  # Cyan
    translation_color: str = "7FFF7F"  # Light green


@dataclass
class MovieConfig:
    """Configuration for movie creation."""

    # Subtitle options
    subtitle_options: SubtitleOptions

    # Video dimensions
    width: int = 1024
    height: int = 1024

    # Video options
    video_quality: str = "medium"  # ffmpeg preset
    crf: int = 23  # quality level (lower = better)


class OpenAIKeyException(click.ClickException):
    """Exception raised when the OpenAI API key is not set."""

    def __init__(self, feature_name: str):
        message = f"OPENAI_API_KEY environment variable not set. Please set it to use {feature_name} features."
        super().__init__(message)

    def show(self, file=None):
        """Enhanced error display with additional help information."""
        message = self.format_message()
        click.echo(f"\nError: {message}", err=True)
        click.echo("\nGet your API key from https://platform.openai.com/account/api-keys", err=True)
        click.echo("Then set it as an environment variable:", err=True)
        click.echo("  export OPENAI_API_KEY=your-api-key", err=True)
