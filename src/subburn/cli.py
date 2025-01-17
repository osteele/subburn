#!/usr/bin/env python3

import builtins
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
from . import image_gen

console = Console()

def debug_print(verbose: bool, *args, **kwargs):
    """Print only if verbose mode is enabled."""
    if verbose:
        print(*args, **kwargs)

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
        # Handle both dictionary and TranscriptionSegment objects
        if hasattr(segment, 'start'):
            start = format_timestamp(float(segment.start))
            end = format_timestamp(float(segment.end))
            text = convert_to_cjk_punctuation(segment.text.strip())
        else:
            start = format_timestamp(float(segment["start"]))
            end = format_timestamp(float(segment["end"]))
            text = convert_to_cjk_punctuation(segment["text"].strip())
        srt_content.extend([
            str(i),
            f"{start} --> {end}",
            text,
            ""
        ])
    return "\n".join(srt_content)


def create_image_list_file(image_timestamps: dict[float, Path], temp_dir: Path, verbose: bool = False) -> Path:
    """Create a file listing images and their timestamps for FFmpeg."""
    image_list_path = temp_dir / "images.txt"
    
    # Sort timestamps to ensure proper ordering
    sorted_entries = sorted(image_timestamps.items())
    debug_print(verbose, f"Creating image list with {len(sorted_entries)} images")
    
    with open(image_list_path, "w") as f:
        # Write concat file header
        f.write("ffconcat version 1.0\n\n")
        
        for i, (timestamp, image_path) in enumerate(sorted_entries):
            # For the first image, start at 0
            start_time = 0 if i == 0 else timestamp
            # End time is the start of the next image or None for the last image
            end_time = sorted_entries[i + 1][0] if i < len(sorted_entries) - 1 else None
            
            if end_time is None:
                # For the last image, use a duration of 5 seconds
                f.write(f"file {image_path}\n")
                f.write("duration 5\n")
                debug_print(verbose, f"Image {i}: {image_path} (final image, duration: 5s)")
            else:
                duration = end_time - start_time
                f.write(f"file {image_path}\n")
                f.write(f"duration {duration}\n")
                debug_print(verbose, f"Image {i}: {image_path} (duration: {duration}s)")
            f.write("\n")
    
    if verbose:
        # Print the contents of the file for debugging
        debug_print(verbose, "\nContents of image list file:")
        with open(image_list_path) as f:
            debug_print(verbose, f.read())
    
    return image_list_path


def transcribe_audio(audio_path: Path, progress: Progress, task_id: int) -> tuple[Path, list]:
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
    return srt_path, response.segments


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
    """Compute output path based on input files."""
    base = input_files.audio or input_files.video
    return base.with_suffix(".mp4")  # Always use .mp4 extension for better compatibility


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
    return str(path).replace(":", "\\:")


def run_ffmpeg_with_progress(cmd: Sequence[str | Path], progress: Progress, task_id: int):
    """Run ffmpeg command with progress indication."""
    try:
        process = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        progress.update(task_id, description="Initializing encoder")
        
        for line in process.stderr:
            if "frame=" in line:
                # Extract frame number and fps
                frame_match = line.split("frame=")[1].split()[0]
                fps_match = line.split("fps=")[1].split()[0]
                
                try:
                    frame = int(frame_match)
                    fps = float(fps_match)
                    if fps > 0:
                        progress.update(task_id, description=f"Encoding at {fps:.1f} fps")
                except ValueError:
                    continue
        
        if process.wait() != 0:
            error_output = process.stderr.read() if process.stderr else "No error output"
            raise click.ClickException(
                f"FFmpeg processing failed:\n{error_output}\n\nCommand:\n{' '.join(str(x) for x in cmd)}"
            )
        
        progress.update(task_id, description="Encoding complete", advance=100)
        
    except subprocess.CalledProcessError as e:
        raise click.ClickException(f"FFmpeg processing failed: {e}")


def open_file_with_app(path: Path):
    """Open a file with the default system application."""
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", path])


@click.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output file path")
@click.option("--width", type=int, default=1024, help="Width of output video")
@click.option("--height", type=int, default=1024, help="Height of output video")
@click.option("--open-file", is_flag=True, help="Open the output file after creation")
@click.option("--whisper", is_flag=True, help="Force using Whisper for transcription")
@click.option("--generate-images", is_flag=True, help="Generate images for each segment using DALL-E")
@click.option("--image-style", default="A minimalist, elegant scene", help="Style prompt for generated images")
@click.option("--verbose", is_flag=True, help="Show detailed progress information")
def main(
    files: tuple[Path, ...],
    output: Path | None,
    width: int = 1024,
    height: int = 1024,
    open_file: bool = False,
    whisper: bool = False,
    generate_images: bool = False,
    image_style: str = "A minimalist, elegant scene",
    verbose: bool = False,
):
    """Create a video with burnt-in subtitles."""
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Processing", total=100)
            
            # Collect and validate input files
            input_files = collect_input_files([Path(f) for f in files])
            output_path = output or compute_output_path(input_files)
            
            # Get or create subtitle file
            if not input_files.subtitle and not whisper:
                input_files.subtitle = input_files.audio.with_suffix(".srt")
                if not input_files.subtitle.exists():
                    whisper = True
            
            # Initialize variables
            segments = None
            image_timestamps = None
            
            if whisper:
                debug_print(verbose, "Starting transcription...")
                if not input_files.audio:
                    raise click.BadParameter("Cannot transcribe video files yet")
                input_files.subtitle, segments = transcribe_audio(
                    input_files.audio,
                    progress,
                    task_id,
                )
                debug_print(verbose, f"Transcription complete. Generated {len(segments) if segments else 0} segments")
                
                # Generate images if requested
                if generate_images:
                    if not segments:
                        debug_print(verbose, "No segments available for image generation")
                    else:
                        debug_print(verbose, f"Generating images for {len(segments)} segments...")
                        image_timestamps = image_gen.generate_images_for_segments(segments, image_style, progress)
                        if image_timestamps:
                            debug_print(verbose, f"Generated {len(image_timestamps)} images")
                        else:
                            debug_print(verbose, "No images were generated")
                elif verbose:
                    debug_print(verbose, "Image generation not requested")
            else:
                debug_print(verbose, "Using existing subtitle file:", input_files.subtitle)
                if generate_images:
                    debug_print(verbose, "Reading existing subtitle file for image generation...")
                    # Read the subtitle file and create segments
                    with builtins.open(input_files.subtitle, 'r', encoding='utf-8') as f:
                        srt_content = f.read()
                    # Parse SRT content into segments
                    segments = []
                    current_segment = {}
                    for line in srt_content.strip().split('\n'):
                        line = line.strip()
                        if not line:
                            if current_segment:
                                segments.append(current_segment)
                                current_segment = {}
                            continue
                        if '-->' in line:
                            start, end = line.split('-->')
                            start = start.strip().replace(',', '.')
                            end = end.strip().replace(',', '.')
                            current_segment['start'] = float(start.split(':')[0]) * 3600 + float(start.split(':')[1]) * 60 + float(start.split(':')[2])
                            current_segment['end'] = float(end.split(':')[0]) * 3600 + float(end.split(':')[1]) * 60 + float(end.split(':')[2])
                        elif not line[0].isdigit():  # Skip segment numbers
                            current_segment['text'] = line
                    if current_segment:
                        segments.append(current_segment)
                    
                    if segments:
                        debug_print(verbose, f"Found {len(segments)} segments in subtitle file")
                        debug_print(verbose, "Generating images...")
                        image_timestamps = image_gen.generate_images_for_segments(segments, image_style, progress)
                        if image_timestamps:
                            debug_print(verbose, f"Generated {len(image_timestamps)} images")
                        else:
                            debug_print(verbose, "No images were generated")
                    else:
                        debug_print(verbose, "No segments found in subtitle file")
            
            # Get audio duration for background generation
            duration = get_audio_duration(
                str(input_files.audio or input_files.video),
                progress,
                task_id,
            )
            
            # Create temporary directory for working files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Build ffmpeg command
                cmd = ["ffmpeg", "-y"]
                
                # Add background (color or image)
                if image_timestamps and len(image_timestamps) > 0:
                    # Create a list file for the image sequence
                    image_list = create_image_list_file(image_timestamps, temp_path, verbose)
                    cmd.extend([
                        "-f", "concat",
                        "-safe", "0",
                        "-i", str(image_list),
                    ])
                    # Add audio input
                    cmd.extend(["-i", str(input_files.audio or input_files.video)])
                    
                    # Set up filter complex for image sequence
                    filter_complex = [
                        # Scale and pad images to match output dimensions
                        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease",
                        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[bg]",
                        # Add subtitles
                        f"[bg]subtitles={escape_path(input_files.subtitle)}:force_style='Fontsize=24'[v]"
                    ]
                    
                    # Add filter complex and mapping
                    cmd.extend([
                        "-filter_complex", ",".join(filter_complex),
                        "-map", "[v]",
                        "-map", "1:a",
                    ])
                elif input_files.image:
                    cmd.extend(["-i", str(input_files.image)])
                    cmd.extend(["-i", str(input_files.audio or input_files.video)])
                    cmd.extend([
                        "-vf", f"subtitles={escape_path(input_files.subtitle)}:force_style='Fontsize=24'",
                    ])
                else:
                    cmd.extend([
                        "-f", "lavfi",
                        "-i", f"color=c=black:s={width}x{height}:r=25:d={duration}",
                        "-i", str(input_files.audio or input_files.video),
                        "-vf", f"subtitles={escape_path(input_files.subtitle)}:force_style='Fontsize=24'",
                    ])
                
                # Add output options
                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "medium",  # Balance between encoding speed and quality
                    "-crf", "23",  # Reasonable quality setting
                    "-profile:v", "high",  # High profile for better quality
                    "-level:v", "4.0",  # Compatible level for most devices
                    "-pix_fmt", "yuv420p",  # Required for QuickTime compatibility
                    "-movflags", "+faststart",  # Enable streaming-friendly layout
                    "-c:a", "aac",
                    "-b:a", "192k",  # Good quality audio bitrate
                    "-shortest",
                    str(output_path),
                ])
                
                # Print the full command for debugging
                debug_print(verbose, "\nFFmpeg command:")
                debug_print(verbose, " ".join(str(x) for x in cmd))
                
                # Run ffmpeg
                run_ffmpeg_with_progress(cmd, progress, task_id)
            
            if open_file:
                open_file_with_app(output_path)
        
        console.print(f"[green]Created video:[/] {output_path}")
    except ValueError as e:
        if "OPENAI_API_KEY" in str(e) and generate_images:
            console.print("[red]Error:[/] OpenAI API key is required for image generation.")
            console.print("Get your API key from https://platform.openai.com/account/api-keys")
            console.print("Then set it as an environment variable:")
            console.print("  export OPENAI_API_KEY=your-api-key")
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
