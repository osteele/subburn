"""Command-line interface for subburn."""

from pathlib import Path
from typing import Annotated, cast

import click
import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from . import image_gen
from .debug import debug_print, set_debug_level
from .movie import create_movie
from .transcription import create_srt_from_segments, get_audio_duration, transcribe_audio
from .types import MovieConfig, Segment, SubtitleOptions
from .utils import collect_input_files, compute_output_path, open_file_with_app

console = Console()
app = typer.Typer()


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
    original_color: Annotated[
        str, typer.Option(help="Color for original text subtitles in hex format (e.g. 'FFFFFF' for white)")
    ] = "FFFFFF",
    pinyin_color: Annotated[
        str, typer.Option(help="Color for pinyin text in hex format (e.g. '00FFFF' for cyan)")
    ] = "00FFFF",
    translation_color: Annotated[
        str, typer.Option(help="Color for translation text in hex format (e.g. '7FFF7F' for light green)")
    ] = "7FFF7F",
    original_font_size: Annotated[int, typer.Option(help="Font size for original text")] = 28,
    pinyin_font_size: Annotated[int, typer.Option(help="Font size for pinyin text")] = 22,
    translation_font_size: Annotated[int, typer.Option(help="Font size for translation text")] = 22,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Show debug information")] = False,
) -> None:
    """Create a video with burnt-in subtitles.

    The program automatically detects and uses a font with CJK (Chinese, Japanese, Korean) support.
    You can also specify a specific font with the --font option. Recommended fonts for CJK:
    - macOS: 'Arial Unicode MS', 'Hiragino Sans GB', 'PingFang SC'
    - Windows: 'Microsoft YaHei', 'SimHei', 'MingLiU'
    - Linux: 'Noto Sans CJK', 'WenQuanYi Micro Hei'

    You can customize the appearance of subtitles:
    - Set different colors for original text, pinyin, and translations using hex format (e.g., 'FFFFFF' for white)
    - Set different font sizes for each component (default sizes: original=28, pinyin=22, translation=22)
    """
    # Set debug level based on verbose flag
    set_debug_level(1 if verbose else 0)

    # Create subtitle options from CLI options
    subtitle_options = SubtitleOptions(
        show_pinyin=pinyin,
        show_translation=translation,
        font_name=font,
        original_font_size=original_font_size,
        pinyin_font_size=pinyin_font_size,
        translation_font_size=translation_font_size,
        original_color=original_color,
        pinyin_color=pinyin_color,
        translation_color=translation_color,
    )

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
        input_files = collect_input_files([Path(f) for f in files], verbose=verbose)

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

            # Use the subtitle options created at the beginning
            input_files.subtitle, whisper_segments = transcribe_audio(
                input_files.audio, progress, task_id, subtitle_options
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
                            float(end.split(":")[0]) * 3600 + float(end.split(":")[1]) * 60 + float(end.split(":")[2])
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

                # Regenerate SRT with styling options if requested
                if pinyin or translation:
                    srt_content = create_srt_from_segments(parsed_segments, options=subtitle_options)
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
            verbose=verbose,
        )

        # Create movie config using the subtitle options created earlier
        movie_config = MovieConfig(subtitle_options=subtitle_options, width=width, height=height)

        # Create the movie
        create_movie(
            output_path=output_path,
            input_files=input_files,
            config=movie_config,
            image_timestamps=image_timestamps,
            audio_duration=duration,
            progress=progress,
            task_id=task_id,
            verbose=verbose,
        )

        if should_open:
            open_file_with_app(output_path)

    console.print(f"[green]Created video:[/] {output_path}")


if __name__ == "__main__":
    app()
