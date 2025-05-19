# Contributing to Subburn

## Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) - Python package installer and virtual environment manager
- [just](https://github.com/casey/just) - Command runner
- FFmpeg - Required for video processing
- DALL-E - Required for image generation (when using `--generate-images`)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/osteele/subburn.git
   cd subburn
   ```

2. Install dependencies using `uv`:
   ```bash
   uv venv
   uv pip install -e .
   ```

3. Install development dependencies:
   ```bash
   uv pip install --dev
   ```

## Development Workflow

1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. Run tests:
   ```bash
   just test
   ```

3. Run linting and type checks:
   ```bash
   just check
   ```

## Environment Variables

- `OPENAI_API_KEY` - Required for:
  - Automatic transcription using OpenAI's Whisper API
  - Image generation using DALL-E (when using `--generate-images`)
  - Translation of subtitles (when using `--translation`)

## Features

### Automatic Transcription
Use Whisper API to automatically transcribe audio:
```bash
subburn audio.mp3
```

### Chinese Language Support

#### Pinyin Generation
Add pinyin above Chinese subtitles:
```bash
subburn audio.mp3 --pinyin
```

#### Translation
Add English translations below subtitles:
```bash
subburn audio.mp3 --translation
```

#### Combined Pinyin and Translation
Use both features together:
```bash
subburn audio.mp3 --pinyin --translation
```

### Image Generation
Generate background images for each segment using DALL-E:
```bash
subburn audio.mp3 --generate-images
```

Customize the image style:
```bash
subburn audio.mp3 --generate-images --image-style "A watercolor painting in pastel colors"
```

## Project Structure

```
subburn/
├── src/subburn/     # Source code
├── tests/           # Test files
├── docs/            # Documentation
└── pyproject.toml   # Project configuration and dependencies
