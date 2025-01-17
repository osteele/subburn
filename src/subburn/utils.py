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
        return "video"
    elif main_type == "image":
        return "image"
    elif path.suffix.lower() == ".srt":
        return "subtitle"
    raise click.BadParameter(f"Unsupported file type: {path} ({mime_type})")


def escape_path(path: Path) -> str:
    """Escape path for use in FFmpeg command."""
    return str(path).replace(":", "\\\\:")


def open_file_with_app(path: Path) -> None:
    """Open a file with the default system application."""
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
