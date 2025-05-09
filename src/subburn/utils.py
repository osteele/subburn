"""Utility functions for subburn."""

import mimetypes
import os
import subprocess
import sys
from pathlib import Path

import click


class InputFiles:
    """Container for input files."""

    def __init__(self) -> None:
        self.audio: Path | None = None
        self.video: Path | None = None
        self.image: Path | None = None
        self.subtitle: Path | None = None


def format_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace(".", ",")


def convert_to_cjk_punctuation(text: str) -> str:
    """Convert ASCII punctuation to CJK punctuation for Chinese text."""
    # Only convert if the text contains Chinese characters
    if not any("\u4e00" <= c <= "\u9fff" for c in text):
        return text

    # Map of ASCII punctuation to CJK punctuation
    punctuation_map = {
        ",": "，",
        ".": "。",
        "!": "！",
        "?": "？",
        ":": "：",
        ";": "；",
        "(": "（",
        ")": "）",
        "[": "【",
        "]": "】",
        '"': '"',
        "'": "'",
    }

    for ascii_punct, cjk_punct in punctuation_map.items():
        text = text.replace(ascii_punct, cjk_punct)

    return text


def compute_output_path(input_files: InputFiles) -> Path:
    """Compute output path based on input files."""
    base_path = input_files.audio or input_files.video
    if not base_path:
        raise click.BadParameter("No input file found")
    return base_path.with_suffix(".mp4")


def collect_input_files(files: list[Path]) -> InputFiles:
    """Collect and validate input files."""
    input_files = InputFiles()

    for file in files:
        if not file.exists():
            raise click.BadParameter(f"File not found: {file}")

        file_type = classify_file(file)
        if file_type == "audio":
            input_files.audio = file
        elif file_type == "video":
            input_files.video = file
        elif file_type == "image":
            input_files.image = file
        elif file_type == "subtitle":
            input_files.subtitle = file
        else:
            raise click.BadParameter(f"Unsupported file type: {file}")

    return input_files


def is_audio_only_container(path: Path) -> bool:
    """Check if a video container only has audio streams."""
    try:
        # Run ffprobe to check for stream types
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Get list of stream types
        streams = result.stdout.strip().split("\n")

        # If we only have audio streams and no video streams, it's an audio-only container
        return "audio" in streams and "video" not in streams
    except subprocess.SubprocessError:
        # If ffprobe fails, we'll fall back to regular mimetype detection
        return False


def classify_file(path: Path) -> str:
    """Classify a file based on its mimetype and extension."""
    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type:
        if path.suffix.lower() == ".srt":
            return "subtitle"
        raise click.BadParameter(f"Could not determine type of file: {path}")

    main_type = mime_type.split("/")[0]
    if main_type == "audio":
        return "audio"
    elif main_type == "video":
        # Check if this is actually an audio-only container (like MP4 with only audio)
        if is_audio_only_container(path):
            return "audio"
        return "video"
    elif main_type == "image":
        return "image"
    elif path.suffix.lower() == ".srt":
        return "subtitle"
    raise click.BadParameter(f"Unsupported file type: {path} ({mime_type})")


def escape_path(path: Path) -> str:
    """Escape path for use in FFmpeg command."""
    return str(path).replace(":", "\\\\:")


def find_cjk_compatible_font() -> str:
    """Find an installed font with CJK support.

    Attempts to find a font installed on the system that supports CJK characters.
    Returns a fallback font if no specific CJK font is found.

    Returns:
        Name of an installed font with CJK support
    """
    import subprocess
    import sys

    # On macOS, directly test for known fonts that have good CJK support
    if sys.platform == "darwin":
        # Directly check for Arial Unicode MS which is known to work well
        import os

        if os.path.exists("/Library/Fonts/Arial Unicode.ttf") or os.path.exists(
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
        ):
            return "Arial Unicode MS"

        # Directly check for common macOS CJK fonts
        try:
            for mac_font in ["Arial Unicode MS", "Hiragino Sans GB", "PingFang SC"]:
                result = subprocess.run(["fc-list", f":{mac_font}"], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    return mac_font
        except (FileNotFoundError, subprocess.SubprocessError):
            # Fall back to the macOS default below
            pass

    # Try to find any installed font that supports Chinese
    try:
        # Get all fonts that support Chinese characters
        result = subprocess.run(["fc-list", ":lang=zh"], capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            # Extract the font name from the first available CJK-supporting font
            first_line = result.stdout.split("\n")[0]
            if ":" in first_line:
                font_name = first_line.split(":")[1].split(",")[0].strip()
                if font_name:
                    return font_name
    except (FileNotFoundError, subprocess.SubprocessError):
        # fc-list command not available or failed, fallback to platform detection
        pass

    # Platform-specific defaults if all above methods fail
    if sys.platform == "darwin":  # macOS
        return "Arial Unicode MS"
    elif sys.platform == "win32":  # Windows
        return "Microsoft YaHei"
    else:  # Linux and others
        return "Noto Sans CJK"


def create_subtitles_filter(subtitle_path: Path, font_name: str | None = None, font_size: int = 24) -> str:
    """Create properly formatted FFmpeg subtitles filter string.

    This handles proper escaping of paths and font names for the FFmpeg subtitles filter.

    Args:
        subtitle_path: Path to the subtitle file
        font_name: Name of the font to use, or None to auto-detect a CJK compatible font
        font_size: Font size to use

    Returns:
        Properly formatted FFmpeg subtitles filter string
    """
    escaped_path = escape_path(subtitle_path)

    # If no font specified, find a CJK compatible font
    if not font_name:
        font_name = find_cjk_compatible_font()

    # For handling font names in FFmpeg subtitles filter
    # Use a straightforward approach with quotes - this works with LibASS in FFmpeg
    # Also add white text with black outline for better visibility
    style = f"Fontname={font_name},Fontsize={font_size},PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1"
    return f"subtitles={escaped_path}:force_style='{style}'"


def open_file_with_app(path: Path) -> None:
    """Open a file with the default system application."""
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
