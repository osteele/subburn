# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Chinese language support with pinyin generation using pypinyin and jieba
- Translation feature for subtitles using OpenAI's GPT-4 API
- XDG-compliant cache system for translations to reduce API calls
- Generic caching decorator for function results
- Support for specifying output directories with the `-o` option

## [0.1.0] - 2025-05-09

### Added
- Automatic CJK (Chinese, Japanese, Korean) font detection
- Improved CJK rendering support
- Documentation badges in README
- Developer documentation

### Changed
- Migrated from Click to Typer for command-line interface
- Replaced mypy with pyright for type checking
- Updated code quality tools configuration

### Fixed
- CJK font rendering issues
- Type errors and code refactoring

## [0.0.2] - 2025-01-17

### Added
- Image generation feature using DALL-E API (work in progress)

### Fixed
- Type errors and general refactoring

## [0.0.1] - 2025-01-16

### Added
- Initial implementation
- Audio transcription using OpenAI Whisper API
- SRT subtitle generation
- Test suite
- Basic documentation
- FFmpeg integration for video processing
- Rich terminal UI with progress bars

### Dependencies
- typer for CLI
- rich for terminal formatting
- openai for Whisper API
- requests for HTTP operations