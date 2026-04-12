"""
Email utility — sends mail via Gmail SMTP.
Credentials are read from the [mail] section of db.ini.
"""

import configparser
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

_config_path = Path(__file__).parent / "db.ini"


def _get_mail_config():
    cfg = configparser.ConfigParser()
    cfg.read(_config_path)
    return cfg["mail"]


def _markdown_to_html(text):
    """Convert a small subset of markdown to HTML.

    Handles:
      - **bold** → <strong>
      - Paragraphs separated by blank lines → <p> blocks
      - URLs → <a href>
    """
    # Escape HTML special chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # **bold**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    # Auto-link URLs
    text = re.sub(
        r"(https?://[^\s]+)",
        r'<a href="\1">\1</a>',
        text,
    )

    # Split into paragraphs on blank lines, join lines within each paragraph with <br>
    paragraphs = re.split(r"\n\s*\n", text.strip())
    html_paragraphs = [
        "<p>" + p.strip().replace("\n", "<br>\n") + "</p>"
        for p in paragraphs if p.strip()
    ]

    return "\n".join(html_paragraphs)


def send_email(to, subject, body):
    """Send a plain-text + HTML multipart email.

    Args:
        to      : recipient address (string)
        subject : email subject line
        body    : plain-text body (simple markdown supported)
    """
    c = _get_mail_config()

    msg = MIMEMultipart("alternative")
    msg["From"]    = f"{c['name']} <{c['user']}>"
    msg["To"]      = to
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(_markdown_to_html(body), "html"))

    with smtplib.SMTP(c["host"], int(c["port"])) as smtp:
        smtp.starttls()
        smtp.login(c["user"], c["password"])
        smtp.send_message(msg)
