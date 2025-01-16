# Getting Started

## Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) - Python package installer and virtual environment manager
- [just](https://github.com/casey/just) - Command runner
- FFmpeg - Required for video processing

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

- `OPENAI_API_KEY` - Required for automatic transcription using OpenAI's Whisper API

## Project Structure

```
subburn/
├── src/subburn/     # Source code
├── tests/           # Test files
├── docs/            # Documentation
└── pyproject.toml   # Project configuration and dependencies
```
