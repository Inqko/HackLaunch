import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


def _send_email_sync(to: str, subject: str, text: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


async def send_email(to: str, subject: str, text: str) -> bool:
    """Отправляет письмо. Без SMTP_HOST пишет его в лог и возвращает False (демо-режим)."""
    if not settings.smtp_host:
        logger.warning(
            "SMTP не настроен. Письмо для %s (%s):\n%s", to, subject, text
        )
        return False
    try:
        await asyncio.to_thread(_send_email_sync, to, subject, text)
        logger.info("Письмо «%s» отправлено на %s", subject, to)
        return True
    except Exception:
        logger.exception("Не удалось отправить письмо на %s", to)
        return False
