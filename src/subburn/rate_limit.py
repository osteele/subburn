"""Rate limiting utilities."""

import time

# OpenAI rate limit is 7 images per minute
RATE_LIMIT = 7
INITIAL_RETRY_DELAY = 1
MAX_RETRIES = 3


class RateLimiter:
    """Rate limiter for API requests."""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests: list[float] = []

    def wait(self) -> None:
        """Wait if necessary to stay within rate limits."""
        now = time.time()
        minute_ago = now - 60

        # Remove requests older than 1 minute
        self.requests = [t for t in self.requests if t > minute_ago]

        # If at rate limit, wait until oldest request is more than a minute old
        if len(self.requests) >= self.requests_per_minute:
            wait_time = self.requests[0] - minute_ago
            if wait_time > 0:
                time.sleep(wait_time)
            self.requests = self.requests[1:]

        self.requests.append(now)
