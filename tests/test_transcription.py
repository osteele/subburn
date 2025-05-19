"""Tests for transcription module."""

import pytest
from pypinyin import Style, pinyin

from subburn.transcription import create_srt_from_segments, generate_pinyin
from subburn.types import Segment


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
        result = create_srt_from_segments(segments)
        
        expected = "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n2\n00:00:01,000 --> 00:00:02,000\n你好世界\n"
        assert result == expected

    def test_srt_with_pinyin(self) -> None:
        """Test SRT creation with pinyin for Chinese text."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world"),
            Segment(start=1.0, end=2.0, text="你好世界"),
        ]
        result = create_srt_from_segments(segments, add_pinyin=True)
        
        expected = "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n2\n00:00:01,000 --> 00:00:02,000\n你好世界\nnǐhǎo shìjiè\n"
        assert result == expected

    def test_srt_with_translation(self) -> None:
        """Test SRT creation with translation."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world", translation=None),
            Segment(start=1.0, end=2.0, text="你好世界", translation="Hello world"),
        ]
        result = create_srt_from_segments(segments, add_translation=True)
        
        expected = "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n2\n00:00:01,000 --> 00:00:02,000\n你好世界\nHello world\n"
        assert result == expected

    def test_srt_with_pinyin_and_translation(self) -> None:
        """Test SRT creation with both pinyin and translation."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world", translation=None),
            Segment(start=1.0, end=2.0, text="你好世界", translation="Hello world"),
        ]
        result = create_srt_from_segments(
            segments, add_pinyin=True, add_translation=True
        )
        
        expected = "1\n00:00:00,000 --> 00:00:01,000\nHello world\n\n2\n00:00:01,000 --> 00:00:02,000\n你好世界\nnǐhǎo shìjiè\nHello world\n"
        assert result == expected

    def test_srt_with_cjk_punctuation(self) -> None:
        """Test SRT creation handles CJK punctuation conversion."""
        segments = [
            Segment(start=0.0, end=1.0, text="你好,世界!"),
        ]
        result = create_srt_from_segments(segments)
        
        # Check that ASCII punctuation is converted to CJK in the subtitle text
        assert "你好，世界！" in result
        # Timestamps use ASCII commas, so we need to check more specifically
        lines = result.split('\n')
        subtitle_text = lines[2]  # Third line is the subtitle text
        assert "," not in subtitle_text  # ASCII comma should be converted in subtitle
        assert "!" not in subtitle_text  # ASCII exclamation should be converted in subtitle

    def test_empty_segments(self) -> None:
        """Test SRT creation with empty segments list."""
        result = create_srt_from_segments([])
        assert result == ""