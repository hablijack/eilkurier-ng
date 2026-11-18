"""Pictures: finding them in feeds and pages, downscaling, the download step and the printed edition."""

import io
from datetime import UTC, date, datetime

import feedparser
import pytest
from factories import add_article, add_reader, add_source, article_page, rss
from PIL import Image as PILImage
from sqlalchemy import func, select

from eilkurier import collect, images
from eilkurier.db import Article, Image, ImageMode, Status
from eilkurier.edition import build_edition, compose
from eilkurier.http import HostThrottle
from eilkurier.render import EditionRenderer


def picture(width: int = 1600, height: int = 900, mode: str = "RGB", fmt: str = "JPEG") -> bytes:
    img = PILImage.new(mode, (width, height), (40, 120, 200, 128) if mode == "RGBA" else (40, 120, 200))
    out = io.BytesIO()
    img.save(out, fmt)
    return out.getvalue()


def entry(extra: str = "", description: str = "") -> feedparser.FeedParserDict:
    feed = rss([{"title": "T", "link": "https://news.example.org/a", "teaser": description, "extra": extra}])
    return feedparser.parse(feed).entries[0]


# --- finding ------------------------------------------------------------------------------------


def test_feed_picture_prefers_the_largest_media_content() -> None:
    found = images.from_feed(
        entry(
            '<media:content url="https://img.example.org/small.jpg" medium="image" width="300"/>'
            '<media:content url="https://img.example.org/big.jpg" medium="image" width="1600"/>'
            "<media:credit>Foto: dpa</media:credit>"
        )
    )
    assert found.url == "https://img.example.org/big.jpg"
    assert found.credit == "Foto: dpa"


def test_feed_picture_from_enclosure_and_from_content_html() -> None:
    enclosure = entry('<enclosure url="https://img.example.org/e.jpg" type="image/jpeg" length="1"/>')
    assert images.from_feed(enclosure).url == "https://img.example.org/e.jpg"

    html = (
        '&lt;img src="https://cpx.example.org/pixel.gif" width="1" height="1"/&gt;'
        '&lt;img src="/uploads/photo.jpg" alt="Die Brücke" width="800"/&gt;'
    )
    found = images.from_feed(entry(description=html), base_url="https://news.example.org/a")
    assert found.url == "https://news.example.org/uploads/photo.jpg"  # tracking pixel skipped, URL absolute
    assert found.alt == "Die Brücke"
    assert images.from_feed(entry()) is None


def test_page_picture_from_open_graph() -> None:
    page = article_page(
        "Brücke",
        head='<meta property="og:image" content="/img/bruecke.jpg">'
        '<meta property="og:image:alt" content="Brücke">',
    )
    found = images.from_page(page, "https://news.example.org/artikel")
    assert (found.url, found.alt) == ("https://news.example.org/img/bruecke.jpg", "Brücke")
    twitter = article_page("x", head='<meta name="twitter:image" content="https://cdn.example.org/t.jpg">')
    assert images.from_page(twitter, "https://news.example.org/").url == "https://cdn.example.org/t.jpg"
    assert images.from_page(article_page("x"), "https://news.example.org/") is None
    logo = article_page("x", head='<meta property="og:image" content="https://news.example.org/logo.png">')
    assert images.from_page(logo, "https://news.example.org/") is None


# --- downscaling --------------------------------------------------------------------------------


def test_process_downscales_to_a_plain_jpeg() -> None:
    data, width, height = images.process(picture(3000, 2000))
    assert (width, height) == (1400, 933)
    assert PILImage.open(io.BytesIO(data)).format == "JPEG"
    # Transparent PNGs get a white background instead of black.
    data, *_ = images.process(picture(800, 600, mode="RGBA", fmt="PNG"))
    assert PILImage.open(io.BytesIO(data)).mode == "RGB"


@pytest.mark.parametrize(
    ("size", "reason"), [((300, 200), "too small"), ((2000, 400), "odd shape"), ((500, 1200), "odd shape")]
)
def test_process_rejects_icons_and_banners(size: tuple[int, int], reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        images.process(picture(*size))


def test_process_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="unreadable"):
        images.process(b"<html>not a picture</html>")


# --- pipeline -----------------------------------------------------------------------------------


def test_collect_finds_feed_pictures_and_the_page_one_wins(session, settings, web) -> None:
    source = add_source(session, url="https://news.example.org/feed.rss")
    web.add(
        "https://news.example.org/feed.rss",
        rss(
            [
                {
                    "title": "Brücke öffnet",
                    "link": "https://news.example.org/a",
                    "extra": '<media:content url="https://img.example.org/thumb.jpg" medium="image"/>',
                }
            ]
        ),
    )
    http = web.client()
    collect.collect_source(session, source, http, settings)
    article = session.scalar(select(Article))
    assert (article.image_url, article.image_status) == ("https://img.example.org/thumb.jpg", Status.PENDING)

    page = article_page(
        "Brücke öffnet", head='<meta property="og:image" content="https://img.example.org/big.jpg">'
    )
    web.add("https://news.example.org/a", page)
    collect.fetch_fulltexts(session, http, settings, HostThrottle(0))
    assert article.image_url == "https://img.example.org/big.jpg"  # `auto`: the page's (larger) picture


def test_image_mode_feed_ignores_the_page_and_none_finds_nothing(session, settings, web) -> None:
    feed_only = add_source(
        session, name="Feed", url="https://a.example.org/feed.rss", image_mode=ImageMode.FEED
    )
    never = add_source(session, name="Nie", url="https://b.example.org/feed.rss", image_mode=ImageMode.NONE)
    item = '<media:content url="https://img.example.org/f.jpg" medium="image"/>'
    for source, host in ((feed_only, "a"), (never, "b")):
        web.add(
            source.url, rss([{"title": f"T{host}", "link": f"https://{host}.example.org/x", "extra": item}])
        )
        web.add(
            f"https://{host}.example.org/x",
            article_page("T", head='<meta property="og:image" content="/p.jpg">'),
        )
        collect.collect_source(session, source, web.client(), settings)
    collect.fetch_fulltexts(session, web.client(), settings, HostThrottle(0))
    by_source = {a.source_id: a for a in session.scalars(select(Article))}
    assert by_source[feed_only.id].image_url == "https://img.example.org/f.jpg"
    assert (by_source[never.id].image_url, by_source[never.id].image_status) == (None, Status.SKIPPED)


def test_fetch_downloads_only_likely_printed_pictures(session, settings, web) -> None:
    source = add_source(session)
    add_reader(session, [source], story_count=1)
    printed = add_article(
        session, source, "Wichtig", image_url="https://img.example.org/1.jpg", image_status="pending"
    )
    later = add_article(
        session,
        source,
        "Später",
        hours_ago=30,
        image_url="https://img.example.org/2.jpg",
        image_status="pending",
    )
    web.add("https://img.example.org/*", picture(), headers={"content-type": "image/jpeg"})
    assert images.fetch(session, web.client(), settings, HostThrottle(0), datetime.now(UTC)) == 1
    assert printed.image_status == Status.DONE and printed.image.width == 1400
    assert later.image_status == Status.PENDING  # not in the reader's next edition: not downloaded
    # Another article with the same picture reuses the stored one.
    again = add_article(
        session, source, "Nochmal", image_url="https://img.example.org/1.jpg", image_status="pending"
    )
    session.delete(printed)
    images.fetch(session, web.client(), settings, HostThrottle(0), datetime.now(UTC))
    assert again.image_status == Status.DONE
    assert session.scalar(select(func.count()).select_from(Image)) == 1


def test_fetch_skips_generic_and_broken_pictures(session, settings, web) -> None:
    source, other = add_source(session), add_source(session, name="Andere")
    add_reader(session, [source, other], story_count=5)  # at most 3 articles per source are picked
    for i in range(3):  # the same picture on every article: a logo or placeholder
        add_article(
            session, source, f"G{i}", image_url="https://img.example.org/logo-ish.jpg", image_status="pending"
        )
    broken = add_article(
        session, other, "Kaputt", image_url="https://img.example.org/x.jpg", image_status="pending"
    )
    web.add("https://img.example.org/logo-ish.jpg", picture(), headers={"content-type": "image/jpeg"})
    web.add("https://img.example.org/x.jpg", "<html>Fehler</html>", headers={"content-type": "text/html"})
    images.fetch(session, web.client(), settings, HostThrottle(0), datetime.now(UTC))
    statuses = {a.title: a.image_status for a in session.scalars(select(Article))}
    assert statuses == {"G0": "skipped", "G1": "skipped", "G2": "skipped", "Kaputt": "skipped"}
    assert broken.image_id is None


def test_fetch_loads_the_page_for_sources_without_fulltext(session, settings, web) -> None:
    source = add_source(session, fetch_fulltext=False, image_mode=ImageMode.PAGE)
    add_reader(session, [source])
    article = add_article(
        session, source, "Ohne Volltext", url="https://news.example.org/o", image_status="pending"
    )
    web.add(
        "https://news.example.org/o", article_page("x", head='<meta property="og:image" content="/o.jpg">')
    )
    web.add("https://news.example.org/o.jpg", picture(), headers={"content-type": "image/jpeg"})
    images.fetch(session, web.client(), settings, HostThrottle(0), datetime.now(UTC))
    assert article.image_status == Status.DONE


def test_edition_prints_pictures_for_lead_and_large_stories(session, settings, web) -> None:
    source = add_source(session)
    reader = add_reader(session, [source], story_count=8)
    for i in range(5):
        add_article(
            session,
            source,
            f"Meldung {i}",
            hours_ago=1 + i,
            image_url=f"https://img.example.org/{i}.jpg",
            image_status="pending",
            image_credit="Foto: Test" if i == 0 else None,
        )
    web.add("https://img.example.org/*", picture(), headers={"content-type": "image/jpeg"})
    settings.image_batch = 10
    images.fetch(session, web.client(), settings, HostThrottle(0), datetime.now(UTC))

    payload = compose(session, reader, settings, date.today(), None)
    assert payload["lead"]["image"]["credit"] == "Foto: Test"
    assert payload["lead"]["image"]["alt"] == "Bild zum Artikel „Meldung 0“"  # PDF/UA needs alt text
    with_picture = [s["size"] for s in payload["stories"] if "image" in s]
    assert with_picture == ["large", "large"]  # medium and small stories stay without

    renderer = EditionRenderer(settings.resource_root)
    for theme in ("epaper", "klassisch"):  # the retro theme prints them in black and white
        reader.theme = theme
        edition = build_edition(session, reader, settings, date.today(), None, renderer)
        assert edition.pdf.startswith(b"%PDF") and b"/Image" in edition.pdf


def test_purge_keeps_pictures_in_use(session, settings) -> None:
    source = add_source(session)
    used = Image(url="https://img.example.org/used.jpg", data=b"x", width=1, height=1)
    unused = Image(url="https://img.example.org/old.jpg", data=b"x", width=1, height=1)
    session.add_all([used, unused])
    session.flush()
    add_article(session, source, "A", image_id=used.id)
    old = datetime(2000, 1, 1, tzinfo=UTC)
    used.created_at = unused.created_at = old
    session.flush()
    images.purge_old(session, settings, datetime.now(UTC))
    session.flush()
    assert [i.url for i in session.scalars(select(Image))] == ["https://img.example.org/used.jpg"]


def test_upgrade_backfills_sources_and_recent_articles(engine, session) -> None:
    """Installations from before 0.3.0: catalog picture settings and a second chance for recent articles."""
    from alembic import command

    from eilkurier.migrate import alembic_config

    heise = add_source(session, name="heise", url="https://www.heise.de/rss/heise-atom.xml")
    own = add_source(session, name="Eigene", url="https://example.org/own.rss")
    recent = add_article(session, own, "Neu", hours_ago=2)
    old = add_article(session, own, "Alt", hours_ago=48)
    session.commit()
    config = alembic_config(engine.url.render_as_string(hide_password=False))
    command.downgrade(config, "0004")
    command.upgrade(config, "head")
    session.expire_all()
    assert (heise.image_mode, own.image_mode) == ("page", "auto")
    assert (recent.image_status, old.image_status) == ("pending", "skipped")
