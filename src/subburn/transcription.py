"""Transcription utilities."""

import os
import subprocess
from pathlib import Path

import click
import openai
from rich.progress import Progress, TaskID

from .types import TranscriptionSegment
from .utils import convert_to_cjk_punctuation, format_timestamp


def create_srt_from_segments(segments: list[TranscriptionSegment]) -> str:
    """Create SRT content from segments."""
    if not segments:
        return ""

    srt_lines = []
    for i, segment in enumerate(segments, 1):
        start_time = format_timestamp(segment["start"])
        end_time = format_timestamp(segment["end"])
        srt_lines.extend(
            [
                str(i),
                f"{start_time} --> {end_time}",
                convert_to_cjk_punctuation(segment["text"]),
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


def transcribe_audio(audio_path: Path, progress: Progress, task_id: TaskID) -> tuple[Path, list[TranscriptionSegment]]:
    """Transcribe audio using OpenAI Whisper API."""
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

    progress.update(task_id, description="Creating subtitle file", advance=10)

    # Convert OpenAI segments to our format
    segments: list[TranscriptionSegment] = []
    if response.segments is not None:
        for seg in response.segments:
            segments.append(
                TranscriptionSegment(
                    start=float(seg.start),
                    end=float(seg.end),
                    text=seg.text,
                )
            )

    # Create SRT file
    srt_content = create_srt_from_segments(segments)
    srt_path = audio_path.with_suffix(".srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    progress.update(task_id, description="Transcription complete", advance=100)
    return srt_path, segments
