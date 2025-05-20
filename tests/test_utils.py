"""Tests for utility functions."""

import sys
from pathlib import Path
from unittest import mock

from subburn.movie import create_subtitles_filter
from subburn.types import SubtitleOptions
from subburn.utils import find_cjk_compatible_font


def test_create_subtitles_filter():
    """Test create_subtitles_filter function."""
    subtitle_path = Path("/path/to/subtitle.srt")

    # Test with simple font name
    options = SubtitleOptions(font_name="Arial")
    filter_str = create_subtitles_filter(subtitle_path, options)
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Arial,Fontsize=28,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected

    # Test with auto-detected font (we'll mock the find_cjk_compatible_font function)
    with mock.patch("subburn.movie.find_cjk_compatible_font", return_value="Mock CJK Font"):
        options = SubtitleOptions()
        filter_str = create_subtitles_filter(subtitle_path, options)
        expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Mock CJK Font,Fontsize=28,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
        assert filter_str == expected

    # Test with font name containing spaces
    options = SubtitleOptions(font_name="Arial Unicode MS")
    filter_str = create_subtitles_filter(subtitle_path, options)
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Arial Unicode MS,Fontsize=28,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected

    # Test with CJK font name
    options = SubtitleOptions(font_name="Hiragino Sans GB")
    filter_str = create_subtitles_filter(subtitle_path, options)
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Hiragino Sans GB,Fontsize=28,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected

    # Test with font name containing special characters
    options = SubtitleOptions(font_name="Font-With.Special+Chars")
    filter_str = create_subtitles_filter(subtitle_path, options)
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Font-With.Special+Chars,Fontsize=28,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected

    # Test with custom font size
    options = SubtitleOptions(font_name="Arial", original_font_size=36)
    filter_str = create_subtitles_filter(subtitle_path, options)
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Arial,Fontsize=36,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected
    
    # Test with custom color
    options = SubtitleOptions(font_name="Arial", original_color="FF0000")
    filter_str = create_subtitles_filter(subtitle_path, options)
    expected = "subtitles=/path/to/subtitle.srt:force_style='Fontname=Arial,Fontsize=28,PrimaryColour=&HFF0000,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected
    
    # Test with path containing colon (like on Windows)
    win_path = Path("C:/path/to/subtitle.srt")
    options = SubtitleOptions(font_name="Arial")
    filter_str = create_subtitles_filter(win_path, options)
    expected = "subtitles=C\\\\:/path/to/subtitle.srt:force_style='Fontname=Arial,Fontsize=28,PrimaryColour=&HFFFFFF,BorderStyle=1,Outline=1,Shadow=1'"
    assert filter_str == expected


def test_find_cjk_compatible_font():
    """Test the font detection function."""
    # Test direct file check on macOS
    with mock.patch("sys.platform", "darwin"):
        with mock.patch("os.path.exists", return_value=True):
            font = find_cjk_compatible_font()
            assert font == "Arial Unicode MS"

    # Test with fc-list for Chinese fonts
    mock_result = mock.MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "/path/to/font/file.ttf: CJK Font,Regular"

    with mock.patch("sys.platform", "linux"):
        with mock.patch("os.path.exists", return_value=False):
            with mock.patch("subprocess.run", return_value=mock_result):
                font = find_cjk_compatible_font()
                assert font == "CJK Font"

    # Test with fc-list failing
    with mock.patch("subprocess.run", side_effect=FileNotFoundError()):
        with mock.patch("os.path.exists", return_value=False):
            with mock.patch("sys.platform", "darwin"):
                font = find_cjk_compatible_font()
                assert font == "Arial Unicode MS"

            with mock.patch("sys.platform", "win32"):
                font = find_cjk_compatible_font()
                assert font == "Microsoft YaHei"

            with mock.patch("sys.platform", "linux"):
                font = find_cjk_compatible_font()
                assert font == "Noto Sans CJK"