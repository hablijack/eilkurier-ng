"""Pictures: find them (feed entry or article page), download and downscale them for print.

Where a source's pictures come from is set per source (`Source.image_mode`, catalog field `images`):
`feed` = the picture the feed entry carries, `page` = the article page's preview picture (og:image),
`auto` = the page's picture when the page has one (usually the larger one), else the feed's, `none` = never.
Finding is cheap and happens for every article (the feed and the page are loaded anyway); downloading only
for articles that a reader's next edition would likely print.
"""

import io
import logging
import re
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

import httpx
from lxml import html as lxml_html
from PIL import Image as PILImage
from PIL import ImageOps
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from eilkurier.db import Article, Image, ImageMode, Reader, Source, Status
from eilkurier.http import HostThrottle
from eilkurier.settings import Settings
from eilkurier.text import strip_html

log = logging.getLogger(__name__)

MAX_DOWNLOAD_BYTES = 12_000_000
MAX_PIXELS = 50_000_000  # decompression bomb guard (Pillow's own default is ~89 MP)
TARGET_SIDE = 1400  # px, long side: ~ 20 cm at 180 dpi, enough for a full-width lead picture
MIN_WIDTH = 400  # smaller pictures are icons or thumbnails that look blurry even at column width
WIDE_WIDTH = 1000  # from this width a picture may span the full page (lead story)
ASPECT_RANGE = (0.6, 2.6)  # width / height; outside: banners, skyscrapers, infographics
JPEG_QUALITY = 82
# The same picture on this many articles of one source is a logo/placeholder, not a news photo.
GENERIC_REPEATS = 3
IMAGE_EXT = re.compile(r"\.(jpe?g|png|webp|avif|gif)(\?|$)", re.I)
IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
ATTR = re.compile(r"""\b(src|alt|width)\s*=\s*["']([^"']*)["']""", re.I)
# Tracking pixels, emoji, share buttons and avatars that feeds put into the content.
NOT_A_PHOTO = re.compile(
    r"(feedburner|pixel|tracking|emoji|gravatar|avatar|/share|/icons?/|logo|placeholder|1x1|spacer)", re.I
)


@dataclass
class Found:
    url: str
    alt: str | None = None
    credit: str | None = None


def wants_feed(mode: str) -> bool:
    return mode in (ImageMode.AUTO, ImageMode.FEED)


def wants_page(mode: str) -> bool:
    return mode in (ImageMode.AUTO, ImageMode.PAGE)


def _clean(text: str | None, limit: int) -> str | None:
    text = strip_html(text or "").strip()
    return text[:limit] or None


def _usable_url(url: str | None) -> bool:
    return bool(url) and urlsplit(url).scheme in ("http", "https") and not NOT_A_PHOTO.search(url)


def from_feed(entry: Any, base_url: str | None = None) -> Found | None:
    """The best picture of a feed entry: media:content / media:thumbnail, image enclosure, first <img>."""
    candidates: list[tuple[int, Found]] = []
    credit = None
    for c in entry.get("media_credit") or []:
        credit = _clean(c.get("content"), 300) or credit
    description = _clean(entry.get("media_description"), 500)

    for m in entry.get("media_content") or []:
        url, kind = m.get("url"), (m.get("type") or "")
        if (
            m.get("medium") == "image"
            or kind.startswith("image/")
            or (not kind and IMAGE_EXT.search(url or ""))
        ):
            candidates.append((int(m.get("width") or 0) or 1000, Found(url, description, credit)))
    for m in entry.get("media_thumbnail") or []:
        candidates.append((int(m.get("width") or 0) or 1, Found(m.get("url"), description, credit)))
    for link in entry.get("links") or []:
        if link.get("rel") == "enclosure" and (link.get("type") or "").startswith("image/"):
            candidates.append((1000, Found(link.get("href"), description, credit)))
    if not candidates:
        for content in [*(entry.get("content") or []), {"value": entry.get("summary") or ""}]:
            for tag in IMG_TAG.findall(content.get("value") or ""):
                attrs = {k.lower(): v for k, v in ATTR.findall(tag)}
                width = int(attrs["width"]) if attrs.get("width", "").isdigit() else 500
                if width >= MIN_WIDTH or "width" not in attrs:
                    candidates.append(
                        (width, Found(attrs.get("src", ""), _clean(attrs.get("alt"), 500), credit))
                    )
            if candidates:
                break
    best = None
    for _width, found in sorted(candidates, key=lambda c: -c[0]):
        if base_url and found.url:
            found.url = urljoin(base_url, found.url)
        if _usable_url(found.url):
            best = found
            break
    return best


def from_page(html: str | bytes, page_url: str) -> Found | None:
    """The page's preview picture (Open Graph / Twitter card), which news sites set for every article."""
    try:
        doc = lxml_html.fromstring(html)
    except (ValueError, lxml_html.etree.ParserError):
        return None

    def meta(*keys: str) -> str | None:
        for key in keys:
            values = doc.xpath(f"//meta[@property='{key}' or @name='{key}']/@content")
            if values and values[0].strip():
                return values[0].strip()
        return None

    url = meta("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")
    if not url:
        return None
    url = urljoin(page_url, url)
    if not _usable_url(url):
        return None
    return Found(url, _clean(meta("og:image:alt", "twitter:image:alt"), 500), None)


def apply(article: Article, found: Found | None) -> None:
    """Remember a found picture; the download happens later, and only if the article is likely printed."""
    if found is None:
        return
    article.image_url = found.url[:2000]
    article.image_alt = found.alt
    article.image_credit = found.credit
    article.image_status = Status.PENDING


# --- download + downscale ---------------------------------------------------------------------


def download(http: httpx.Client, url: str) -> bytes:
    with http.stream(
        "GET", url, headers={"Accept": "image/avif,image/webp,image/jpeg,image/png,*/*;q=0.5"}
    ) as r:
        r.raise_for_status()
        kind = r.headers.get("content-type", "")
        if kind and not kind.startswith("image/") and "octet-stream" not in kind:
            raise ValueError(f"not an image: {kind}")
        if int(r.headers.get("content-length") or 0) > MAX_DOWNLOAD_BYTES:
            raise ValueError("picture too large")
        data = bytearray()
        for chunk in r.iter_bytes():
            data += chunk
            if len(data) > MAX_DOWNLOAD_BYTES:
                raise ValueError("picture too large")
    return bytes(data)


def process(data: bytes) -> tuple[bytes, int, int]:
    """Validate and downscale to a plain RGB JPEG without metadata. ValueError: unusable for print."""
    PILImage.MAX_IMAGE_PIXELS = MAX_PIXELS
    with warnings.catch_warnings():
        warnings.simplefilter("error", PILImage.DecompressionBombWarning)
        try:
            img = PILImage.open(io.BytesIO(data))
            width, height = img.size
            if width < MIN_WIDTH:
                raise ValueError(f"too small ({width} px)")
            if not ASPECT_RANGE[0] <= width / height <= ASPECT_RANGE[1]:
                raise ValueError(f"odd shape ({width}x{height})")
            img.draft("RGB", (TARGET_SIDE, TARGET_SIDE))  # JPEG: decode at reduced size (fast on the Pi)
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = PILImage.new("RGB", img.size, "white")
                background.paste(img, mask=img.getchannel("A"))
                img = background
            img = img.convert("RGB")
            img.thumbnail((TARGET_SIDE, TARGET_SIDE), PILImage.Resampling.LANCZOS)
            out = io.BytesIO()
            img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        except (
            OSError,
            SyntaxError,
            PILImage.DecompressionBombError,
            PILImage.DecompressionBombWarning,
        ) as exc:
            raise ValueError(f"unreadable picture: {exc}") from exc
    return out.getvalue(), img.width, img.height


def grayscale(jpeg: bytes) -> bytes:
    """Black-and-white version for the retro theme."""
    img = PILImage.open(io.BytesIO(jpeg)).convert("L")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue()


# --- worker step ------------------------------------------------------------------------------


def likely_printed(session: Session, settings: Settings, now: datetime) -> list[Article]:
    """Articles that some reader's next edition would pick (same selection as the edition itself)."""
    from eilkurier.edition import select_articles  # edition imports render; keep this module light

    today: date = now.astimezone(ZoneInfo(settings.timezone)).date()
    readers = session.scalars(
        select(Reader).where(Reader.active.is_(True)).options(selectinload(Reader.interests))
    ).all()
    seen: dict[int, Article] = {}
    for reader in readers:
        for scored in select_articles(session, reader, now, today)[: reader.story_count]:
            seen.setdefault(scored.article.id, scored.article)
    return list(seen.values())


def _is_generic(session: Session, article: Article) -> bool:
    repeats = session.scalar(
        select(func.count()).where(
            Article.source_id == article.source_id, Article.image_url == article.image_url
        )
    )
    return (repeats or 0) >= GENERIC_REPEATS


def fetch(
    session: Session, http: httpx.Client, settings: Settings, throttle: HostThrottle, now: datetime
) -> int:
    """Download the pictures of likely printed articles. Returns the number of new pictures."""
    pending = [a for a in likely_printed(session, settings, now) if a.image_status == Status.PENDING]
    done = 0
    for article in pending[: settings.image_batch]:
        source: Source = article.source
        if source.image_mode == ImageMode.NONE:
            article.image_status = Status.SKIPPED
            continue
        if not article.image_url and wants_page(source.image_mode) and article.url:
            # Source without full text: the page has not been loaded yet, so look for its preview picture now.
            throttle.wait(article.url)
            try:
                response = http.get(article.url)
                response.raise_for_status()
                apply(article, from_page(response.content, str(response.url)))
            except httpx.HTTPError as exc:
                log.info("page for picture failed for %s: %s", article.url, exc)
        if not article.image_url or _is_generic(session, article):
            article.image_status = Status.SKIPPED
            continue
        existing = session.scalar(select(Image).where(Image.url == article.image_url))
        if existing is None:
            throttle.wait(article.image_url)
            try:
                data, width, height = process(download(http, article.image_url))
            except (httpx.HTTPError, ValueError) as exc:
                log.info("picture skipped for %s: %s", article.image_url, exc)
                article.image_status = Status.SKIPPED
                continue
            existing = Image(url=article.image_url, data=data, width=width, height=height)
            session.add(existing)
            session.flush()
            done += 1
        article.image_id = existing.id
        article.image_status = Status.DONE
    return done


def purge_old(session: Session, settings: Settings, now: datetime) -> None:
    """Pictures no article uses any more go after the retention period (printed PDFs keep their copy)."""
    cutoff = now - timedelta(days=settings.article_retention_days)
    used = select(Article.image_id).where(Article.image_id.is_not(None))
    for image in session.scalars(select(Image).where(Image.created_at < cutoff, Image.id.not_in(used))):
        session.delete(image)
