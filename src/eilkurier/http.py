import time
from urllib.parse import urlsplit

import httpx

from eilkurier.settings import Settings


def make_client(settings: Settings, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": settings.user_agent, "Accept-Language": f"{settings.language},en;q=0.5"},
        timeout=httpx.Timeout(20.0, connect=10.0),
        follow_redirects=True,
        transport=transport,
    )


class HostThrottle:
    """Politeness: at most one request per `interval` seconds to the same host."""

    def __init__(self, interval: float = 1.5) -> None:
        self.interval = interval
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> None:
        host = urlsplit(url).netloc
        last = self._last.get(host)
        if last is not None:
            delay = self.interval - (time.monotonic() - last)
            if delay > 0:
                time.sleep(delay)
        self._last[host] = time.monotonic()
