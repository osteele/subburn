# subburn

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/charliermarsh/ruff)

Create videos with burnt-in subtitles from audio or video files.

I built this to create study materials for language learning by combining audio
files with their transcripts. I haven't found an iPhone app that I like that
shows subtitles, so I made a tool to burn them in so that a normal video player
can show them.

## Language Learning Use Case

`subburn` is particularly useful for language learners who want to create playable and scrubbable subtitled audio materials from audio lessons and their transcripts. For more on language learning approaches and techniques, see [Oliver's Language Learning resources](https://osteele.com/topics/language-learning/).

### Basic Subtitles

For example, if you have an audio file of a dialogue and its transcript in SRT format:

```bash
subburn "mandarin-dialogue.mp3" "dialogue-transcript.srt" --open
```

This will create a video with the dialogue audio and synchronized subtitles, perfect for shadowing practice or reading along while listening.

### Enhanced Chinese Learning

For Chinese language learning, you can use the pinyin and translation features:

```bash
# Add pinyin above Chinese characters
subburn "chinese-lesson.mp3" "transcript.srt" --pinyin --open

# Add English translations below Chinese text
subburn "chinese-lesson.mp3" "transcript.srt" --translation --open

# Use both for comprehensive learning
subburn "chinese-lesson.mp3" "transcript.srt" --pinyin --translation --open
```

This creates a three-line display with pinyin, Chinese characters, and English translation—ideal for Chinese language learners at any level.

# Features

- 🎵 Create videos from audio files and SRT subtitles
- 🎬 Add subtitles to existing videos
- 🖼️ Use background images for visual interest
- 🎨 Generate dynamic background images using DALL-E
- 🔍 Automatically detect file types
- ⏳ Show progress with a beautiful TUI
- 🚀 Open the created video when done
- 🎯 Automatic transcription using OpenAI Whisper
- 🈳 Support for Chinese with pinyin and translations
- 💾 Caches translations to avoid redundant API calls

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

### Chinese Language Support

`subburn` provides special support for Chinese language content with pinyin and translations:

#### Add Pinyin

Generate pinyin above Chinese subtitles to help with pronunciation:

```bash
subburn chinese_audio.mp3 --pinyin
```

#### Add English Translations

Add English translations below Chinese subtitles:

```bash
subburn chinese_audio.mp3 --translation
```

#### Combine Both Features

Use both pinyin and translation for comprehensive language learning:

```bash
subburn chinese_audio.mp3 --pinyin --translation
```

These features require an OpenAI API key for translation. Translations are cached to minimize API usage.

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

## Cache

Translations are cached in the XDG cache directory:
- Linux: `~/.cache/subburn/`
- macOS: `~/Library/Caches/subburn/`
- Windows: `%LOCALAPPDATA%\subburn\Cache\`

This prevents redundant API calls when processing the same content multiple times.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

For more technical documentation, see the [docs/](docs/) directory.

## License

MIT 2024 Oliver Steele
