#!/usr/bin/env python3

import argparse
import os
import random
import time
import logging
import sqlite3
import re

DB_PATH = "downloads.db"

def safe_filename(input_str: str, max_length: int = 150) -> str:
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', input_str.strip())
    sanitized = sanitized.strip('. ').strip()
    sanitized = sanitized[:max_length]
    if not sanitized:
        sanitized = "untitled"
    return sanitized

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
    cursor.execute("INSERT OR IGNORE INTO downloads (url, title) VALUES (?, ?)", (url, title))
    conn.commit()
    conn.close()

def download_video_yt_tiktok(
    url: str,
    platform: str,
    output_dir: str,
    fallback_title: str,
    retries: int = 3,
    db_path: str = DB_PATH
) -> bool:
    if is_url_downloaded(url, db_path=db_path):
        logging.info(f"[i] URL already downloaded: {url}. Skipping.")
        return True
    try:
        import yt_dlp
    except ImportError:
        logging.error("[x] yt-dlp is not installed. Run `pip install yt-dlp`.")
        return False

    for attempt in range(1, retries + 1):
        try:
            ydl_opts = {
                'outtmpl': os.path.join(output_dir, '%(title).150s.%(ext)s'),
                'quiet': True,
                'noplaylist': True,
            }
            os.makedirs(output_dir, exist_ok=True)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title') or fallback_title
                safe_title = safe_filename(title, 150)
                record_successful_download(url, safe_title, db_path=db_path)
                return True
        except Exception as exc:
            logging.error(f"[x] yt-dlp error on attempt {attempt} for {url}: {exc}")
        if attempt < retries:
            backoff = random.uniform(1, 3)
            logging.info(f"[i] Retrying in {backoff:.2f} seconds...")
            time.sleep(backoff)
    logging.error(f"[x] All {retries} attempts failed for {url}. Giving up.")
    return False

def main():
    parser = argparse.ArgumentParser(
        description="Standalone YouTube/TikTok video downloader."
    )
    parser.add_argument(
        "url",
        help="A YouTube or TikTok video URL."
    )
    parser.add_argument(
        "--platform",
        choices=["youtube", "tiktok"],
        required=True,
        help="Platform: youtube or tiktok."
    )
    parser.add_argument(
        "--output_dir",
        default="downloads",
        help="Directory to save the downloaded file."
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retries on failure."
    )
    parser.add_argument(
        "--db_path",
        default=DB_PATH,
        help="Path to the downloads DB."
    )
    parser.add_argument(
        "--fallback_title",
        default="DownloadedVideo",
        help="Fallback title if not found."
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    initialize_database(args.db_path)
    output_dir = os.path.join(args.output_dir, args.platform)
    success = download_video_yt_tiktok(
        url=args.url,
        platform=args.platform,
        output_dir=output_dir,
        fallback_title=args.fallback_title,
        retries=args.retries,
        db_path=args.db_path
    )
    if not success:
        logging.error(f"[x] Download failed for {args.url}.")
    else:
        logging.info(f"[i] Successfully downloaded {args.url} into {output_dir}.")

if __name__ == "__main__":
    main()

