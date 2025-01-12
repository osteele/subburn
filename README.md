# subburn

Create videos with burnt-in subtitles from audio or video files.

I built this to create study materials for language learning by combining audio
files with their transcripts. I haven't found an iPhone app that I like that
shows subtitles, so I made a tool to burn them in so that a normal video player
can show them.

## Language Learning Use Case

`subburn` is particularly useful for language learners who want to create playable and scrubbable subtitled audio materials from audio lessons and their transcripts.

For example, if you have an audio file of a dialogue and its transcript in SRT format:

```bash
subburn "mandarin-dialogue.mp3" "dialogue-transcript.srt" --open
```

This will create a video with the dialogue audio and synchronized subtitles, perfect for shadowing practice or reading along while listening.

# Features

- 🎵 Create videos from audio files and SRT subtitles
- 🎬 Add subtitles to existing videos
- 🖼️ Use background images for visual interest
- 🔍 Automatically detect file types
- 🚀 Open the created video when done

## Installation

```bash
uv venv
uv pip install -e .
```

## Usage

The script automatically detects file types based on their extensions and MIME types. You can provide the files in any order:

```bash
# Create a movie with a blank background
subburn input.mp3 subtitles.srt

# Create a movie with a still image background
subburn input.mp3 subtitles.srt background.jpg

# Add subtitles to an existing video
subburn video.mp4 subtitles.srt

# Specify custom output path
subburn input.mp3 subtitles.srt -o output.mov
```

If no output file is specified, the script will create a `.mov` file with the same name as the input audio or video file.

## Development

This project uses `uv` for dependency management and development tools.

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run tests
just test

# Run linting and type checking
just check
```

## License

MIT 2024 Oliver Steele
