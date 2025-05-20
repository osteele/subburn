"""Tests for transcription module."""

import pytest
from pypinyin import Style, pinyin

from subburn.transcription import create_srt_from_segments, generate_pinyin
from subburn.types import Segment, SubtitleOptions


class TestGeneratePinyin:
    """Test pinyin generation functionality."""

    def test_generate_pinyin_chinese_text(self) -> None:
        """Test pinyin generation for Chinese text."""
        result = generate_pinyin("你好世界")
        assert result == "nǐhǎo shìjiè"  # jieba correctly groups as words

    def test_generate_pinyin_mixed_text(self) -> None:
        """Test pinyin generation for mixed Chinese/English text."""
        result = generate_pinyin("Hello 世界")
        assert result == "Hello shìjiè"  # No extra space between English and pinyin

    def test_generate_pinyin_empty_text(self) -> None:
        """Test pinyin generation for empty text."""
        result = generate_pinyin("")
        assert result == ""


class TestCreateSrtFromSegments:
    """Test SRT creation functionality."""

    def test_basic_srt_creation(self) -> None:
        """Test basic SRT creation without pinyin or translation."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world"),
            Segment(start=1.0, end=2.0, text="你好世界"),
        ]
        options = SubtitleOptions(show_pinyin=False, show_translation=False)
        result = create_srt_from_segments(segments, options=options)
        
        expected = "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n2\n00:00:01,000 --> 00:00:02,000\n你好世界\n"
        assert result == expected

    def test_srt_with_pinyin(self) -> None:
        """Test SRT creation with pinyin for Chinese text."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world"),
            Segment(start=1.0, end=2.0, text="你好世界"),
        ]
        options = SubtitleOptions(show_pinyin=True, show_translation=False)
        result = create_srt_from_segments(segments, options=options)
        
        # The actual result will contain font styling HTML, so just check for basic content
        assert "Hello world" in result
        assert "你好世界" in result
        assert "nǐhǎo shìjiè" in result

    def test_srt_with_translation(self) -> None:
        """Test SRT creation with translation."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world", translation=None),
            Segment(start=1.0, end=2.0, text="你好世界", translation="Hello world"),
        ]
        options = SubtitleOptions(show_pinyin=False, show_translation=True)
        result = create_srt_from_segments(segments, options=options)
        
        # The actual result will contain font styling HTML, so just check for basic content
        assert "Hello world" in result
        assert "你好世界" in result
        # Second "Hello world" is the translation
        assert result.count("Hello world") >= 2

    def test_srt_with_pinyin_and_translation(self) -> None:
        """Test SRT creation with both pinyin and translation."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world", translation=None),
            Segment(start=1.0, end=2.0, text="你好世界", translation="Hello world"),
        ]
        options = SubtitleOptions(show_pinyin=True, show_translation=True)
        result = create_srt_from_segments(segments, options=options)
        
        # Check for all components
        assert "Hello world" in result
        assert "你好世界" in result
        assert "nǐhǎo shìjiè" in result
        # Count of "Hello world" - one original text and one translation
        assert result.count("Hello world") >= 2

    def test_srt_with_cjk_punctuation(self) -> None:
        """Test SRT creation handles CJK punctuation conversion."""
        segments = [
            Segment(start=0.0, end=1.0, text="你好,世界!"),
        ]
        options = SubtitleOptions(show_pinyin=False, show_translation=False)
        result = create_srt_from_segments(segments, options=options)
        
        # Check that ASCII punctuation is converted to CJK in the subtitle text
        assert "你好，世界！" in result
        # Timestamps use ASCII commas, so we need to check more specifically
        lines = result.split('\n')
        subtitle_text = lines[2]  # Third line is the subtitle text
        assert "," not in subtitle_text  # ASCII comma should be converted in subtitle
        assert "!" not in subtitle_text  # ASCII exclamation should be converted in subtitle

    def test_empty_segments(self) -> None:
        """Test SRT creation with empty segments list."""
        options = SubtitleOptions(show_pinyin=False, show_translation=False)
        result = create_srt_from_segments([], options=options)
        assert result == ""