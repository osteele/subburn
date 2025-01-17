"""Image generation functionality for subburn."""

import base64
import concurrent.futures
import os
import tempfile
import time
from pathlib import Path
import threading
from datetime import datetime, timedelta

from openai import OpenAI, OpenAIError
from rich.progress import Progress

def check_openai_api_key():
    """Check if OpenAI API key is set and valid."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Get your API key from https://platform.openai.com/account/api-keys"
        )
    return api_key

# OpenAI rate limit is 7 images per minute
RATE_LIMIT = 7
RATE_WINDOW = 60  # seconds
INITIAL_RETRY_DELAY = 2  # seconds
MAX_RETRIES = 3

class RateLimiter:
    def __init__(self, rate_limit: int, window: int):
        self.rate_limit = rate_limit
        self.window = window
        self.requests = []
        self.lock = threading.Lock()
    
    def wait(self):
        """Wait until a request can be made within rate limits."""
        while True:
            with self.lock:
                now = time.time()
                # Remove old requests
                self.requests = [t for t in self.requests if now - t < self.window]
                
                if len(self.requests) < self.rate_limit:
                    self.requests.append(now)
                    return
            
            # Wait before checking again
            time.sleep(1)

rate_limiter = RateLimiter(RATE_LIMIT, RATE_WINDOW)

def generate_image_for_text(
    text: str,
    style: str,
    output_dir: Path,
    segment_index: int,
) -> Path | None:
    """Generate an image for the given text using DALL-E."""
    api_key = check_openai_api_key()
    client = OpenAI(api_key=api_key)
    
    retry_delay = INITIAL_RETRY_DELAY
    
    for attempt in range(MAX_RETRIES):
        try:
            # Wait for rate limit
            rate_limiter.wait()
            
            prompt = f"{style}. Scene depicting: {text}"
            
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
                response_format="b64_json"
            )
            
            # Decode and save the image
            image_data = base64.b64decode(response.data[0].b64_json)
            image_path = output_dir / f"image_{segment_index}.png"
            with open(image_path, "wb") as f:
                f.write(image_data)
                
            return image_path
            
        except OpenAIError as e:
            error_message = str(e)
            if 'rate_limit' in error_message.lower():
                if attempt < MAX_RETRIES - 1:
                    print(f"Rate limit hit, retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                continue
            print(f"Error generating image: {e}")
            return None
        except Exception as e:
            print(f"Error generating image: {e}")
            return None
    
    print("Max retries exceeded")
    return None

def process_segment(args) -> tuple[float, Path | None]:
    """Process a single segment for parallel execution."""
    segment, style, output_dir, segment_index = args
    text = segment.text if hasattr(segment, 'text') else segment["text"]
    start_time = float(segment.start if hasattr(segment, 'start') else segment["start"])
    
    image_path = generate_image_for_text(
        text.strip(),
        style,
        output_dir,
        segment_index,
    )
    return start_time, image_path, text[:30]

def generate_images_for_segments(
    segments: list,
    style: str,
    progress: Progress,
) -> dict[float, Path]:
    """Generate images for each segment of text."""
    # Early check for API key to fail fast
    check_openai_api_key()

    # Create a permanent directory for images
    output_dir = Path(tempfile.gettempdir()) / "subburn_images"
    output_dir.mkdir(exist_ok=True)
    
    # Create a task for overall progress
    task_id = progress.add_task(
        "Generating images",
        total=len(segments),
    )
    
    # Prepare arguments for parallel processing
    process_args = [
        (segment, style, output_dir, i)
        for i, segment in enumerate(segments)
    ]
    
    # Process segments in parallel with limited workers
    images = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(process_segment, args): i
            for i, args in enumerate(process_args)
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(futures):
            start_time, image_path, text_preview = future.result()
            if image_path:
                images[start_time] = image_path
                progress.update(task_id, advance=1, description=f"Generated image for: {text_preview}...")
            else:
                progress.update(task_id, advance=1, description="Error generating image")
    
    progress.update(task_id, description="Image generation complete")
    return images
