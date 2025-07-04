#!/usr/bin/env python3
"""Send JSON fact‑check results via Gmail.

This utility reads the file ``factcheck_dirs_for_transcription.txt`` created by
``email_video_runner.py``. Each line in that file should be a directory
containing processed videos with ``.json`` metadata produced by the pipeline.
Every JSON file found is emailed as an attachment to the provided recipient.
"""

import argparse
import logging
import mimetypes
import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path


def get_env_var(name: str, default: str | None = None, required: bool = False) -> str | None:
    """Fetch an environment variable with optional requirement."""
    val = os.environ.get(name, default)
    if required and not val:
        print(f"[x] Missing required environment variable: {name}")
        sys.exit(1)
    return val


def load_factcheck_dirs(list_path: str = "factcheck_dirs_for_transcription.txt") -> list[str]:
    """Return directories containing fact‑check results."""
    if not os.path.exists(list_path):
        logging.warning(f"[!] Factcheck directories list not found: {list_path}")
        return []
    with open(list_path, "r", encoding="utf-8") as f:
        dirs = [line.strip() for line in f if line.strip()]
    if not dirs:
        logging.warning(f"[!] No directories listed in {list_path}.")
    return dirs


def send_email_with_attachment(sender: str, password: str, recipient: str, subject: str, body: str | None, attachment_path: Path) -> None:
    """Send a single email with ``attachment_path`` as an attachment."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid()
    msg.set_content(body or "See attached factcheck results.")

    with open(attachment_path, "rb") as f:
        data = f.read()
    mime = mimetypes.guess_type(str(attachment_path))[0] or "application/json"
    maintype, subtype = mime.split("/", 1)
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=attachment_path.name)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)
        logging.info(f"[i] Sent: {subject} to {recipient}")
    except Exception as e:
        logging.error(f"[x] Failed to send {attachment_path}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Email JSON fact‑check responses")
    parser.add_argument("recipient", help="Destination email address")
    parser.add_argument("--list_path", default="factcheck_dirs_for_transcription.txt", help="File with directories to scan")
    parser.add_argument("--glob", default="*.json", help="Glob pattern for JSON files")
    parser.add_argument("--subject_prefix", default="[FACTCHECK - RESPONSE] ", help="Subject prefix for each email")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    sender = get_env_var("GMAIL_EMAIL", required=True)
    # Gmail App password stored in GMAIL_PASSWD
    password = get_env_var("GMAIL_PASSWD", required=True)

    fact_dirs = load_factcheck_dirs(args.list_path)
    if not fact_dirs:
        logging.info("[i] No factcheck directories to process. Exiting.")
        return

    json_files: list[Path] = []
    for d in fact_dirs:
        p = Path(d)
        if not p.is_dir():
            logging.warning(f"[!] Directory not found or not a directory: {d}")
            continue
        found = list(p.glob(args.glob))
        if found:
            logging.info(f"[i] Found {len(found)} JSON file(s) in {d}")
            json_files.extend(found)
        else:
            logging.info(f"[i] No JSON files found in {d}")

    if not json_files:
        logging.info("[i] No JSON files to send. Exiting.")
        return

    for jf in json_files:
        subj = f"{args.subject_prefix}{jf.name}"
        send_email_with_attachment(sender, password, args.recipient, subj, None, jf)


if __name__ == "__main__":
    main()
