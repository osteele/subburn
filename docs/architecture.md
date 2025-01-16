# Architecture

Subburn is a command-line tool for creating videos with burnt-in subtitles from audio or video files.

## Core Components

### CLI Module (`cli.py`)

The main entry point that handles:
- File classification and validation
- Audio transcription using OpenAI's Whisper API
- Video generation using FFmpeg
- Progress reporting using Rich

### Key Functions

- `transcribe_audio()` - Handles audio transcription via Whisper API
- `create_srt_from_segments()` - Converts Whisper API output to SRT format
- `run_ffmpeg_with_progress()` - Manages FFmpeg operations with progress tracking
- `collect_input_files()` - Validates and classifies input files

## Data Flow

1. Input Processing
   - Classify input files (audio, video, subtitles, images)
   - Validate file combinations

2. Transcription (if needed)
   - Convert audio to required format
   - Send to Whisper API
   - Generate SRT subtitles

3. Video Generation
   - Construct FFmpeg command based on inputs
   - Execute FFmpeg with progress tracking
   - Generate output video with burnt-in subtitles

## Dependencies

- `click` - Command line interface
- `rich` - Terminal formatting and progress bars
- `openai` - Whisper API integration
- FFmpeg (external) - Video processing
