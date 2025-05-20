"""Tests for translation module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from subburn.translation import (
    DEFAULT_MODEL_PARAMS,
    Translation,
    TranslationResponse,
    contains_chinese,
    get_translation_key_params,
    serialize_segments,
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


class TestTranslationUtils:
    """Test translation utility functions."""

    def test_serialize_segments(self) -> None:
        """Test serialization of segments to JSON string."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world"),
            Segment(start=1.0, end=2.0, text="你好世界"),
        ]
        
        serialized = serialize_segments(segments)
        
        # Verify it's a valid JSON string
        parsed = json.loads(serialized)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        
        # Check that only the necessary fields are included
        assert "start" in parsed[0]
        assert "end" in parsed[0]
        assert "text" in parsed[0]
        assert "translation" not in parsed[0]
        
        # Check actual values
        assert parsed[0]["text"] == "Hello world"
        assert parsed[1]["text"] == "你好世界"
    
    def test_get_translation_key_params(self) -> None:
        """Test generation of model parameters for cache key."""
        params = get_translation_key_params()
        
        # Check that default parameters are included
        assert params["model"] == DEFAULT_MODEL_PARAMS.model
        assert params["temperature"] == DEFAULT_MODEL_PARAMS.temperature
        assert params["system_prompt"] == DEFAULT_MODEL_PARAMS.system_prompt


class TestTranslateSegments:
    """Test segment translation functionality."""

    @patch("openai.OpenAI")
    def test_translate_segments_with_chinese(self, mock_openai_client) -> None:
        """Test translation of segments containing Chinese text."""
        # Create test segments
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world"),
            Segment(start=1.0, end=2.0, text="你好世界"),
            Segment(start=2.0, end=3.0, text="再见"),
        ]
        
        # Create mock OpenAI client
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
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
        with patch("os.environ", {"OPENAI_API_KEY": "fake-key"}):
            result = translate_segments(segments)
        
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
        assert result[0].translation is None  # English text not translated
        assert result[1].translation == "Hello world"
        assert result[2].translation == "Goodbye"
        
        # Verify original segments were not modified
        assert segments[0].translation is None
        assert segments[1].translation is None
        assert segments[2].translation is None

    @patch("openai.OpenAI")
    def test_translate_segments_no_chinese(self, mock_openai_client) -> None:
        """Test translation when no Chinese text is present."""
        segments = [
            Segment(start=0.0, end=1.0, text="Hello world"),
            Segment(start=1.0, end=2.0, text="Good morning"),
        ]
        
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        
        # Call the function
        with patch("os.environ", {"OPENAI_API_KEY": "fake-key"}):
            result = translate_segments(segments)
        
        # Verify API was not called
        mock_client.beta.chat.completions.parse.assert_not_called()
        
        # Verify no translations were added
        assert result[0].translation is None
        assert result[1].translation is None

    @patch("openai.OpenAI")
    def test_translate_segments_empty_list(self, mock_openai_client) -> None:
        """Test translation with empty segment list."""
        segments = []
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
        
        with patch("os.environ", {"OPENAI_API_KEY": "fake-key"}):
            result = translate_segments(segments)
        
        # Verify API was not called
        mock_client.beta.chat.completions.parse.assert_not_called()
        
        # Verify an empty list is returned
        assert result == []

    @patch("openai.OpenAI")
    def test_translate_segments_preserves_order(self, mock_openai_client) -> None:
        """Test that translation preserves segment order."""
        segments = [
            Segment(start=0.0, end=1.0, text="第一"),
            Segment(start=1.0, end=2.0, text="Second"),
            Segment(start=2.0, end=3.0, text="第三"),
        ]
        
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
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
        
        with patch("os.environ", {"OPENAI_API_KEY": "fake-key"}):
            result = translate_segments(segments)
        
        # Check correct segments were translated
        assert result[0].translation == "First"
        assert result[1].translation is None  # English, not translated
        assert result[2].translation == "Third"

    @patch("openai.OpenAI")
    def test_translate_segments_missing_translation(self, mock_openai_client) -> None:
        """Test assertion error when translation is missing."""
        segments = [
            Segment(start=0.0, end=1.0, text="你好"),
            Segment(start=1.0, end=2.0, text="世界"),
        ]
        
        mock_client = Mock()
        mock_openai_client.return_value = mock_client
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
        with patch("os.environ", {"OPENAI_API_KEY": "fake-key"}):
            with pytest.raises(AssertionError, match="Missing translation for segment 2"):
                translate_segments(segments)