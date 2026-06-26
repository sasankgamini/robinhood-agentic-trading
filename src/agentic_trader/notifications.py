from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Notifier:
    def send(self, subject: str, body: str) -> None:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    def send(self, subject: str, body: str) -> None:
        print(f"[notification] {subject}\n{body}")


class EmailNotifier(Notifier):
    def __init__(self, config: dict):
        self.config = config

    def send(self, subject: str, body: str) -> None:
        host = os.environ[self.config["smtp_host_env"]]
        port = int(os.environ.get(self.config["smtp_port_env"], "587"))
        user = os.environ[self.config["smtp_user_env"]]
        password = os.environ[self.config["smtp_password_env"]]
        email_to = os.environ[self.config["email_to_env"]]
        email_from = os.environ.get(self.config["email_from_env"], user)

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = email_from
        message["To"] = email_to
        message.set_content(body)

        with smtplib.SMTP(host, port) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(message)


def build_notifier(config: dict) -> Notifier:
    load_dotenv()
    if config.get("email_enabled"):
        return EmailNotifier(config)
    return ConsoleNotifier()
