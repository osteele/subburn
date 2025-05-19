"""Tests for translation module."""

import pytest
from unittest.mock import Mock, patch

from subburn.translation import (
    Translation,
    TranslationResponse,
    contains_chinese,
    translate_segments,
)
from subburn.types import Segment


class TestContainsChinese:
    """Test Chinese character detection."""

    def test_contains_chinese_with_chinese_text(self) -> None:
        """Test detection of Chinese characters in text."""
        assert contains_chinese("你好世界") is True
        assert contains_chinese("混合text文字") is True
        assert contains_chinese("中") is True

    def test_contains_chinese_without_chinese_text(self) -> None:
        """Test detection when no CJK characters present."""
        assert contains_chinese("Hello world") is False
        assert contains_chinese("123456") is False
        assert contains_chinese("") is False
        # Note: 日本語 contains CJK ideographs, so it would return True


class TestTranslateSegments:
    """Test segment translation functionality."""

    def test_translate_segments_with_chinese(self) -> None:
        """Test translation of segments containing Chinese text."""
        # Create test segments
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world"),
            Segment(start=1.0, end=2.0, text="你好世界"),
            Segment(start=2.0, end=3.0, text="再见"),
        ]
        
        # Create mock OpenAI client
        mock_client = Mock()
        mock_response = Mock()
        mock_message = Mock()
        
        # Create the expected parsed response
        parsed_response = TranslationResponse(
            translations=[
                Translation(index=1, translation="Hello world"),
                Translation(index=2, translation="Goodbye"),
            ]
        )
        
        # Configure the mock chain
        mock_message.parsed = parsed_response
        mock_response.choices = [Mock(message=mock_message)]
        mock_client.beta.chat.completions.parse.return_value = mock_response
        
        # Call the function
        translate_segments(segments, mock_client)
        
        # Verify the API was called correctly
        mock_client.beta.chat.completions.parse.assert_called_once()
        call_args = mock_client.beta.chat.completions.parse.call_args
        
        # Check that the right model and temperature were used
        assert call_args.kwargs["model"] == "gpt-4o-mini"
        assert call_args.kwargs["temperature"] == 0.3
        assert call_args.kwargs["response_format"] == TranslationResponse
        
        # Check that messages contain the right content
        messages = call_args.kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "1. 你好世界" in messages[1]["content"]
        assert "2. 再见" in messages[1]["content"]
        
        # Verify translations were assigned
        assert segments[0].translation is None  # English text not translated
        assert segments[1].translation == "Hello world"
        assert segments[2].translation == "Goodbye"

    def test_translate_segments_no_chinese(self) -> None:
        """Test translation when no Chinese text is present."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world"),
            Segment(start=1.0, end=2.0, text="Good morning"),
        ]
        
        mock_client = Mock()
        
        # Call the function
        translate_segments(segments, mock_client)
        
        # Verify API was not called
        mock_client.beta.chat.completions.parse.assert_not_called()
        
        # Verify no translations were added
        assert segments[0].translation is None
        assert segments[1].translation is None

    def test_translate_segments_empty_list(self) -> None:
        """Test translation with empty segment list."""
        segments = []
        mock_client = Mock()
        
        translate_segments(segments, mock_client)
        
        # Verify API was not called
        mock_client.beta.chat.completions.parse.assert_not_called()

    def test_translate_segments_preserves_order(self) -> None:
        """Test that translation preserves segment order."""
        segments = [
            Segment(start=0.0, end=1.0, text="第一"),
            Segment(start=1.0, end=2.0, text="Second"),
            Segment(start=2.0, end=3.0, text="第三"),
        ]
        
        mock_client = Mock()
        mock_response = Mock()
        mock_message = Mock()
        
        parsed_response = TranslationResponse(
            translations=[
                Translation(index=1, translation="First"),
                Translation(index=2, translation="Third"),
            ]
        )
        
        mock_message.parsed = parsed_response
        mock_response.choices = [Mock(message=mock_message)]
        mock_client.beta.chat.completions.parse.return_value = mock_response
        
        translate_segments(segments, mock_client)
        
        # Check correct segments were translated
        assert segments[0].translation == "First"
        assert segments[1].translation is None  # English, not translated
        assert segments[2].translation == "Third"

    def test_translate_segments_missing_translation(self) -> None:
        """Test assertion error when translation is missing."""
        segments = [
            Segment(start=0.0, end=1.0, text="你好"),
            Segment(start=1.0, end=2.0, text="世界"),
        ]
        
        mock_client = Mock()
        mock_response = Mock()
        mock_message = Mock()
        
        # Response missing translation for index 2
        parsed_response = TranslationResponse(
            translations=[
                Translation(index=1, translation="Hello"),
            ]
        )
        
        mock_message.parsed = parsed_response
        mock_response.choices = [Mock(message=mock_message)]
        mock_client.beta.chat.completions.parse.return_value = mock_response
        
        # Should raise assertion error
        with pytest.raises(AssertionError, match="Missing translation for segment 2"):
            translate_segments(segments, mock_client)