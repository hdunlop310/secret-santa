import logging
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import parseaddr
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# Personal links carry tokens; anything that prints an email must strip them first.
_LINK_RE = re.compile(r"https?://\S+/(?:g|p)/[A-Za-z0-9_-]+\S*")


def redact_links(text: str) -> str:
    return _LINK_RE.sub("[private link]", text)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class EmailSender(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailSender:
    """Prints emails for local development, with private links redacted."""

    def send(self, message: EmailMessage) -> None:
        print(f"[email] to={message.to} subject={message.subject!r}")
        print(redact_links(message.text))


class MemoryEmailSender:
    """Keeps sent emails in a list. Used by tests."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)


class SmtpEmailSender:
    def __init__(self, host: str, port: int, sender: str) -> None:
        self.host, self.port, self.sender = host, port, sender

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self.sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            smtp.send_message(mime)


class ResendEmailSender:
    def __init__(self, api_key: str, sender: str) -> None:
        self.api_key, self.sender = api_key, sender

    def send(self, message: EmailMessage) -> None:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "from": self.sender,
                "to": [message.to],
                "subject": message.subject,
                "text": message.text,
                "html": message.html,
            },
            timeout=10,
        )
        response.raise_for_status()


@lru_cache
def get_email_sender() -> EmailSender:
    settings = get_settings()
    match settings.email_backend:
        case "smtp":
            return SmtpEmailSender(settings.smtp_host, settings.smtp_port, settings.email_from)
        case "resend":
            return ResendEmailSender(settings.resend_api_key, settings.email_from)
        case _:
            return ConsoleEmailSender()


def send_safely(sender: EmailSender, message: EmailMessage) -> None:
    """Send an email without letting a delivery failure break the request.

    Logs only the recipient domain and error type: never the body, which holds links.
    """
    try:
        sender.send(message)
    except Exception as exc:
        domain = parseaddr(message.to)[1].rpartition("@")[2]
        log.warning("email to @%s failed: %s", domain, type(exc).__name__)
