"""SMTP delivery for recommendation digest emails."""

from __future__ import annotations

import argparse
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import time
from typing import Callable

from paper_recommender.emailer import render_email_html


def build_email_message(subject: str, sender: str, receiver: str, html: str) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = receiver
    message.set_content(html, subtype="html")
    return message


def should_send_digest(payload: dict, send_empty: bool = False) -> bool:
    return send_empty or bool(payload.get("recommendations"))


def send_email_message(
    message: EmailMessage,
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    use_ssl: bool = True,
) -> None:
    if use_ssl:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)


def send_email_message_with_retries(
    message: EmailMessage,
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    use_ssl: bool = True,
    attempts: int = 3,
    send_func: Callable[..., None] = send_email_message,
    sleep_func: Callable[[float], None] = time.sleep,
) -> int:
    max_attempts = max(1, attempts)
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            send_func(
                message=message,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                username=username,
                password=password,
                use_ssl=use_ssl,
            )
            return attempt
        except Exception as error:
            last_error = error
            if attempt < max_attempts:
                sleep_func(float(attempt))
    if last_error is not None:
        raise last_error
    raise RuntimeError("Email delivery failed without an exception")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send recommendation digest email.")
    parser.add_argument("--recommendations", required=True, help="Recommendation JSON payload.")
    parser.add_argument("--subject", default=None, help="Email subject override.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum SMTP delivery attempts.")
    parser.add_argument("--send-empty", action="store_true", help="Send email even when there are no recommendations.")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.recommendations).read_text(encoding="utf-8"))
    if not should_send_digest(payload, send_empty=args.send_empty):
        print("Skipped email digest because there are no recommendations")
        return 0

    site_base_url = _required_env("SITE_BASE_URL")
    feedback_base_url = os.environ.get("FEEDBACK_BASE_URL", f"{site_base_url.rstrip('/')}/feedback.html")
    html = render_email_html(payload, site_base_url=site_base_url, feedback_base_url=feedback_base_url)

    sender = _required_env("EMAIL_SENDER")
    receiver = _required_env("EMAIL_RECEIVER")
    subject = args.subject or f"Daily arXiv Recommendations - {payload.get('run_date', '')}"
    message = build_email_message(subject=subject, sender=sender, receiver=receiver, html=html)

    smtp_host = _required_env("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    username = os.environ.get("SMTP_USERNAME", sender)
    password = _required_env("SMTP_PASSWORD")
    use_ssl = os.environ.get("SMTP_USE_SSL", "true").lower() != "false"
    attempts_used = send_email_message_with_retries(
        message,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        username=username,
        password=password,
        use_ssl=use_ssl,
        attempts=args.max_attempts,
    )
    print(f"Sent recommendation digest to {receiver} after {attempts_used} attempt(s)")
    return 0


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
