"""Pipeline tests against a real Postgres: collect → full text → reporter → edition → delivery."""

import json
from datetime import UTC, datetime, time, timedelta
from typing import ClassVar
from zoneinfo import ZoneInfo

import httpx
from factories import PARAGRAPH, add_article, add_reader, add_source, article_page, rss
from sqlalchemy import func, select

from eilkurier import collect, reporter
from eilkurier.db import Article, CalendarEvent, Channel, Edition, Interest, Letter, Reader, Status, Story
from eilkurier.deliver import deliver, poll_telegram
from eilkurier.edition import compose
from eilkurier.http import HostThrottle
from eilkurier.llm import LLM
from eilkurier.render import EditionRenderer
from eilkurier.worker import Worker, due_readers

# --- collecting ---------------------------------------------------------------------------------


def test_rss_collection_is_idempotent_and_conditional(session, settings, web) -> None:
    source = add_source(session, url="https://example.org/feed.rss")
    web.add(
        "https://example.org/feed.rss",
        rss(
            [
                {"title": "Brücke öffnet", "link": "https://example.org/a"},
                {"title": "Markt", "link": "https://example.org/b"},
            ]
        ),
        headers={"etag": '"v1"'},
    )
    http = web.client()
    assert collect.collect_source(session, source, http, settings) == 2
    assert collect.collect_source(session, source, http, settings) == 0  # same items again
    assert source.etag == '"v1"'
    assert web.requests[-1].headers["if-none-match"] == '"v1"'

    web.add("https://example.org/feed.rss", "", status=304)
    assert collect.collect_source(session, source, http, settings) == 0
    assert source.last_error is None


def test_broken_source_records_error(session, settings, web) -> None:
    source = add_source(session, url="https://example.org/missing.rss")
    assert collect.collect_source(session, source, web.client(), settings) == 0
    assert "404" in source.last_error


def test_fulltext_success_and_paywall(session, settings, web) -> None:
    source = add_source(session)
    good = add_article(
        session, source, "Gut", fulltext=None, fulltext_status=Status.PENDING, url="https://x.org/good"
    )
    wall = add_article(
        session, source, "Wand", fulltext=None, fulltext_status=Status.PENDING, url="https://x.org/wall"
    )
    web.add("https://x.org/good", article_page("Gut"))
    web.add("https://x.org/wall", "<html><body><p>Bitte abonnieren.</p></body></html>")
    assert collect.fetch_fulltexts(session, web.client(), settings, HostThrottle(0)) == 1
    assert good.fulltext_status == Status.DONE and "Mühlbach" in good.fulltext
    assert wall.fulltext_status == Status.SKIPPED and wall.teaser_only


def test_ics_calendar_expands_recurring_events(session, settings, web) -> None:
    today = datetime.now(UTC).date()
    ics = (
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:test\r\n"
        "BEGIN:VEVENT\r\nUID:chor\r\nSUMMARY:Chorprobe\r\n"
        f"DTSTART:{today:%Y%m%d}T180000Z\r\nRRULE:FREQ=DAILY;COUNT=3\r\nEND:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    source = add_source(session, name="Familie", url="https://cal.example.org/family.ics", kind="ics")
    web.add("https://cal.example.org/family.ics", ics)
    assert collect.collect_source(session, source, web.client(), settings) == 3
    assert session.scalar(select(func.count()).select_from(CalendarEvent)) == 3


# --- reporter -----------------------------------------------------------------------------------


def test_reporter_enriches_and_builds_stories(session, settings, simulator_http) -> None:
    source = add_source(session)
    first = add_article(session, source, "Brücke Mühlbach Sanierung beginnt", hours_ago=30)
    second = add_article(session, source, "Brücke Mühlbach Sanierung endet", hours_ago=2)
    other = add_article(
        session, source, "Fußball Bezirksliga Derby", fulltext="Das Derby endete torlos. " * 40, hours_ago=1
    )
    session.commit()

    assert reporter.run(session, LLM(settings, simulator_http), settings) == 3
    for a in (first, second, other):
        session.refresh(a)
        assert a.enrichment_status == Status.DONE and a.embedding is not None
    assert first.story_id == second.story_id != other.story_id
    assert session.scalar(select(func.count()).select_from(Story)) == 2


def test_reporter_waits_when_model_is_away(session, settings) -> None:
    source = add_source(session)
    article = add_article(session, source, "Etwas")
    session.commit()
    down = httpx.Client(base_url="http://x", transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert reporter.run(session, LLM(settings, down), settings) == 0
    session.refresh(article)
    assert article.enrichment_status == Status.PENDING and article.enrichment_attempts == 0


def test_bad_answers_give_up_after_three_attempts(session, settings) -> None:
    source = add_source(session)
    article = add_article(session, source, "Etwas")
    session.commit()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "gemma3:4b"}, {"id": "embeddinggemma"}]})
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "[]"}}]}
        )

    llm = LLM(settings, httpx.Client(base_url="http://x", transport=httpx.MockTransport(handler)))
    for attempt in range(1, 4):  # one attempt per worker pass, so a bad answer doesn't block the queue
        reporter.run(session, llm, settings)
        session.refresh(article)
        assert article.enrichment_attempts == attempt
    assert article.enrichment_status == Status.FAILED


# --- edition ------------------------------------------------------------------------------------


def test_compose_selects_by_interest_and_skips_printed(session, settings, simulator_http) -> None:
    news = add_source(session, name="Zeitung")
    blog = add_source(session, name="Blog")
    reader = add_reader(session, [news, blog], story_count=3)
    reader.interests = []
    session.flush()
    from eilkurier.db import Interest

    reader.interests.append(Interest(term="Gitarre", weight=3))
    themes = [
        "Kartoffelernte",
        "Eisenbahnstrecke",
        "Stadttheater",
        "Feuerwehrfest",
        "Schulneubau",
        "Rathausplatz",
    ]
    for i, theme in enumerate(themes):
        add_article(session, news, f"Meldung {i}", fulltext=f"{theme}! " * 120)
    add_article(
        session, blog, "Neue Gitarre vorgestellt", fulltext="Eine neue Gitarre mit sechs Saiten. " * 20
    )
    add_article(session, news, "Uralt", hours_ago=100)
    session.commit()
    reporter.run(session, LLM(settings, simulator_http), settings)

    edition = compose(session, reader, settings, datetime.now(UTC).date(), None)
    assert edition["lead"]["headline"] == "Neue Gitarre vorgestellt"
    headlines = [s["headline"] for s in edition["stories"]] + [b["headline"] for b in edition["briefs"]]
    assert "Uralt" not in headlines
    assert len(edition["stories"]) == 2  # story_count 3 = lead + 2
    assert sum(1 for h in headlines if h.startswith("Meldung")) <= 3  # max 3 per source in total picks

    session.add(
        Edition(
            reader_id=reader.id,
            number=1,
            issue_date=datetime.now(UTC).date() - timedelta(days=1),
            payload=edition,
        )
    )
    session.flush()
    again = compose(session, reader, settings, datetime.now(UTC).date(), None)
    printed = {edition["lead"]["headline"], *(s["headline"] for s in edition["stories"])}
    assert printed.isdisjoint({s["headline"] for s in again.get("stories", [])})
    assert again["edition"]["number"] == 2


def test_unedited_articles_are_printed_as_excerpts(session, settings) -> None:
    source = add_source(session)
    reader = add_reader(session, [source])
    add_article(session, source, "Ohne Reporter")
    session.flush()
    edition = compose(session, reader, settings, datetime.now(UTC).date(), None)
    assert edition["lead"]["excerpt"] is True
    assert edition["lead"]["body"][0].startswith("Die Stadtverwaltung")
    assert edition["meta"]["edited"] == 0


def test_background_shows_earlier_events(session, settings, simulator_http) -> None:
    source = add_source(session)
    reader = add_reader(session, [source])
    start = "Die Sanierung der Brücke am Mühlbach hat am Montag begonnen. "
    add_article(
        session, source, "Brücke Mühlbach Sanierung beginnt", hours_ago=60, fulltext=start + PARAGRAPH * 3
    )
    add_article(session, source, "Brücke Mühlbach Sanierung endet", hours_ago=2)
    session.commit()
    reporter.run(session, LLM(settings, simulator_http), settings)
    edition = compose(session, reader, settings, datetime.now(UTC).date(), None)
    assert edition["lead"]["headline"] == "Brücke Mühlbach Sanierung endet"
    assert [e.split(": ", 1)[1] for e in edition["lead"]["background"]] == [start.strip()]


def test_empty_edition_still_renders(session, settings) -> None:
    reader = add_reader(session, [])
    session.add(Letter(author="Mama", text="Sonntag Kuchen!"))
    session.flush()
    edition = compose(session, reader, settings, datetime.now(UTC).date(), None)
    assert "lead" not in edition and edition["family"] == [{"from": "Mama", "text": "Sonntag Kuchen!"}]
    assert EditionRenderer(settings.resource_root).render_pdf(edition).startswith(b"%PDF")


# --- scheduling & delivery ----------------------------------------------------------------------


def test_due_readers(session) -> None:
    tz = ZoneInfo("Europe/Berlin")
    now = datetime(2026, 11, 17, 6, 30, tzinfo=tz)  # a Tuesday
    early = add_reader(session, [], name="Früh", delivery_time=time(6, 0))
    add_reader(session, [], name="Spät", delivery_time=time(7, 0))
    add_reader(session, [], name="Wochenende", delivery_time=time(6, 0), delivery_days=[6, 7])
    new = add_reader(session, [], name="Neu", delivery_time=time(6, 0))
    new.created_at = now - timedelta(minutes=5)
    session.flush()
    assert [r.name for r in due_readers(session, now)] == [early.name]
    session.add(Edition(reader_id=early.id, number=1, issue_date=now.date(), payload={}))
    session.flush()
    assert due_readers(session, now) == []


class FakeSMTP:
    sent: ClassVar[list] = []

    def __init__(self, settings) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        pass

    def send_message(self, message) -> None:
        FakeSMTP.sent.append(message)


def test_worker_builds_and_delivers_by_telegram(scope, settings, web, simulator_http) -> None:
    settings.telegram_bot_token = "TOKEN"
    with scope() as s:
        source = add_source(s)
        add_reader(s, [source], channel=Channel.TELEGRAM, telegram_chat_id="42", delivery_time=time(0, 0))
        add_article(s, source, "Brücke öffnet")
    web.add("https://api.telegram.org/botTOKEN/sendDocument", '{"ok": true, "result": {}}')
    web.add("https://api.brightsky.dev/weather", "{}")
    worker = Worker(settings, http=web.client(), llm=LLM(settings, simulator_http), session_scope=scope)
    worker._step("editions", worker.editions)

    with scope() as s:
        edition = s.scalar(select(Edition))
        assert edition.delivery_status == Status.DONE and edition.pdf.startswith(b"%PDF")
    sent = [r for r in web.requests if r.url.path.endswith("/sendDocument")]
    assert len(sent) == 1 and b"application/pdf" in sent[0].content


def test_email_delivery_and_retry(session, settings) -> None:
    settings.smtp_host = "mail.local"
    source = add_source(session)
    reader = add_reader(session, [source], channel=Channel.EMAIL, email="oma@example.org")
    edition = Edition(
        reader=reader, number=3, issue_date=datetime.now(UTC).date(), payload={}, pdf=b"%PDF-1.7"
    )
    session.add(edition)
    session.flush()

    class Broken(FakeSMTP):
        def send_message(self, message) -> None:
            raise OSError("connection refused")

    deliver(edition, settings, httpx.Client(), Broken)
    assert edition.delivery_status == Status.FAILED and "refused" in edition.delivery_error
    FakeSMTP.sent = []
    deliver(edition, settings, httpx.Client(), FakeSMTP)
    assert edition.delivery_status == Status.DONE and edition.delivery_attempts == 2
    message = FakeSMTP.sent[0]
    assert message["To"] == "oma@example.org" and "Nr. 3" in message["Subject"]
    assert next(message.iter_attachments()).get_filename().endswith(".pdf")


def test_without_channel_delivery_is_skipped(session, settings) -> None:
    reader = add_reader(session, [])
    edition = Edition(reader=reader, number=1, issue_date=datetime.now(UTC).date(), payload={}, pdf=b"x")
    session.add(edition)
    session.flush()
    deliver(edition, settings, httpx.Client())
    assert edition.delivery_status == Status.SKIPPED


def test_telegram_link_letters_and_commands(session, settings, web) -> None:
    settings.telegram_bot_token = "TOKEN"
    reader = add_reader(session, [], name="Oma", telegram_link_code="ABC234")
    session.flush()
    updates = [
        {"update_id": 10, "message": {"chat": {"id": 99}, "text": "/start abc234"}},
        {"update_id": 11, "message": {"chat": {"id": 99}, "text": "Am Sonntag gibt es Datschi!"}},
        {"update_id": 12, "message": {"chat": {"id": 7}, "text": "Hallo?"}},
        {"update_id": 13, "message": {"chat": {"id": 99}, "text": "/ausgabe"}},
    ]
    web.add("https://api.telegram.org/botTOKEN/getUpdates", json.dumps({"ok": True, "result": updates}))
    web.add("https://api.telegram.org/botTOKEN/sendMessage", '{"ok": true, "result": {}}')
    assert poll_telegram(session, settings, web.client()) == 4
    assert reader.telegram_chat_id == "99" and reader.telegram_link_code is None
    assert reader.channel == Channel.TELEGRAM
    letter = session.scalar(select(Letter))
    assert letter.author == "Oma" and letter.via == "telegram"
    replies = [r for r in web.requests if r.url.path.endswith("/sendMessage")]
    assert len(replies) == 4  # linked, thanks, unknown chat, no edition yet

    poll_telegram(session, settings, web.client())
    get_updates = [r for r in web.requests if r.url.path.endswith("/getUpdates")]
    assert b'"offset":14' in get_updates[-1].content.replace(b" ", b"")


def test_purge_old_articles(session, settings) -> None:
    source = add_source(session)
    add_article(session, source, "Alt", hours_ago=24 * 90)
    add_article(session, source, "Neu")
    collect.purge_old(session, settings, datetime.now(UTC))
    assert [a.title for a in session.scalars(select(Article))] == ["Neu"]


def test_reader_deletion_cascades(session) -> None:
    source = add_source(session)
    reader = add_reader(session, [source])
    session.add(Edition(reader=reader, number=1, issue_date=datetime.now(UTC).date(), payload={}))
    session.flush()
    session.delete(reader)
    session.flush()
    assert session.scalar(select(func.count()).select_from(Edition)) == 0
    assert session.scalar(select(func.count()).select_from(Reader)) == 0


def test_reporter_works_on_likely_printed_articles_first(session) -> None:
    subscribed, other = add_source(session), add_source(session, "Nachbarort-Bote")
    add_reader(session, [subscribed], interests=[Interest(term="Garten", weight=2)])
    newest = add_article(session, subscribed, "Neuer Bahnhof eröffnet", hours_ago=1)
    garden = add_article(session, subscribed, "Garten im Herbst winterfest machen", hours_ago=10)
    unsubscribed = add_article(session, other, "Garten-Tipps aus dem Nachbarort", hours_ago=0.5)
    old = add_article(session, subscribed, "Garten-Rückblick", hours_ago=24 * 5)
    session.commit()
    order = reporter.work_order(session, datetime.now(UTC))
    assert order == [garden.id, newest.id, unsubscribed.id, old.id]
