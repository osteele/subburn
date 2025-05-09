"""Tests for utility functions."""

from pathlib import Path
from subburn.utils import create_subtitles_filter


def test_create_subtitles_filter():
    """Test create_subtitles_filter function."""
    subtitle_path = Path("/path/to/subtitle.srt")
    
    # Test with simple font name
    filter_str = create_subtitles_filter(subtitle_path, "Arial")
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Arial,Fontsize=24,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected

    # Test with font name containing spaces
    filter_str = create_subtitles_filter(subtitle_path, "Arial Unicode MS")
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Arial Unicode MS,Fontsize=24,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected

    # Test with CJK font name
    filter_str = create_subtitles_filter(subtitle_path, "Hiragino Sans GB")
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Hiragino Sans GB,Fontsize=24,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected

    # Test with font name containing special characters
    filter_str = create_subtitles_filter(subtitle_path, "Font-With.Special+Chars")
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Font-With.Special+Chars,Fontsize=24,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected

    # Test with font size
    filter_str = create_subtitles_filter(subtitle_path, "Arial", 36)
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Arial,Fontsize=36,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected
    
    # Test with path containing colon (like on Windows)
    win_path = Path("C:/path/to/subtitle.srt")
    filter_str = create_subtitles_filter(win_path, "Arial")
    expected = "subtitles=C\\\\:/path/to/subtitle.srt:force_style='Fontname=Arial,Fontsize=24,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected