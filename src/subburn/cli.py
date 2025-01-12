#!/usr/bin/env python3

import mimetypes
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Sequence

import click
import openai
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)

console = Console()


def format_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    td = timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    seconds = td.seconds % 60
    milliseconds = round(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def convert_to_cjk_punctuation(text: str) -> str:
    """Convert ASCII punctuation to CJK punctuation for Chinese text."""
    # Only convert if the text contains Chinese characters
    if not any(0x4E00 <= ord(c) <= 0x9FFF for c in text):
        return text
    
    replacements = {
        ", ": "，",
        "! ": "！",
        "? ": "？",
        ": ": "：",
        "; ": "；",
        ". ": "。",
        ",": "，",
        "!": "！",
        "?": "？",
        ":": "：",
        ";": "；",
        ".": "。",
    }
    result = text
    for ascii_char, cjk_char in replacements.items():
        result = result.replace(ascii_char, cjk_char)
    return result


def create_srt_from_segments(segments: list) -> str:
    """Create SRT content from Whisper segments."""
    srt_content = []
    for i, segment in enumerate(segments, 1):
        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        text = convert_to_cjk_punctuation(segment.text.strip())
        srt_content.extend([
            str(i),
            f"{start} --> {end}",
            text,
            ""
        ])
    return "\n".join(srt_content)


def transcribe_audio(audio_path: Path, progress: Progress, task_id: int) -> Path:
    """Transcribe audio using OpenAI Whisper API."""
    if "OPENAI_API_KEY" not in os.environ:
        raise click.ClickException(
            "OPENAI_API_KEY environment variable not set. "
            "Please provide an SRT file or set OPENAI_API_KEY for automatic transcription."
        )

    progress.update(task_id, description="Transcribing audio with Whisper")
    client = openai.OpenAI()
    
    try:
        with open(audio_path, "rb") as audio:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
    except Exception as e:
        raise click.ClickException(f"Whisper transcription failed: {str(e)}")
    
    # Create SRT file in same directory as audio
    srt_path = audio_path.with_suffix(".srt")
    srt_content = create_srt_from_segments(response.segments)
    
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    
    progress.update(task_id, description="Transcription complete", advance=100)
    return srt_path


@dataclass
class InputFiles:
    audio: Path | None = None
    video: Path | None = None
    subtitle: Path | None = None
    image: Path | None = None


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


def collect_input_files(files: list[Path]) -> InputFiles:
    """Classify input files and validate the combination."""
    result = InputFiles()
    for file in files:
        file_type = classify_file(file)
        if file_type == "audio" and not result.audio:
            result.audio = file
        elif file_type == "video" and not result.video:
            result.video = file
        elif file_type == "subtitle" and not result.subtitle:
            result.subtitle = file
        elif file_type == "image" and not result.image:
            result.image = file
        else:
            raise click.BadParameter(f"Duplicate or conflicting file type: {file}")
    
    # Validate combination
    if result.audio and result.video:
        raise click.BadParameter("Cannot use both audio and video files")
    if not (result.audio or result.video):
        raise click.BadParameter("No audio or video file provided")
    if result.video and result.image:
        raise click.BadParameter("Cannot use both video and image files")
    
    return result


def compute_output_path(input_files: InputFiles) -> Path:
    """Compute output path from input files."""
    source = input_files.video or input_files.audio
    if not source:
        raise click.BadParameter("No source file found")
    return source.with_suffix(".mov")


def get_audio_duration(audio_path: str, progress: Progress, task_id: int) -> float:
    """Get the duration of an audio file in seconds."""
    progress.update(task_id, description="Reading audio file")
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    progress.update(task_id, advance=100)
    return float(result.stdout.strip())


def escape_path(path: Path) -> str:
    """Escape a path for FFmpeg filters."""
    # Replace backslashes with forward slashes and escape special characters
    return str(path.resolve()).replace("\\", "/").replace("'", "'\\''")


def run_ffmpeg_with_progress(cmd: Sequence[str | Path], progress: Progress, task_id: int) -> None:
    """Run ffmpeg command with progress indication."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    
    if not process.stderr:
        raise click.ClickException("Failed to start FFmpeg process")

    progress.update(task_id, description="Initializing encoder")
    duration = None
    started = False
    error_lines = []
    
    while True:
        line = process.stderr.readline()
        if not line:
            break
        
        # Collect error messages
        if "Error" in line or "error" in line or "failed" in line:
            error_lines.append(line.strip())
        
        # Show different initialization stages
        if not started:
            if "Input #0" in line:
                progress.update(task_id, description="Reading input files")
            elif "Stream mapping" in line:
                progress.update(task_id, description="Setting up streams")
            elif "Press [q] to stop" in line:
                progress.update(task_id, description="Starting encode")
                started = True
        
        # Try to get duration if we don't have it yet
        if not duration and "Duration: " in line:
            try:
                duration_str = line.split("Duration: ")[1].split(",")[0].strip()
                h, m, s = map(float, duration_str.split(":"))
                duration = h * 3600 + m * 60 + s
            except (IndexError, ValueError):
                pass
        
        if "time=" in line:
            # Extract time progress
            try:
                time_str = line.split("time=")[1].split()[0]
                h, m, s = map(float, time_str.split(":"))
                current_time = h * 3600 + m * 60 + s
                
                if duration:
                    progress.update(task_id, 
                                  description="Encoding video",
                                  completed=current_time,
                                  total=duration)
            except (IndexError, ValueError):
                pass
    
    if process.wait() != 0:
        error_msg = "\n".join(error_lines) if error_lines else "Unknown FFmpeg error"
        cmd_str = " ".join(str(x) for x in cmd)
        raise click.ClickException(f"FFmpeg processing failed:\n{error_msg}\n\nCommand:\n{cmd_str}")


def open_file(path: Path) -> None:
    """Open a file with the default system application."""
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=True)
    elif sys.platform == "win32":
        subprocess.run(["start", str(path)], check=True, shell=True)
    else:
        subprocess.run(["xdg-open", str(path)], check=True)


@click.command()
@click.argument("files", type=click.Path(exists=True, path_type=Path), nargs=-1, required=True)
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output file path")
@click.option("--width", default=1920, help="Output video width")
@click.option("--height", default=1080, help="Output video height")
@click.option("--open", is_flag=True, help="Open the output file when done")
@click.option("--whisper/--no-whisper", default=True, help="Use Whisper for automatic transcription if no SRT file is provided")
def main(files: tuple[Path, ...], output: Path | None, width: int, height: int, open: bool, whisper: bool) -> None:
    """Create a video with burnt-in subtitles.

    Perfect for language learning: combine audio files with their transcripts into
    study materials. You can provide the files in any order - the script will
    automatically detect audio, video, subtitle, and image files.
    
    If no subtitle file is provided and OPENAI_API_KEY is set in the environment,
    it will automatically transcribe the audio using OpenAI's Whisper API.
    
    Examples:
    
        Create a video from an audio file and subtitles:
            subburn audio.mp3 subtitles.srt
        
        Create a video with automatic transcription:
            subburn audio.mp3
        
        Add a background image:
            subburn audio.mp3 subtitles.srt background.jpg
        
        Add subtitles to an existing video:
            subburn video.mp4 subtitles.srt
    """
    input_files = collect_input_files(list(files))
    output_path = output or compute_output_path(input_files)
    
    progress_columns = (
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    )
    
    with Progress(*progress_columns, console=console) as progress:
        setup_task = progress.add_task("Setting up...", total=100)
        
        # Use Whisper if no subtitle file is provided
        if not input_files.subtitle and whisper and (input_files.audio or input_files.video):
            source = input_files.audio or input_files.video
            input_files.subtitle = transcribe_audio(source, progress, setup_task)
            console.print(f"[green]Created transcript:[/] {input_files.subtitle}")
        elif not input_files.subtitle:
            raise click.BadParameter(
                "No subtitle file provided. Either provide an SRT file or set OPENAI_API_KEY "
                "for automatic transcription."
            )
        
        if input_files.audio:
            # Get audio duration
            duration = get_audio_duration(str(input_files.audio), progress, setup_task)
            
            # Combine everything using ffmpeg
            encoding_task = progress.add_task("Processing video...", total=100)
            
            # Build the input sources
            inputs = []
            if input_files.image:
                # Use the image file directly
                inputs.extend(["-loop", "1", "-i", str(input_files.image)])
            else:
                # Create a black background using lavfi
                inputs.extend([
                    "-f", "lavfi",
                    "-i", f"color=c=black:s={width}x{height}:r=25:d={duration}"
                ])
            
            # Add audio input
            inputs.extend(["-i", str(input_files.audio)])
            
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-vf", f"subtitles={escape_path(input_files.subtitle)}:force_style='Fontsize=24'",
                "-c:v", "libx264",
                "-tune", "stillimage",
                "-c:a", "aac",
                "-shortest",
                str(output_path)
            ]
            run_ffmpeg_with_progress(cmd, progress, encoding_task)
        else:
            # Process video with subtitles
            encoding_task = progress.add_task("Processing video...", total=100)
            cmd = [
                "ffmpeg", "-y",
                "-i", str(input_files.video),
                "-vf", f"subtitles={escape_path(input_files.subtitle)}:force_style='Fontsize=24'",
                "-c:v", "libx264",
                "-c:a", "aac",
                str(output_path)
            ]
            run_ffmpeg_with_progress(cmd, progress, encoding_task)
    
    console.print(f"[green]Created video:[/] {output_path}")
    
    if open:
        open_file(output_path)


if __name__ == "__main__":
    main()
