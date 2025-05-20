"""Transcription utilities."""

import logging
import os
import subprocess
from pathlib import Path

import click
import jieba
import openai
from pypinyin import Style, pinyin
from rich.progress import Progress, TaskID

from .translation import contains_chinese, translate_segments
from .types import Segment
from .utils import convert_to_cjk_punctuation, format_timestamp

# Configure jieba logger to suppress default messages
jieba_logger = logging.getLogger('jieba')
jieba_logger.setLevel(logging.ERROR)

# Avoid printing loading message by setting silent mode
jieba.setLogLevel(logging.ERROR)


def generate_pinyin(text: str) -> str:
    """Generate pinyin for Chinese text with word segmentation."""
    # Use jieba to segment the text into words
    words = list(jieba.cut(text))

    result = []
    prev_was_pinyin = False

    for word in words:
        is_pinyin = contains_chinese(word)
        if is_pinyin:
            # Get pinyin for Chinese word, joined without spaces between syllables
            word = "".join(p[0] for p in pinyin(word, style=Style.TONE))

            # Add space before pinyin if previous was also pinyin
            if prev_was_pinyin:
                result.append(" ")
        result.append(word)
        prev_was_pinyin = is_pinyin

    return "".join(result)


def create_srt_from_segments(
    segments: list[Segment], *, add_pinyin: bool = False, add_translation: bool = False
) -> str:
    """Create SRT content from segments with optional pinyin and translation."""
    if not segments:
        return ""

    srt_lines = []
    for i, segment in enumerate(segments, 1):
        start_time = format_timestamp(segment.start)
        end_time = format_timestamp(segment.end)
        text = convert_to_cjk_punctuation(segment.text)

        # Add base text
        lines = [text]

        # Add pinyin if requested and text contains Chinese characters
        if add_pinyin and contains_chinese(text):
            pinyin_text = generate_pinyin(text)
            lines.append(pinyin_text)

        # Add translation if requested and available
        if add_translation and segment.translation is not None:
            lines.append(segment.translation)

        srt_lines.extend(
            [
                str(i),
                f"{start_time} --> {end_time}",
                "\n".join(lines),
                "",  # Empty line between entries
            ]
        )
    return "\n".join(srt_lines)


def get_audio_duration(file_path: str, progress: Progress, task_id: TaskID) -> float:
    """Get duration of audio/video file using ffprobe."""
    progress.update(task_id, description="Getting audio duration")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        duration = float(result.stdout.strip())
        progress.update(task_id, advance=5)
        return duration
    except (subprocess.CalledProcessError, ValueError) as e:
        raise click.ClickException(f"Failed to get audio duration: {e}") from e


def transcribe_audio(
    audio_path: Path,
    progress: Progress,
    task_id: TaskID,
    *,
    pinyin: bool = False,
    translation: bool = False,
) -> tuple[Path, list[Segment]]:
    """Transcribe audio using OpenAI Whisper API with optional translation."""
    if "OPENAI_API_KEY" not in os.environ:
        raise ValueError("OPENAI_API_KEY environment variable not set. Please set it to use transcription features.")

    client = openai.OpenAI()
    progress.update(task_id, description="Transcribing audio", advance=10)

    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
        )

    progress.update(task_id, description="Processing segments", advance=10)

    # Convert OpenAI segments to our format
    segments: list[Segment] = []
    if response.segments is not None:
        for seg in response.segments:
            segment = Segment(
                start=float(seg.start),
                end=float(seg.end),
                text=seg.text,
            )
            segments.append(segment)

    # Add translations if requested
    if translation and segments:
        progress.update(task_id, description="Translating segments", advance=10)
        segments = translate_segments(segments)

    # Create SRT file with pinyin and translation options
    srt_content = create_srt_from_segments(segments, add_pinyin=pinyin, add_translation=translation)
    srt_path = audio_path.with_suffix(".srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    progress.update(task_id, description="Transcription complete", advance=100)
    return srt_path, segments
