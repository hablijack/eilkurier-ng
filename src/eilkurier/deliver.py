"""Delivery of finished editions (Telegram, e-mail) and the Telegram bot's inbox (linking, letters)."""

import logging
import secrets
import smtplib
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from eilkurier.db import Channel, Edition, Letter, Reader, Status, kv_get, kv_set
from eilkurier.settings import Settings

log = logging.getLogger(__name__)

MAX_DELIVERY_ATTEMPTS = 5
LINK_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I

_TEXTS = {
    "de": {
        "caption": "Dein Eilkurier, Ausgabe Nr. {number} vom {date}",
        "subject": "Eilkurier Nr. {number} – {date}",
        "mail_body": "Guten Morgen {name},\n\nim Anhang findest du deine heutige Ausgabe.\n\nDein Eilkurier",
        "linked": "Hallo {name}! Ab jetzt bringt dir der Eilkurier deine Zeitung hierher.",
        "letter_thanks": "Danke! Dein Leserbrief erscheint in der nächsten Ausgabe der Familie.",
        "unknown": "Hallo! Bitte schick mir zuerst den Verknüpfungscode aus der Eilkurier-Weboberfläche.",
        "no_edition": "Es gibt noch keine Ausgabe für dich.",
    },
    "en": {
        "caption": "Your Eilkurier, issue no. {number} of {date}",
        "subject": "Eilkurier no. {number} – {date}",
        "mail_body": "Good morning {name},\n\nattached is today's edition.\n\nYour Eilkurier",
        "linked": "Hello {name}! From now on Eilkurier delivers your paper here.",
        "letter_thanks": "Thanks! Your letter will appear in the family's next edition.",
        "unknown": "Hello! Please send me the link code from the Eilkurier web interface first.",
        "no_edition": "There is no edition for you yet.",
    },
}


def texts(lang: str) -> dict[str, str]:
    return _TEXTS.get(lang, _TEXTS["de"])


def new_link_code() -> str:
    return "".join(secrets.choice(LINK_CODE_ALPHABET) for _ in range(6))


def _filename(edition: Edition) -> str:
    return f"eilkurier-{edition.issue_date.isoformat()}.pdf"


class Telegram:
    def __init__(self, settings: Settings, http: httpx.Client) -> None:
        self.base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
        self.http = http

    def call(self, method: str, **kwargs: Any) -> Any:
        response = self.http.post(f"{self.base}/{method}", **kwargs)
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method}: {data.get('description', response.status_code)}")
        return data["result"]

    def send_message(self, chat_id: str, text: str) -> None:
        self.call("sendMessage", json={"chat_id": chat_id, "text": text})

    def send_document(self, chat_id: str, filename: str, content: bytes, caption: str) -> None:
        self.call(
            "sendDocument",
            data={"chat_id": chat_id, "caption": caption},
            files={"document": (filename, content, "application/pdf")},
        )

    def updates(self, offset: int) -> list[dict[str, Any]]:
        return self.call("getUpdates", json={"offset": offset, "timeout": 0, "allowed_updates": ["message"]})


SmtpFactory = Callable[[Settings], smtplib.SMTP]


def default_smtp(settings: Settings) -> smtplib.SMTP:
    smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
    if settings.smtp_starttls:
        smtp.starttls()
    if settings.smtp_user:
        smtp.login(settings.smtp_user, settings.smtp_password)
    return smtp


def deliver(
    edition: Edition,
    settings: Settings,
    http: httpx.Client,
    smtp_factory: SmtpFactory = default_smtp,
) -> None:
    """Send the edition on the reader's channel. Records the outcome on the edition; never raises."""
    reader = edition.reader
    t = texts(reader.language)
    date_label = edition.issue_date.strftime("%d.%m.%Y")
    edition.delivery_attempts += 1
    try:
        if reader.channel == Channel.TELEGRAM and reader.telegram_chat_id and settings.telegram_enabled:
            Telegram(settings, http).send_document(
                reader.telegram_chat_id,
                _filename(edition),
                edition.pdf or b"",
                t["caption"].format(number=edition.number, date=date_label),
            )
        elif reader.channel == Channel.EMAIL and reader.email and settings.smtp_enabled:
            message = EmailMessage()
            message["From"] = settings.smtp_from
            message["To"] = reader.email
            message["Subject"] = t["subject"].format(number=edition.number, date=date_label)
            message.set_content(t["mail_body"].format(name=reader.name))
            message.add_attachment(
                edition.pdf or b"", maintype="application", subtype="pdf", filename=_filename(edition)
            )
            with smtp_factory(settings) as smtp:
                smtp.send_message(message)
        else:
            edition.delivery_status = Status.SKIPPED
            edition.delivery_error = "no delivery channel configured"
            return
    except (httpx.HTTPError, smtplib.SMTPException, OSError, RuntimeError, ValueError) as exc:
        log.warning("delivery of edition %s failed: %s", edition.id, exc)
        edition.delivery_error = f"{type(exc).__name__}: {exc}"[:1000]
        edition.delivery_status = (
            Status.FAILED if edition.delivery_attempts < MAX_DELIVERY_ATTEMPTS else Status.SKIPPED
        )
        return
    edition.delivery_status = Status.DONE
    edition.delivery_error = None
    edition.delivered_at = datetime.now(UTC)


def poll_telegram(session: Session, settings: Settings, http: httpx.Client) -> int:
    """Process bot messages: link codes connect a chat to a reader; other texts become letters."""
    if not settings.telegram_enabled:
        return 0
    bot = Telegram(settings, http)
    offset = int(kv_get(session, "telegram_offset", "0") or 0)
    try:
        updates = bot.updates(offset)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        log.info("telegram polling failed: %s", exc)
        return 0
    handled = 0
    for update in updates:
        offset = max(offset, update["update_id"] + 1)
        message = update.get("message") or {}
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = (message.get("text") or message.get("caption") or "").strip()
        if not chat_id or not text:
            continue
        try:
            _handle_message(session, bot, chat_id, text)
            handled += 1
        except (httpx.HTTPError, RuntimeError) as exc:
            log.info("telegram reply failed: %s", exc)
    kv_set(session, "telegram_offset", str(offset))
    return handled


def _handle_message(session: Session, bot: Telegram, chat_id: str, text: str) -> None:
    reader = session.scalar(select(Reader).where(Reader.telegram_chat_id == chat_id))
    code = text.removeprefix("/start").strip().upper()
    if reader is None:
        candidate = session.scalar(select(Reader).where(Reader.telegram_link_code == code)) if code else None
        if candidate is None:
            bot.send_message(chat_id, texts("de")["unknown"])
            return
        candidate.telegram_chat_id = chat_id
        candidate.telegram_link_code = None
        if candidate.channel == Channel.NONE:
            candidate.channel = Channel.TELEGRAM
        bot.send_message(chat_id, texts(candidate.language)["linked"].format(name=candidate.name))
        return
    if text.startswith("/ausgabe") or text.startswith("/edition"):
        latest = session.scalar(
            select(Edition).where(Edition.reader_id == reader.id).order_by(Edition.issue_date.desc()).limit(1)
        )
        if latest is None or latest.pdf is None:
            bot.send_message(chat_id, texts(reader.language)["no_edition"])
        else:
            bot.send_document(chat_id, _filename(latest), latest.pdf, f"Eilkurier Nr. {latest.number}")
        return
    if text.startswith("/"):
        return
    session.add(Letter(author=reader.name, text=text[:1000], reader_id=reader.id, via="telegram"))
    bot.send_message(chat_id, texts(reader.language)["letter_thanks"])
