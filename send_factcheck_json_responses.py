#!/usr/bin/env python3

import os
import sys
import smtplib
import logging
from pathlib import Path
from email.message import EmailMessage
from email.utils import make_msgid

import mimetypes

def get_env_var(name, default=None, required=False):
    val = os.environ.get(name, default)
    if required and not val:
        print(f"[x] Missing required environment variable: {name}")
        sys.exit(1)
    return val

def load_factcheck_dirs(list_path="factcheck_dirs_for_transcription.txt"):
    """Load list of directories to process, or None if not present."""
    if not os.path.exists(list_path):
        logging.warning(f"[!] Factcheck directories list not found: {list_path}")
        return []
    with open(list_path, "r", encoding="utf-8") as f:
        dirs = [line.strip() for line in f if line.strip()]
    if not dirs:
        logging.warning(f"[!] No directories listed in {list_path}.")
    return dirs

def send_email_with_attachment(sender, password, recipient, subject, body, attachment_path):
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = subject
    msg['Message-ID'] = make_msgid()
    msg.set_content(body or "See attached factcheck results.")

    # Add the JSON attachment
    with open(attachment_path, 'rb') as f:
        data = f.read()
    maintype, subtype = mimetypes.guess_type(attachment_path)[0].split('/')
    filename = os.path.basename(attachment_path)
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    # Connect and send
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        logging.info(f"[i] Sent: {subject} to {recipient}")
    except Exception as e:
        logging.error(f"[x] Failed to send {attachment_path}: {e}")

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    sender = get_env_var("GMAIL_EMAIL", required=True)
    password = get_env_var("GMAIL_APP_PASSWORD", requ

