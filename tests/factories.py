"""Test data: feeds, article pages and database rows."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

from sqlalchemy.orm import Session

from eilkurier.db import Article, Reader, Source, Status

PARAGRAPH = (
    "Die Stadtverwaltung teilte am Montag mit, dass die Brücke über den Mühlbach am Freitag wieder "
    "freigegeben wird. Die Sanierung hat elf Monate gedauert und rund 2,3 Millionen Euro gekostet. "
    "Für Pendler aus den nördlichen Ortsteilen endet damit eine Umleitung von acht Kilometern. "
)


def rss(items: list[dict], title: str = "Testfeed") -> str:
    entries = []
    for item in items:
        published = format_datetime(item.get("published", datetime.now(UTC) - timedelta(hours=1)))
        entries.append(
            f"<item><title>{item['title']}</title><link>{item['link']}</link><guid>{item['link']}</guid>"
            f"<description>{item.get('teaser', 'Anreißer')}</description>"
            f"<pubDate>{published}</pubDate></item>"
        )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{title}</title>'
        f"<link>https://example.org</link><description>t</description>{''.join(entries)}</channel></rss>"
    )


EXTRA = (
    "Der Bürgermeister bedankte sich bei den Anwohnern für ihre Geduld während der langen Bauzeit.",
    "Auch die Buslinie 4 fährt ab Freitag wieder ihre gewohnte Strecke über die Brücke.",
    "Das Geländer auf der Westseite wird erst im kommenden Frühjahr vollständig erneuert.",
    "Bis dahin bleibt der Fußweg auf dieser Seite gesperrt, Fußgänger nutzen die Ostseite.",
)


def article_page(title: str, paragraphs: int = 4) -> str:
    body = "".join(f"<p>{EXTRA[i % len(EXTRA)]} {PARAGRAPH if i == 0 else ''}</p>" for i in range(paragraphs))
    return (
        f"<html><head><title>{title}</title></head><body><nav>Menü Start Impressum</nav>"
        f"<article><h1>{title}</h1>{body}</article><footer>© Testverlag</footer></body></html>"
    )


def add_source(session: Session, name: str = "Musterstädter Anzeiger", **kw) -> Source:
    source = Source(name=name, url=kw.pop("url", f"https://example.org/{name}.rss"), category="Region", **kw)
    session.add(source)
    session.flush()
    return source


def add_reader(session: Session, sources: list[Source], **kw) -> Reader:
    reader = Reader(name=kw.pop("name", "Papa"), sources=sources, **kw)
    reader.created_at = datetime.now(UTC) - timedelta(days=30)
    session.add(reader)
    session.flush()
    return reader


def add_article(session: Session, source: Source, title: str, hours_ago: float = 1, **kw) -> Article:
    article = Article(
        source=source,
        guid=kw.pop("guid", f"{source.id}-{title}"),
        url=kw.pop("url", f"https://example.org/{abs(hash(title))}"),
        title=title,
        teaser=kw.pop("teaser", "Kurzer Anreißer."),
        published_at=datetime.now(UTC) - timedelta(hours=hours_ago),
        fulltext=kw.pop("fulltext", PARAGRAPH * 3),
        fulltext_status=kw.pop("fulltext_status", Status.DONE),
        **kw,
    )
    session.add(article)
    session.flush()
    return article
