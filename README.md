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
- 🎨 Generate dynamic background images using DALL-E
- 🔍 Automatically detect file types
- ⏳ Show progress with a beautiful TUI
- 🚀 Open the created video when done
- 🎯 Automatic transcription using OpenAI Whisper

## Installation

```bash
uv venv
uv pip install -e .
```

## Usage

### Basic Usage

Create a video from an audio file and its transcript:
```bash
subburn audio.mp3 subtitles.srt
```

### Automatic Transcription

If you have an OpenAI API key, `subburn` can automatically transcribe your audio:

```bash
export OPENAI_API_KEY=your-api-key
subburn audio.mp3  # Will create audio.srt and then the video
```

To disable automatic transcription:
```bash
subburn audio.mp3 --no-whisper
```

### Dynamic Background Images

Generate unique background images for each subtitle segment using DALL-E:

```bash
subburn audio.mp3 --generate-images
```

Customize the image style:
```bash
subburn audio.mp3 --generate-images --image-style "A watercolor painting in pastel colors"
```

This feature requires an OpenAI API key and will generate a unique image that matches the content of each subtitle segment.

### Additional Options

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
