# API Reference

## CLI Interface

### Main Command

```python
subburn [OPTIONS] FILES...
```

Creates videos with burnt-in subtitles from audio or video files.

#### Options

- `--output PATH` - Output file path
- `--width INTEGER` - Output video width
- `--height INTEGER` - Output video height
- `--open` - Open the output file after creation
- `--whisper/--no-whisper` - Force/disable Whisper transcription
- `--generate-images` - Generate images for each segment using DALL-E
- `--image-style TEXT` - Style prompt for generated images (default: "A minimalist, artistic illustration")

## Core Functions

### Image Generation

```python
def generate_image_for_text(
    text: str,
    style: str,
    output_dir: Path,
    progress: Progress,
    task_id: int,
) -> Path
```

Generates an image for a given text segment using DALL-E.

```python
def generate_images_for_segments(
    segments: list,
    style: str,
    progress: Progress,
) -> dict[float, Path]
```

Generates images for each transcript segment, returning a mapping of timestamps to image paths.

### Transcription

```python
def transcribe_audio(audio_path: Path, progress: Progress, task_id: int) -> list
```

Transcribes audio using OpenAI's Whisper API. Returns a list of transcript segments.

### SRT Generation

```python
def create_srt_from_segments(segments: list) -> str
```

Creates SRT subtitle content from Whisper API segments.

### File Classification

```python
def classify_file(path: Path) -> str
```

Classifies a file based on its mimetype and extension.

### FFmpeg Integration

```python
def run_ffmpeg_with_progress(
    cmd: Sequence[str | Path],
    progress: Progress,
    task_id: int
) -> None
```

Runs FFmpeg command with progress tracking using Rich progress bars.

## Data Classes

### InputFiles

```python
@dataclass
class InputFiles:
    audio: Path | None = None
    video: Path | None = None
    subtitle: Path | None = None
    image: Path | None = None
```

Represents the collection of input files for video generation.
