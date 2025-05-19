# Architecture

Subburn is a command-line tool for creating videos with burnt-in subtitles from audio or video files.

## Core Components

### CLI Module (`cli.py`)

The main entry point that handles:
- Command-line argument parsing using Typer
- File classification and validation
- Audio transcription using OpenAI's Whisper API
- Subtitle processing with optional pinyin and translation
- Image generation using DALL-E API
- Video generation using FFmpeg
- Progress reporting using Rich

### Transcription Module (`transcription.py`)

Handles audio transcription and subtitle generation:
- `transcribe_audio()` - Transcribes audio using Whisper API
- `create_srt_from_segments()` - Converts segments to SRT format with optional pinyin/translation
- `generate_pinyin()` - Generates pinyin for Chinese text using pypinyin
- `contains_chinese()` - Detects Chinese characters in text

### Translation Module (`translation.py`)

Provides translation functionality:
- `translate_segments()` - Batch translates Chinese segments using OpenAI API
- Uses structured output with Pydantic models for reliable responses
- Implements efficient single-call translation for all segments
- Temperature set to 0.3 for consistent, deterministic translations

### Image Generation Module (`image_gen.py`)

Handles the generation of background images:
- Generates images for each subtitle segment using DALL-E
- Manages image storage and retrieval
- Implements rate limiting and retry logic
- Provides progress tracking for image generation

### Types Module (`types.py`)

Defines core data structures:
- `Segment` - Dataclass representing a subtitle segment with timing, text, and optional translation

### Utilities Module (`utils.py`)

Helper functions for:
- File classification and validation
- Timestamp formatting
- CJK punctuation conversion
- Font detection for Chinese/Japanese/Korean support
- FFmpeg subtitle filter creation

## Data Flow

1. Input Processing
   - Classify input files (audio, video, subtitles, images)
   - Validate file combinations

2. Transcription (if needed)
   - Send audio to Whisper API
   - Convert API response to Segment objects
   - Generate SRT subtitles

3. Translation (if requested)
   - Identify Chinese segments
   - Batch translate using OpenAI API with structured output
   - Update segments with translations

4. Subtitle Enhancement
   - Add pinyin to Chinese text (if requested)
   - Include translations in subtitle output
   - Generate multi-line subtitles

5. Image Generation (if enabled)
   - Process each subtitle segment
   - Generate images using DALL-E
   - Store images with timestamps

6. Video Generation
   - Construct FFmpeg command based on inputs
   - Execute FFmpeg with progress tracking
   - Generate output video with burnt-in subtitles

## Key Design Decisions

### Translation Temperature
The translation module uses a temperature of 0.3 for OpenAI API calls. This setting was chosen based on empirical observations in the NLP community:

- Temperature 0.0-0.3: More deterministic, better for tasks requiring consistency (translation, summarization)
- Temperature 0.5-0.7: Balanced creativity/consistency  
- Temperature 0.8-1.0: More creative, better for creative writing

For translation specifically, lower temperatures (0.2-0.3) are preferred because:
1. We want consistent terminology across similar phrases
2. We need faithful reproduction of meaning, not creative interpretation
3. Professional translations should be predictable and accurate

### Batch Translation
Translation is performed in a single API call for efficiency:
- All Chinese segments are numbered and sent together
- Structured output ensures reliable response format
- Reduces API calls from N to 1, saving time and cost

### Type System
The codebase uses:
- Dataclasses for domain objects (Segment)
- Pydantic models for API structured outputs
- Type hints throughout for better IDE support and type checking

## Dependencies

- `typer` - Command line interface with type hints
- `rich` - Terminal formatting and progress bars
- `openai` - Whisper API, DALL-E, and translation services
- `pypinyin` - Chinese pinyin generation
- `pydantic` - Structured API responses
- `httpx` - HTTP client for image downloading
- FFmpeg (external) - Video processing