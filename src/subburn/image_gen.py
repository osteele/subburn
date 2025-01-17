"""Generate images for video segments."""

import os
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx
from openai import OpenAI, OpenAIError
from rich.progress import Progress

from .debug import debug_print
from .rate_limit import (
    INITIAL_RETRY_DELAY,
    MAX_RETRIES,
    RATE_LIMIT,
    RateLimiter,
)
from .types import Segment


def check_openai_api_key() -> str:
    """Check if OpenAI API key is set and valid."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Get your API key from https://platform.openai.com/account/api-keys"
        )
    return api_key


def generate_image(
    text: str,
    style_prompt: str,
    output_dir: Path,
    segment_index: int,
) -> tuple[float, Optional[Path]]:
    """Generate an image for the given text using DALL-E."""
    api_key = check_openai_api_key()
    client = OpenAI(api_key=api_key)

    retry_delay = INITIAL_RETRY_DELAY

    for attempt in range(MAX_RETRIES):
        try:
            # Combine text with style prompt
            prompt = f"{text} - {style_prompt}"

            # Generate image
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )

            # Get image URL
            image_url = response.data[0].url
            if not image_url:
                return 0, None

            # Download image
            image_response = httpx.get(image_url)
            if image_response.status_code != 200:
                debug_print("Failed to download image: {}", image_response.status_code)
                return 0, None

            # Save image
            image_path = output_dir / f"image_{segment_index:04d}.png"
            image_path.write_bytes(image_response.content)

            return 0, image_path

        except OpenAIError as e:
            debug_print("OpenAI API error: {}", e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return 0, None

        except Exception as e:
            debug_print("Error generating image: {}", e)
            return 0, None

    return 0, None


def generate_images_for_segments(
    segments: list[Segment],
    style_prompt: str,
    progress: Progress,
) -> dict[float, Path]:
    """Generate images for each segment of text."""
    # Early check for API key to fail fast
    check_openai_api_key()

    # Create a permanent directory for images
    output_dir = Path(tempfile.gettempdir()) / "subburn_images"
    output_dir.mkdir(exist_ok=True)

    # Initialize rate limiter
    rate_limiter = RateLimiter(RATE_LIMIT)

    # Create progress bar
    task_id = progress.add_task("Generating images", total=len(segments))

    # Generate images for each segment
    image_timestamps: dict[float, Path] = {}
    for i, segment in enumerate(segments):
        rate_limiter.wait()

        timestamp, image_path = generate_image(
            segment["text"],
            style_prompt,
            output_dir,
            i,
        )

        if image_path:
            image_timestamps[segment["start"]] = image_path

        progress.update(task_id, advance=1)

    return image_timestamps
