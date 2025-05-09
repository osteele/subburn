"""Test the CLI module."""

from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner

from subburn.utils import (
    InputFiles,
    classify_file,
    collect_input_files,
    compute_output_path,
    convert_to_cjk_punctuation,
    format_timestamp,
)


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_files(tmp_path: Path) -> Generator[dict[str, Path], None, None]:
    """Create temporary test files."""
    files = {
        "audio": tmp_path / "test.mp3",
        "video": tmp_path / "test.mp4",
        "subtitle": tmp_path / "test.srt",
        "image": tmp_path / "test.jpg",
    }
    # Create empty files
    for path in files.values():
        path.touch()
    yield files
    # Cleanup
    for path in files.values():
        if path.exists():
            path.unlink()


def test_format_timestamp() -> None:
    """Test timestamp formatting."""
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(3661.5) == "01:01:01,500"
    assert format_timestamp(7322.75) == "02:02:02,750"


def test_convert_cjk_punctuation() -> None:
    """Test CJK punctuation conversion."""
    # Should not convert non-Chinese text
    assert convert_to_cjk_punctuation("Hello, world!") == "Hello, world!"
    # Should convert punctuation in Chinese text
    assert convert_to_cjk_punctuation("你好, 世界!") == "你好， 世界！"
    assert convert_to_cjk_punctuation("问题?") == "问题？"


def test_classify_file(temp_files: dict[str, Path]) -> None:
    """Test file classification."""
    assert classify_file(temp_files["audio"]) == "audio"
    assert classify_file(temp_files["video"]) == "video"
    assert classify_file(temp_files["subtitle"]) == "subtitle"
    assert classify_file(temp_files["image"]) == "image"


def test_collect_input_files(temp_files: dict[str, Path]) -> None:
    """Test input file collection."""
    files = [temp_files["audio"], temp_files["subtitle"]]
    input_files = collect_input_files(files)
    assert input_files.audio == temp_files["audio"]
    assert input_files.subtitle == temp_files["subtitle"]
    assert input_files.video is None
    assert input_files.image is None


def test_compute_output_path(temp_files: dict[str, Path]) -> None:
    """Test output path computation."""
    input_files = InputFiles()
    input_files.audio = temp_files["audio"]
    input_files.subtitle = temp_files["subtitle"]
    output = compute_output_path(input_files)
    assert output.name.startswith("test")
    assert output.suffix == ".mp4"
