"""Consent walls: give the consent a reader would give by clicking "Zustimmen", then load the page again.

Only for walls that ask for consent to cookies and advertising and then show the full article for free. This
module never gets around bot blocks or pay walls (that is up to the publisher; see `docs/sperren.md`).

Each handler recognises its consent page and repeats what the page's own accept button does. The parameters
(cookie version, endpoint) are read from the consent page every time, so a new consent version on the site
does not break it. Cookies live in the `httpx.Client`'s jar for the worker's lifetime (nothing is stored).
"""

import json
import logging
import re
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

# Golem.de: articles redirect to /sonstiges/zustimmung/auswahl.html. The accept button calls
# <cookieUrl>/setconsentcookie.php?type=cmp, which sets `golem_consent20=cmp<cookieVersion>`.
GOLEM_CONFIG = re.compile(r"GolemConsent\.setCustomConfig\((\{.*?\})\);", re.S)


def _golem(http: httpx.Client, response: httpx.Response) -> bool:
    url = urlsplit(str(response.url))
    if not (url.hostname or "").endswith("golem.de") or "/zustimmung/" not in url.path:
        return False
    match = GOLEM_CONFIG.search(response.text)
    if not match:
        return False
    try:
        config = json.loads(match.group(1))
        endpoint = f"{config['cookieUrl']}/setconsentcookie.php"
        params = {
            "type": "cmp",
            "version": config["cookieVersion"],
            "expire": str(config.get("cookieExpire", 90)),
            "referer": "",
        }
    except (ValueError, KeyError, TypeError):
        return False
    if urlsplit(endpoint).hostname not in ("golem.de", "www.golem.de"):
        return False  # never send anything to a host the page names unless it is golem.de itself
    http.get(endpoint, params=params).raise_for_status()
    return True


HANDLERS: tuple[Callable[[httpx.Client, httpx.Response], bool], ...] = (_golem,)


def get_page(http: httpx.Client, url: str) -> httpx.Response:
    """GET an article page; if a known consent wall answers, accept it and load the page once more."""
    response = http.get(url)
    response.raise_for_status()
    for handler in HANDLERS:
        try:
            accepted = handler(http, response)
        except httpx.HTTPError as exc:
            log.info("consent for %s failed: %s", url, exc)
            return response
        if accepted:
            log.info("consent given for %s", urlsplit(url).hostname)
            response = http.get(url)
            response.raise_for_status()
            break
    return response
