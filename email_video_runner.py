#!/usr/bin/env python3
"""
email_video_runner.py

Connects to Gmail via IMAP, fetches messages, extracts URLs, and downloads videos using yt-dlp
with retry, cookie support, and IMAP reconnection.
"""
import argparse
import imaplib
import email
import sys
import logging
import time
import os
import re
import sqlite3
import random
from email.utils import parseaddr

import yt_dlp

# ---------------------- Constants ----------------------
DB_PATH = "downloads.db"
MAX_IMAP_RETRIES = int(os.environ.get("MAX_IMAP_RETRIES", "3"))
IMAP_RETRY_DELAY = float(os.environ.get("IMAP_RETRY_DELAY", "1.0"))
YTDLP_COOKIES_FILE = os.environ.get("YTDLP_COOKIES_FILE")
FACTCHECK_KEYWORD = "factcheck"
FACTCHECK_RESPONSE_PREFIX = "[FACTCHECK - RESPONSE] - "  # New for loop prevention

# ---------------------- DB Functions ----------------------
def initialize_database(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def is_url_downloaded(url: str, db_path: str = DB_PATH) -> bool:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM downloads WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def record_successful_download(url: str, title: str, db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO downloads (url, title) VALUES (?, ?)", (url, title))
        conn.commit()
        logging.info(f"[i] Recorded download: {url} with title '{title}'")
    except sqlite3.Error as e:
        logging.error(f"[x] DB record error for {url}: {e}")
    finally:
        conn.close()

# ---------------------- Filename Utility ----------------------
def safe_filename(input_str: str, max_length: int = 150) -> str:
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', input_str.strip())
    sanitized = sanitized.strip('. ').strip()[:max_length]
    return sanitized or "untitled"

# ---------------------- IMAP Reconnection ----------------------
def reconnect_imap(imap_srv, email_addr: str, passwd: str, mailbox: str):
    """Re-establish IMAP connection and select mailbox."""
    try:
        if imap_srv:
            imap_srv.logout()
    except Exception:
        pass
    srv = imaplib.IMAP4_SSL("imap.gmail.com")
    srv.login(email_addr, passwd)
    srv.select(mailbox)
    logging.info("[i] Reconnected to IMAP server and selected mailbox '%s'", mailbox)
    print(f"[i] Reconnected to IMAP server and selected mailbox '{mailbox}'")
    return srv

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
    imap_srv,
    msg_ids,
    approved_senders,
    url_logfile,
    db_path,
    retries,
    email_addr,
    passwd,
    mailbox
):
    factcheck_dirs = []

    for msg_id in msg_ids:
        msg_id_str = msg_id.decode('utf-8', errors='ignore')
        logging.info(f"[i] Processing msg ID: {msg_id_str}")
        print(f"[i] Processing msg ID: {msg_id_str}")
        # Fetch with retry on IMAP abort
        for attempt in range(1, MAX_IMAP_RETRIES + 1):
            try:
                rv, msg_data = imap_srv.fetch(msg_id, '(RFC822)')
                break
            except imaplib.IMAP4.abort as e:
                logging.warning(f"[!] IMAP abort on fetch {msg_id_str} (attempt {attempt}): {e}")
                print(f"[!] IMAP abort on fetch {msg_id_str} (attempt {attempt}): {e}")
                imap_srv = reconnect_imap(imap_srv, email_addr, passwd, mailbox)
                time.sleep(IMAP_RETRY_DELAY)
        else:
            logging.error(f"[x] Failed to fetch msg {msg_id_str} after {MAX_IMAP_RETRIES} retries—skipping")
            print(f"[x] Failed to fetch msg {msg_id_str} after {MAX_IMAP_RETRIES} retries—skipping")
            continue

        if rv != 'OK':
            logging.warning(f"[!] Could not fetch message {msg_id_str}")
            print(f"[!] Could not fetch message {msg_id_str}")
            continue

        for part in msg_data:
            if isinstance(part, tuple):
                message = email.message_from_bytes(part[1])
                sender = parseaddr(message.get('From', ''))[1].lower()
                if sender not in approved_senders:
                    msg = f"[i] Skipping email from {sender}; not approved."
                    logging.info(msg)
                    print(msg)
                    continue

                subject = message.get('Subject', 'NoSubject').strip()
                if subject.lower().startswith(FACTCHECK_RESPONSE_PREFIX.lower()):
                    msg = f"[i] Skipping response email with subject: {subject}"
                    logging.info(msg)
                    print(msg)
                    continue

                is_factcheck = FACTCHECK_KEYWORD.lower() in subject.lower()

                body_text = ''
                if message.is_multipart():
                    for p in message.walk():
                        if p.get_content_type() == 'text/plain':
                            payload = p.get_payload(decode=True)
                            if payload:
                                body_text += payload.decode('utf-8', errors='ignore') + '\n'
                else:
                    payload = message.get_payload(decode=True)
                    body_text = payload.decode('utf-8', errors='ignore') if payload else ''

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
    parser.add_argument('gmail_passwd', nargs='?', help='Gmail app password')
    parser.add_argument('--approved_sender', action='append', help='Approved sender(s)')
    parser.add_argument('--mailbox', default='INBOX', help='Mailbox to select')
    parser.add_argument('--url_logfile', default='extracted_urls.txt', help='File to log URLs')
    parser.add_argument('--db_path', default=DB_PATH, help='SQLite DB path')
    parser.add_argument('--retries', type=int, default=3, help='Download retries')
    parser.add_argument('--enable_debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()

    # Env fallback
    if not args.gmail_email:
        args.gmail_email = os.environ.get('GMAIL_EMAIL')
    if not args.gmail_passwd:
        # Gmail App password via env var GMAIL_PASSWD
        args.gmail_passwd = os.environ.get('GMAIL_PASSWD')

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

    if not args.gmail_email or not args.gmail_passwd:
        logging.error("[x] Must provide Gmail credentials via CLI or env vars.")
        print("[x] Must provide Gmail credentials via CLI or env vars.")
        sys.exit(1)
    return args


def configure_logging(enable_debug=False):
    level = logging.DEBUG if enable_debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def connect_to_gmail(email_addr, passwd, mailbox):
    try:
        logging.info("[i] Connecting to IMAP server...")
        print("[i] Connecting to IMAP server...")
        srv = imaplib.IMAP4_SSL('imap.gmail.com')
        ret, _ = srv.login(email_addr, passwd)
        if ret == 'OK':
            logging.info(f"[i] Logged in as {email_addr}")
            print(f"[i] Logged in as {email_addr}")
        else:
            logging.error(f"[x] IMAP login returned: {ret}")
            print(f"[x] IMAP login returned: {ret}")
            return None
        ret, _ = srv.select(mailbox)
        if ret != 'OK':
            logging.error(f"[x] Unable to open mailbox {mailbox}")
            print(f"[x] Unable to open mailbox {mailbox}")
            return None
        return srv
    except imaplib.IMAP4.error as e:
        logging.error(f"[x] IMAP error: {e}")
        print(f"[x] IMAP error: {e}")
        return None


def fetch_last_msgs(imap_srv):
    ret, data = imap_srv.search(None, 'ALL')
    if ret != 'OK':
        logging.error("[x] IMAP search failed.")
        print("[x] IMAP search failed.")
        return []
    ids = data[0].split()
    logging.info(f"[i] Found {len(ids)} messages in mailbox")
    print(f"[i] Found {len(ids)} messages in mailbox")
    return sorted(ids)


def main():
    args = parse_arguments()
    configure_logging(args.enable_debug)
    initialize_database(args.db_path)

    start = time.time()
    imap_srv = connect_to_gmail(args.gmail_email, args.gmail_passwd, args.mailbox)
    if not imap_srv:
        sys.exit(1)

    msg_ids = fetch_last_msgs(imap_srv)
    if not msg_ids:
        logging.info("[i] No messages to process. Exiting.")
        print("[i] No messages to process. Exiting.")
        imap_srv.logout()
        sys.exit(0)

    process_messages(
        imap_srv,
        msg_ids,
        args.approved_sender,
        args.url_logfile,
        args.db_path,
        args.retries,
        args.gmail_email,
        args.gmail_passwd,
        args.mailbox
    )

    try:
        imap_srv.close()
    except Exception as e:
        logging.debug(f"[DEBUG] imap close error: {e}")
        print(f"[DEBUG] imap close error: {e}")
    imap_srv.logout()

    elapsed = time.time() - start
    mins, secs = divmod(int(elapsed), 60)
    logging.info(f"[i] Completed in {mins}m{secs}s")
    print(f"[i] Completed in {mins}m{secs}s")


if __name__ == '__main__':
    main()

