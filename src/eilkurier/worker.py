"""The worker: one loop that collects, enriches, builds and delivers. Stateless; all state is in Postgres."""

import logging
import signal
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from eilkurier import collect, deliver, reporter
from eilkurier.db import Edition, Reader, Status, kv_get, kv_set, session_scope
from eilkurier.edition import build_edition
from eilkurier.http import HostThrottle, make_client
from eilkurier.llm import LLM
from eilkurier.render import EditionRenderer
from eilkurier.settings import Settings

log = logging.getLogger(__name__)

TICK_SECONDS = 30


def due_readers(session: Session, local_now: datetime) -> list[Reader]:
    """Readers whose delivery time has passed today and who have no edition for today yet."""
    today = local_now.date()
    done = select(Edition.reader_id).where(Edition.issue_date == today)
    readers = session.scalars(
        select(Reader)
        .options(selectinload(Reader.interests))
        .where(Reader.active, Reader.id.not_in(done), Reader.delivery_time <= local_now.time())
    ).all()
    due = []
    for reader in readers:
        if local_now.isoweekday() not in (reader.delivery_days or []):
            continue
        # Readers created after today's delivery time start with their next regular edition.
        scheduled = datetime.combine(today, reader.delivery_time, tzinfo=local_now.tzinfo)
        if reader.created_at and reader.created_at > scheduled:
            continue
        due.append(reader)
    return due


def retry_deliveries(session: Session) -> list[Edition]:
    return list(
        session.scalars(
            select(Edition)
            .where(
                Edition.delivery_status == Status.FAILED,
                Edition.delivery_attempts < deliver.MAX_DELIVERY_ATTEMPTS,
            )
            .order_by(Edition.created_at)
        )
    )


class Worker:
    def __init__(
        self,
        settings: Settings,
        http: httpx.Client | None = None,
        llm: LLM | None = None,
        renderer: EditionRenderer | None = None,
        session_scope: Callable = session_scope,
        smtp_factory: deliver.SmtpFactory = deliver.default_smtp,
    ) -> None:
        self.settings = settings
        self.http = http or make_client(settings)
        self.llm = llm or (LLM(settings) if settings.llm_enabled else None)
        self.renderer = renderer or EditionRenderer(settings.resource_root)
        self.session_scope = session_scope
        self.smtp_factory = smtp_factory
        self.throttle = HostThrottle()
        self.stopping = False

    def _step(self, name: str, fn: Callable[[Session], object]) -> None:
        """Run one step in its own transaction; a failing step never blocks the others."""
        try:
            with self.session_scope() as session:
                result = fn(session)
            if result:
                log.info("%s: %s", name, result)
        except Exception:
            log.exception("step %s failed", name)

    # -- steps ----------------------------------------------------------------------------------

    def editions(self, session: Session) -> int:
        local_now = datetime.now(ZoneInfo(self.settings.timezone))
        count = 0
        for reader in due_readers(session, local_now):
            edition = build_edition(
                session, reader, self.settings, local_now.date(), self.http, self.renderer
            )
            deliver.deliver(edition, self.settings, self.http, self.smtp_factory)
            session.commit()
            count += 1
        for edition in retry_deliveries(session):
            deliver.deliver(edition, self.settings, self.http, self.smtp_factory)
            session.commit()
        return count

    def telegram(self, session: Session) -> int:
        return deliver.poll_telegram(session, self.settings, self.http)

    def collect(self, session: Session) -> int:
        now = datetime.now(UTC)
        total = 0
        for source in collect.due_sources(session, self.settings, now):
            total += collect.collect_source(session, source, self.http, self.settings)
            session.commit()
        return total

    def fulltexts(self, session: Session) -> int:
        return collect.fetch_fulltexts(session, self.http, self.settings, self.throttle)

    def reporter(self, session: Session) -> int:
        if self.llm is None:
            return 0
        return reporter.run(session, self.llm, self.settings, budget_seconds=120)

    def housekeeping(self, session: Session) -> None:
        today = date.today().isoformat()
        if kv_get(session, "housekeeping") != today:
            collect.purge_old(session, self.settings, datetime.now(UTC))
            kv_set(session, "housekeeping", today)

    def tick(self) -> None:
        # Time-critical first: editions and deliveries, then the bot, then the slow pipeline.
        self._step("editions", self.editions)
        self._step("telegram", self.telegram)
        self._step("collect", self.collect)
        self._step("fulltext", self.fulltexts)
        self._step("reporter", self.reporter)
        self._step("housekeeping", self.housekeeping)

    def run_forever(self) -> None:
        def stop(*_: object) -> None:
            log.info("stopping after the current step")
            self.stopping = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        log.info(
            "worker started (LLM: %s, Telegram: %s, e-mail: %s)",
            self.settings.llm_url or "none",
            self.settings.telegram_enabled,
            self.settings.smtp_enabled,
        )
        while not self.stopping:
            started = time.monotonic()
            self.tick()
            remaining = TICK_SECONDS - (time.monotonic() - started)
            while remaining > 0 and not self.stopping:
                time.sleep(min(1.0, remaining))
                remaining -= 1.0
