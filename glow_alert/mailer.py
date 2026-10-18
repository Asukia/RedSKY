"""SMTP sender. Credentials come only from environment variables (GitHub Secrets).

Port 465 -> implicit TLS (SMTP_SSL); any other port -> STARTTLS.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    user: str
    password: str
    sender: str

    @classmethod
    def from_env(cls) -> "SmtpSettings":
        missing = [k for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD") if not os.environ.get(k)]
        if missing:
            raise RuntimeError(f"missing environment variables: {missing}")
        return cls(
            host=os.environ["SMTP_HOST"],
            port=int(os.environ.get("SMTP_PORT") or 465),
            user=os.environ["SMTP_USER"],
            password=os.environ["SMTP_PASSWORD"],
            sender=os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"],
        )


def send_email(settings: SmtpSettings, to: tuple[str, ...], subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.sender
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    if settings.port == 465:
        with smtplib.SMTP_SSL(settings.host, settings.port, context=context, timeout=30) as s:
            s.login(settings.user, settings.password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.host, settings.port, timeout=30) as s:
            s.starttls(context=context)
            s.login(settings.user, settings.password)
            s.send_message(msg)
