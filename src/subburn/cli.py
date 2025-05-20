"""Command-line interface for subburn."""

import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, cast

import click
import typer
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
from .types import Segment
from .utils import (
    collect_input_files,
    compute_output_path,
    create_subtitles_filter,
    open_file_with_app,
)

console = Console()
app = typer.Typer()


def run_ffmpeg_with_progress(cmd: Sequence[str | Path], progress: Progress, task_id: TaskID) -> None:
    """Run ffmpeg command with progress tracking."""
    progress.update(task_id, description="Processing video")

    process = subprocess.Popen(
        [str(x) for x in cmd],  # Convert all arguments to strings
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    # Collect stderr output
    stderr_output = []

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
        error_msg = "\n".join(stderr_output[-20:])  # Show the last 20 lines which usually contain the error
        raise click.ClickException(f"FFmpeg processing failed with exit code {exit_code}:\n\n{error_msg}")

    progress.update(task_id, description="Video processing complete", completed=100)


def create_image_list_file(image_timestamps: dict[float, Path], temp_dir: Path) -> Path:
    """Create a file listing images and their durations for ffmpeg concat."""
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


@app.command()
def main(
    files: Annotated[list[Path], typer.Argument(help="Input files")],
    output: Annotated[Path | None, typer.Option("-o", "--output", help="Output file path or directory")] = None,
    width: Annotated[int, typer.Option("-w", "--width", help="Output video width")] = 1024,
    height: Annotated[int, typer.Option("-h", "--height", help="Output video height")] = 1024,
    should_open: Annotated[bool, typer.Option("--open", help="Open the output file when done")] = False,
    whisper: Annotated[bool, typer.Option(help="Force transcription with Whisper")] = False,
    generate_images: Annotated[bool, typer.Option(help="Generate images for each subtitle")] = False,
    image_style: Annotated[str, typer.Option(help="Style for generated images")] = "A minimalist, elegant scene",
    font: Annotated[
        str | None, typer.Option(help="Font to use for subtitles (e.g. 'Arial Unicode MS', 'Hiragino Sans GB')")
    ] = None,
    pinyin: Annotated[bool, typer.Option(help="Add pinyin to Chinese subtitles")] = False,
    translation: Annotated[bool, typer.Option(help="Add English translation to subtitles")] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show debug information")] = False,
) -> None:
    """Create a video with burnt-in subtitles.

    The program automatically detects and uses a font with CJK (Chinese, Japanese, Korean) support.
    You can also specify a specific font with the --font option. Recommended fonts for CJK:
    - macOS: 'Arial Unicode MS', 'Hiragino Sans GB', 'PingFang SC'
    - Windows: 'Microsoft YaHei', 'SimHei', 'MingLiU'
    - Linux: 'Noto Sans CJK', 'WenQuanYi Micro Hei'
    """
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
            
            # Handle output path - check if it's a directory
            if output and output.is_dir():
                output_path = compute_output_path(input_files, output_dir=output)
            else:
                output_path = output or compute_output_path(input_files)

            # Prevent overwriting input files
            if (input_files.audio and output_path.resolve() == input_files.audio.resolve()) or (
                input_files.video and output_path.resolve() == input_files.video.resolve()
            ):
                raise click.UsageError(
                    f"Output file would overwrite input file: {output_path}\n"
                    f"Please specify a different output file using the --output option"
                )

            # Get or create subtitle file
            if not input_files.subtitle and not whisper:
                if not input_files.audio:
                    raise click.BadParameter("No audio file found")
                input_files.subtitle = input_files.audio.with_suffix(".srt")
                if not input_files.subtitle.exists():
                    whisper = True

            # Initialize variables
            whisper_segments: list[Segment] = []
            image_timestamps: dict[float, Path] = {}

            if whisper:
                debug_print("Starting transcription...")
                if not input_files.audio:
                    raise click.BadParameter("Cannot transcribe video files yet")
                input_files.subtitle, whisper_segments = transcribe_audio(
                    input_files.audio,
                    progress,
                    task_id,
                    pinyin=pinyin,
                    translation=translation,
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

                # If we need to process the subtitle file for images, pinyin, or translation
                if generate_images or pinyin or translation:
                    debug_print("Reading existing subtitle file for processing...")
                    try:
                        with open(input_files.subtitle, encoding="utf-8") as f:
                            srt_content = f.read()
                    except OSError as e:
                        raise click.BadParameter(f"Failed to read subtitle file: {e}") from e

                    # Parse SRT content into segments
                    parsed_segments: list[Segment] = []
                    current_segment = Segment(
                        start=0.0,
                        end=0.0,
                        text="",
                    )
                    for line in srt_content.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            if current_segment.text:
                                # Only use the first line of text (the original Chinese)
                                # This handles cases where the SRT already has pinyin/translation
                                first_line = current_segment.text.split("\n")[0]
                                current_segment.text = first_line
                                parsed_segments.append(current_segment)
                                current_segment = Segment(
                                    start=0.0,
                                    end=0.0,
                                    text="",
                                )
                            continue
                        if "-->" in line:
                            start, end = line.split("-->")
                            start = start.strip().replace(",", ".")
                            end = end.strip().replace(",", ".")
                            current_segment.start = (
                                float(start.split(":")[0]) * 3600
                                + float(start.split(":")[1]) * 60
                                + float(start.split(":")[2])
                            )
                            current_segment.end = (
                                float(end.split(":")[0]) * 3600
                                + float(end.split(":")[1]) * 60
                                + float(end.split(":")[2])
                            )
                        elif not line.isdigit():  # Skip segment numbers
                            # Accumulate all text lines (handles multi-line subtitles)
                            if current_segment.text:
                                current_segment.text += "\n" + line
                            else:
                                current_segment.text = line
                    if current_segment.text:
                        # Only use the first line of text (the original Chinese)
                        # This handles cases where the SRT already has pinyin/translation
                        first_line = current_segment.text.split("\n")[0]
                        current_segment.text = first_line
                        parsed_segments.append(current_segment)

                    # Add translations if requested
                    if translation and parsed_segments:
                        progress.update(task_id, description="Translating segments", advance=10)
                        from .translation import translate_segments

                        # Get segments with translations (cached or newly translated)
                        parsed_segments = translate_segments(parsed_segments)

                    # Regenerate SRT with pinyin and translation if requested
                    if pinyin or translation:
                        from .transcription import create_srt_from_segments

                        srt_content = create_srt_from_segments(
                            parsed_segments, add_pinyin=pinyin, add_translation=translation
                        )
                        with open(input_files.subtitle, "w", encoding="utf-8") as f:
                            f.write(srt_content)
                        debug_print("Updated subtitle file with pinyin/translation")

                    # Generate images if requested
                    if generate_images and parsed_segments:
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
                    elif generate_images:
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
                        f"[bg]{create_subtitles_filter(input_files.subtitle, font)}[v]",
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
                            create_subtitles_filter(input_files.subtitle, font),
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
                            create_subtitles_filter(input_files.subtitle, font),
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
    app()
