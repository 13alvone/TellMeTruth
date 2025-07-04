#!/usr/bin/env python3
"""
email_video_runner.py

Fetches Gmail messages using gmailtail, extracts URLs, and downloads videos using yt-dlp
with retry and cookie support.
"""
import argparse
from gmailtail.config import Config
from gmailtail.gmailtail import GmailTail, OutputFormatter
import sys
import logging
import time
import os
import re
import random

import yt_dlp

from utils import (
    DB_PATH,
    initialize_database,
    is_url_downloaded,
    record_successful_download,
    safe_filename,
)

# ---------------------- Constants ----------------------
YTDLP_COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE")
FACTCHECK_KEYWORD = "factcheck"
FACTCHECK_RESPONSE_PREFIX = "[FACTCHECK - RESPONSE] - "  # New for loop prevention

# ---------------------- DB Functions ----------------------
# Provided by utils module

# ---------------------- Filename Utility ----------------------
# Provided by utils module



# ---------------------- Download with yt-dlp ----------------------

def download_with_ytdlp(
    url: str,
    output_dir: str,
    fallback_title: str,
    retries: int = 3,
    db_path: str = DB_PATH
) -> bool:
    if is_url_downloaded(url, db_path=db_path):
        msg = f"[i] URL already downloaded: {url}. Skipping."
        logging.info(msg)
        print(msg)
        return True
    ydl_opts = {
        'outtmpl': os.path.join(output_dir, '%(title).150s.%(ext)s'),
        'quiet': True,
        'noplaylist': True,
    }
    if YTDLP_COOKIES_FILE:
        ydl_opts['cookiefile'] = YTDLP_COOKIES_FILE
        logging.debug(f"[DEBUG] Using cookies file: {YTDLP_COOKIES_FILE}")
    os.makedirs(output_dir, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            print(f"[DOWNLOAD] Attempting ({attempt}/{retries}) -> {url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title') or fallback_title
                safe_title = safe_filename(title)
                record_successful_download(url, safe_title, db_path=db_path)
                msg = f"[DOWNLOAD] SUCCESS: {safe_title} ({url})"
                logging.info(msg)
                print(msg)
                return True
        except Exception as exc:
            msg = f"[DOWNLOAD] ERROR on {url}: {exc}"
            logging.error(msg)
            print(msg)
        if attempt < retries:
            backoff = random.uniform(1, 3)
            msg = f"[DOWNLOAD] Retrying in {backoff:.2f}s for {url}"
            logging.info(msg)
            print(msg)
            time.sleep(backoff)
    msg = f"[DOWNLOAD] All {retries} attempts failed for {url}. Giving up."
    logging.error(msg)
    print(msg)
    return False

# ---------------------- Message Processing ----------------------

def process_messages(
    messages,
    approved_senders,
    url_logfile,
    db_path,
    retries,
):
    """Process a list of message dictionaries returned by gmailtail."""
    factcheck_dirs = []

    for message in messages:
        sender = (message.get('from', {}).get('email') or '').lower()
        if approved_senders and sender not in approved_senders:
            msg = f"[i] Skipping email from {sender}; not approved."
            logging.info(msg)
            print(msg)
            continue

        subject = (message.get('subject') or 'NoSubject').strip()
        if subject.lower().startswith(FACTCHECK_RESPONSE_PREFIX.lower()):
            msg = f"[i] Skipping response email with subject: {subject}"
            logging.info(msg)
            print(msg)
            continue

        is_factcheck = FACTCHECK_KEYWORD.lower() in subject.lower()

        body_text = message.get('body', '') or message.get('snippet', '')
        urls = re.findall(r'https?://\S+', body_text)
        with open(url_logfile, 'a', encoding='utf-8') as f_out:
            for url in urls:
                f_out.write(url + '\n')
        if not urls:
            msg = "[i] No URLs found in message."
            logging.info(msg)
            print(msg)
            continue

        for url in urls:
            output_dir = os.path.join('downloads', safe_filename(subject, 100))
            msg = f"[i] Downloading URL: {url} to {output_dir}"
            logging.info(msg)
            print(msg)
            success = download_with_ytdlp(url, output_dir, subject, retries, db_path)
            if success:
                msg = f"[i] Download succeeded for {url}"
                logging.info(msg)
                print(msg)
                if is_factcheck and output_dir not in factcheck_dirs:
                    factcheck_dirs.append(output_dir)
                    msg = f"[FACTCHECK] Marked for transcription: {output_dir}"
                    logging.info(msg)
                    print(msg)
            else:
                msg = f"[x] Download failed for {url}"
                logging.error(msg)
                print(msg)

    if factcheck_dirs:
        with open('factcheck_dirs_for_transcription.txt', 'w', encoding='utf-8') as f:
            for d in factcheck_dirs:
                f.write(d + '\n')
        msg = f"[i] Wrote {len(factcheck_dirs)} factcheck dirs for transcription."
        logging.info(msg)
        print(msg)

# ---------------------- CLI & Main ----------------------
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Fetch Gmail messages and download video URLs"
    )
    parser.add_argument('gmail_email', nargs='?', help='Gmail address')
    parser.add_argument('--approved_sender', action='append', help='Approved sender(s)')
    parser.add_argument('--url_logfile', default='extracted_urls.txt', help='File to log URLs')
    parser.add_argument('--db_path', default=DB_PATH, help='SQLite DB path')
    parser.add_argument('--retries', type=int, default=3, help='Download retries')
    parser.add_argument('--enable_debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Env fallback
    if not args.gmail_email:
        args.gmail_email = os.environ.get('GMAIL_EMAIL')

    # Restore GMAIL_DESIRED_SENDERS logic:
    env_senders = os.environ.get('GMAIL_DESIRED_SENDERS')
    if not args.approved_sender and env_senders:
        # Accept both comma and semicolon as delimiters
        args.approved_sender = [s.strip().lower() for s in re.split(r'[;,]', env_senders) if s.strip()]
    elif not args.approved_sender:
        # Fallback if nothing set anywhere
        args.approved_sender = []
    else:
        # Already present via CLI, normalize
        args.approved_sender = [s.lower() for s in args.approved_sender]

    if not args.gmail_email:
        logging.error("[x] Must provide Gmail email via CLI or env vars.")
        print("[x] Must provide Gmail email via CLI or env vars.")
        sys.exit(1)
    return args


def configure_logging(enable_debug=False):
    level = logging.DEBUG if enable_debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def fetch_last_msgs(approved_senders):
    """Fetch messages using gmailtail and return them as a list of dicts."""
    credentials = os.environ.get('GMAILTAIL_CREDENTIALS')
    token = os.environ.get('GMAILTAIL_TOKEN')
    if not credentials:
        logging.error('[x] GMAILTAIL_CREDENTIALS environment variable is required')
        print('[x] GMAILTAIL_CREDENTIALS environment variable is required')
        return []

    config = Config()
    config.auth.credentials = credentials
    if token:
        config.auth.cached_auth_token = token

    if approved_senders:
        query = ' OR '.join(f'from:{s}' for s in approved_senders)
        config.filters.query = query

    config.output.format = 'json-lines'
    config.output.include_body = True
    config.monitoring.once = True

    class Collector(OutputFormatter):
        def __init__(self, cfg):
            super().__init__(cfg)
            self.messages = []

        def output_message(self, message):
            self.messages.append(message)

    collector = Collector(config)
    tail = GmailTail(config)
    tail.formatter = collector
    tail.run()
    return collector.messages


def main():
    args = parse_arguments()
    configure_logging(args.enable_debug)
    initialize_database(args.db_path)

    start = time.time()
    messages = fetch_last_msgs(args.approved_sender)
    if not messages:
        logging.info("[i] No messages to process. Exiting.")
        print("[i] No messages to process. Exiting.")
        sys.exit(0)

    process_messages(
        messages,
        args.approved_sender,
        args.url_logfile,
        args.db_path,
        args.retries,
    )


    elapsed = time.time() - start
    mins, secs = divmod(int(elapsed), 60)
    logging.info(f"[i] Completed in {mins}m{secs}s")
    print(f"[i] Completed in {mins}m{secs}s")


if __name__ == '__main__':
    main()

