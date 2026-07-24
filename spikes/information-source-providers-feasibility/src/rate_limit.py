from __future__ import annotations

import time


class RateLimiter:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = max(0.0, delay_seconds)
        self._last_request_at = 0.0

    def wait(self) -> None:
        if self.delay_seconds <= 0:
            return
        now = time.monotonic()
        remaining = self.delay_seconds - (now - self._last_request_at)
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()
