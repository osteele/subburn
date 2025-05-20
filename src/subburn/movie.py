"""Video creation and subtitle rendering."""

import subprocess
import tempfile
from pathlib import Path

import click
from rich.progress import Progress, TaskID

from .types import MovieConfig, SubtitleOptions
from .utils import escape_path, find_cjk_compatible_font


def create_subtitles_filter(subtitle_path: Path, options: SubtitleOptions) -> str:
    """Create properly formatted FFmpeg subtitles filter string.

    Args:
        subtitle_path: Path to the subtitle file
        options: Subtitle display and styling options

    Returns:
        Properly formatted FFmpeg subtitles filter string
    """
    escaped_path = escape_path(subtitle_path)

    # If no font specified, find a CJK compatible font
    font_name = options.font_name if options.font_name else find_cjk_compatible_font()

    # Since SRT format doesn't support different styles for different lines,
    # we'll use ASS format's override tags directly in the subtitle text.
    # The transcription.py module will format the text with these tags.

    # We'll use a simple base style for the subtitles
    style_str = (
        f"Fontname={font_name},Fontsize={options.original_font_size},"
        f"PrimaryColour=&H{options.original_color},BorderStyle=1,Outline=1,Shadow=1"
    )

    return f"subtitles={escaped_path}:force_style='{style_str}'"


def run_ffmpeg_with_progress(cmd: list[str | Path], progress: Progress, task_id: TaskID, verbose: bool = False) -> None:
    """Run ffmpeg command with progress tracking.

    Args:
        cmd: FFmpeg command and arguments
        progress: Progress object for tracking
        task_id: Task ID for progress tracking
        verbose: Whether to print FFmpeg output to console
    """
    progress.update(task_id, description="Processing video")

    # Configure stderr handling based on verbose flag
    stderr_pipe = None if verbose else subprocess.PIPE

    process = subprocess.Popen(
        [str(x) for x in cmd],  # Convert all arguments to strings
        stdout=subprocess.PIPE,  # Always capture stdout
        stderr=stderr_pipe,  # Only pipe stderr if not verbose
        universal_newlines=True,
    )

    # Collect stderr output
    stderr_output = []

    # Only process stderr if we're piping it (not verbose mode)
    if not verbose and process.stderr:
        while True:
            if not process.stderr:
                break

            line = process.stderr.readline()
            if not line:
                break

            # Store stderr output for error reporting
            stderr_output.append(line)

            # Update progress based on ffmpeg output
            if "time=" in line:
                progress.update(task_id, advance=1)

    exit_code = process.wait()
    if exit_code != 0:
        # Format the error output for readability, focusing on the most relevant parts
        if stderr_output:
            error_msg = "\n".join(stderr_output[-20:])  # Show the last 20 lines which usually contain the error
        else:
            error_msg = "FFmpeg error output not captured in verbose mode."
        raise click.ClickException(f"FFmpeg processing failed with exit code {exit_code}:\n\n{error_msg}")

    progress.update(task_id, description="Video processing complete", completed=100)


def create_image_list_file(image_timestamps: dict[float, Path], temp_dir: Path) -> Path:
    """Create a file listing images and their durations for ffmpeg concat."""
    from .debug import debug_print

    image_list_path = temp_dir / "image_list.txt"
    timestamps = sorted(image_timestamps.keys())

    with open(image_list_path, "w") as f:
        for i, start in enumerate(timestamps):
            image_path = image_timestamps[start]
            duration = timestamps[i + 1] - start if i < len(timestamps) - 1 else 5.0

            f.write(f"file '{image_path}'\n")
            f.write(f"duration {duration}\n")
            debug_print("Image {}: {} (duration: {:.2f}s)", i, image_path, duration)

    return image_list_path


def create_movie(
    output_path: Path,
    input_files,  # InputFiles object
    config: MovieConfig,
    image_timestamps: dict[float, Path] | None = None,
    audio_duration: float = 0,
    progress: Progress | None = None,
    task_id: TaskID | None = None,
    verbose: bool = False,
) -> None:
    """Create a movie with the given configuration.

    Args:
        output_path: Path to output movie file
        input_files: Input files object with subtitle, audio/video and optional image
        config: Movie configuration
        image_timestamps: Optional timestamps mapped to image paths
        audio_duration: Duration of audio in seconds
        progress: Progress object for tracking
        task_id: Task ID for progress tracking
        verbose: Whether to print verbose FFmpeg output
    """
    from .debug import debug_print

    # Create temporary directory for working files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Build ffmpeg command
        cmd: list[str | Path] = ["ffmpeg", "-y"]

        # Add background (color, image sequence, or image)
        if image_timestamps and len(image_timestamps) > 0:
            # Create a list file for the image sequence
            image_list = create_image_list_file(image_timestamps, temp_path)
            cmd.extend(
                [
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(image_list),
                ]
            )
            # Add audio input
            cmd.extend(["-i", str(input_files.audio or input_files.video)])

            # Set up filter complex for image sequence
            filter_complex = [
                # Scale and pad images to match output dimensions
                f"[0:v]scale={config.width}:{config.height}:force_original_aspect_ratio=decrease",
                f"pad={config.width}:{config.height}:(ow-iw)/2:(oh-ih)/2[bg]",
                # Add subtitles
                f"[bg]{create_subtitles_filter(input_files.subtitle, config.subtitle_options)}[v]",
            ]

            # Add filter complex and mapping
            cmd.extend(
                [
                    "-filter_complex",
                    ",".join(filter_complex),
                    "-map",
                    "[v]",
                    "-map",
                    "1:a",
                ]
            )
        elif input_files.image:
            cmd.extend(["-i", str(input_files.image)])
            cmd.extend(["-i", str(input_files.audio or input_files.video)])
            cmd.extend(
                [
                    "-vf",
                    create_subtitles_filter(input_files.subtitle, config.subtitle_options),
                ]
            )
        else:
            cmd.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=black:s={config.width}x{config.height}:r=25:d={audio_duration}",
                    "-i",
                    str(input_files.audio or input_files.video),
                    "-vf",
                    create_subtitles_filter(input_files.subtitle, config.subtitle_options),
                ]
            )

        # Add output options
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                config.video_quality,  # Balance between encoding speed and quality
                "-crf",
                str(config.crf),  # Reasonable quality setting
                "-profile:v",
                "high",  # High profile for better quality
                "-level:v",
                "4.0",  # Compatible level for most devices
                "-pix_fmt",
                "yuv420p",  # Required for QuickTime compatibility
                "-movflags",
                "+faststart",  # Enable streaming-friendly layout
                "-c:a",
                "aac",
                "-b:a",
                "192k",  # Good quality audio bitrate
                "-shortest",
                str(output_path),
            ]
        )

        # Print the full command for debugging
        debug_print("\nFFmpeg command:")
        debug_print("{}", " ".join(str(x) for x in cmd))

        # Run ffmpeg
        if progress and task_id:
            run_ffmpeg_with_progress(cmd, progress, task_id, verbose=verbose)
        else:
            # Use subprocess.DEVNULL to suppress output unless verbose is enabled
            stdout = stderr = None if verbose else subprocess.DEVNULL
            subprocess.run([str(x) for x in cmd], stdout=stdout, stderr=stderr, check=True)
