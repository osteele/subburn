"""Command-line interface for subburn."""

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence, cast

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from . import image_gen
from .debug import debug_print, set_debug_level
from .transcription import get_audio_duration, transcribe_audio
from .types import TranscriptionSegment
from .utils import (
    collect_input_files,
    compute_output_path,
    escape_path,
    open_file_with_app,
)

console = Console()


def run_ffmpeg_with_progress(cmd: Sequence[str | Path], progress: Progress, task_id: TaskID) -> None:
    """Run ffmpeg command with progress tracking."""
    progress.update(task_id, description="Processing video")

    try:
        process = subprocess.Popen(
            [str(x) for x in cmd],  # Convert all arguments to strings
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        while True:
            if not process.stderr:
                break

            line = process.stderr.readline()
            if not line:
                break

            # Update progress based on ffmpeg output
            if "time=" in line:
                progress.update(task_id, advance=1)

        if process.wait() != 0:
            raise click.ClickException("FFmpeg processing failed")

        progress.update(task_id, description="Video processing complete", completed=100)
    except Exception as e:
        raise click.ClickException(f"FFmpeg processing failed: {e}")


def create_image_list_file(image_timestamps: dict[float, Path], temp_dir: Path) -> Path:
    """Create a file listing images and their durations for ffmpeg concat."""
    image_list_path = temp_dir / "image_list.txt"
    timestamps = sorted(image_timestamps.keys())

    with open(image_list_path, "w") as f:
        for i, start in enumerate(timestamps):
            image_path = image_timestamps[start]
            if i < len(timestamps) - 1:
                duration = timestamps[i + 1] - start
            else:
                duration = 5.0

            f.write(f"file '{image_path}'\n")
            f.write(f"duration {duration}\n")
            debug_print("Image {}: {} (duration: {:.2f}s)", i, image_path, duration)

    return image_list_path


@click.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output file path")
@click.option("-w", "--width", type=int, default=1024, help="Output video width")
@click.option("-h", "--height", type=int, default=1024, help="Output video height")
@click.option("--open", "should_open", is_flag=True, help="Open the output file when done")
@click.option("--whisper", is_flag=True, help="Force transcription with Whisper")
@click.option("--generate-images", is_flag=True, help="Generate images for each subtitle")
@click.option("--image-style", default="A minimalist, elegant scene", help="Style for generated images")
@click.option("-v", "--verbose", is_flag=True, help="Show debug information")
def main(
    files: tuple[Path, ...],
    output: Path | None,
    width: int = 1024,
    height: int = 1024,
    should_open: bool = False,
    whisper: bool = False,
    generate_images: bool = False,
    image_style: str = "A minimalist, elegant scene",
    verbose: bool = False,
) -> None:
    """Create a video with burnt-in subtitles."""
    # Set debug level based on verbose flag
    set_debug_level(1 if verbose else 0)

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
                if not input_files.audio:
                    raise click.BadParameter("No audio file found")
                input_files.subtitle = input_files.audio.with_suffix(".srt")
                if not input_files.subtitle.exists():
                    whisper = True

            # Initialize variables
            whisper_segments: list[TranscriptionSegment] = []
            image_timestamps: dict[float, Path] = {}

            if whisper:
                debug_print("Starting transcription...")
                if not input_files.audio:
                    raise click.BadParameter("Cannot transcribe video files yet")
                input_files.subtitle, whisper_segments = transcribe_audio(
                    input_files.audio,
                    progress,
                    task_id,
                )
                debug_print("Transcription complete. Generated {} segments", len(whisper_segments))

                # Generate images if requested
                if generate_images:
                    debug_print("Generating images for {} segments...", len(whisper_segments))
                    image_timestamps = image_gen.generate_images_for_segments(
                        cast(list[image_gen.Segment], whisper_segments),
                        image_style,
                        progress,
                    )
                    if image_timestamps:
                        debug_print("Generated {} images", len(image_timestamps))
                    else:
                        debug_print("No images were generated")
                else:
                    debug_print("Image generation not requested")
            else:
                if not input_files.subtitle:
                    raise click.BadParameter("No subtitle file found")
                debug_print("Using existing subtitle file: {}", input_files.subtitle)
                if generate_images:
                    debug_print("Reading existing subtitle file for image generation...")
                    try:
                        with open(input_files.subtitle, "r", encoding="utf-8") as f:
                            srt_content = f.read()
                    except (IOError, OSError) as e:
                        raise click.BadParameter(f"Failed to read subtitle file: {e}")

                    # Parse SRT content into segments
                    parsed_segments: list[TranscriptionSegment] = []
                    current_segment = TranscriptionSegment(
                        start=0.0,
                        end=0.0,
                        text="",
                    )
                    for line in srt_content.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            if current_segment["text"]:
                                parsed_segments.append(current_segment)
                                current_segment = TranscriptionSegment(
                                    start=0.0,
                                    end=0.0,
                                    text="",
                                )
                            continue
                        if "-->" in line:
                            start, end = line.split("-->")
                            start = start.strip().replace(",", ".")
                            end = end.strip().replace(",", ".")
                            current_segment["start"] = (
                                float(start.split(":")[0]) * 3600
                                + float(start.split(":")[1]) * 60
                                + float(start.split(":")[2])
                            )
                            current_segment["end"] = (
                                float(end.split(":")[0]) * 3600
                                + float(end.split(":")[1]) * 60
                                + float(end.split(":")[2])
                            )
                        elif not line.isdigit():  # Skip segment numbers
                            current_segment["text"] = line
                    if current_segment["text"]:
                        parsed_segments.append(current_segment)

                    if parsed_segments:
                        debug_print("Found {} segments in subtitle file", len(parsed_segments))
                        debug_print("Generating images...")
                        image_timestamps = image_gen.generate_images_for_segments(
                            cast(list[image_gen.Segment], parsed_segments),
                            image_style,
                            progress,
                        )
                        if image_timestamps:
                            debug_print("Generated {} images", len(image_timestamps))
                        else:
                            debug_print("No images were generated")
                    else:
                        debug_print("No segments found in subtitle file")

            if not input_files.subtitle:
                raise click.BadParameter("No subtitle file found or created")

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
                cmd: list[str | Path] = ["ffmpeg", "-y"]

                # Add background (color or image)
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
                        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease",
                        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[bg]",
                        # Add subtitles
                        f"[bg]subtitles={escape_path(input_files.subtitle)}:force_style='Fontsize=24'[v]",
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
                            f"subtitles={escape_path(input_files.subtitle)}:force_style='Fontsize=24'",
                        ]
                    )
                else:
                    cmd.extend(
                        [
                            "-f",
                            "lavfi",
                            "-i",
                            f"color=c=black:s={width}x{height}:r=25:d={duration}",
                            "-i",
                            str(input_files.audio or input_files.video),
                            "-vf",
                            f"subtitles={escape_path(input_files.subtitle)}:force_style='Fontsize=24'",
                        ]
                    )

                # Add output options
                cmd.extend(
                    [
                        "-c:v",
                        "libx264",
                        "-preset",
                        "medium",  # Balance between encoding speed and quality
                        "-crf",
                        "23",  # Reasonable quality setting
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
                run_ffmpeg_with_progress(cmd, progress, task_id)

            if should_open:
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
