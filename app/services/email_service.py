import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(recipient, subject, body):
    settings = current_app.config
    required = ("SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM")
    if not all(settings.get(key) for key in required):
        raise RuntimeError("SMTP is not configured.")
    message = EmailMessage()
    message["From"] = settings["SMTP_FROM"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings["SMTP_HOST"], settings["SMTP_PORT"], timeout=10) as server:
        server.starttls()
        server.login(settings["SMTP_USERNAME"], settings["SMTP_PASSWORD"])
        server.send_message(message)
