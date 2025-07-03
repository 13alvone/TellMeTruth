#!/usr/bin/env python3

import argparse
import requests
import time
import random
import logging
import sqlite3
import os
import re
from pathlib import Path
from urllib.parse import urlencode

DB_PATH = "downloads.db"

# Configure top-level logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

###############################################################################
#                              DB FUNCTIONS                                   #
###############################################################################
def initialize_database(db_path: str = DB_PATH):
    """Initialize the SQLite database to store successfully downloaded URLs."""
    logging.debug("[DEBUG] Initializing SQLite database.")
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
    logging.debug("[DEBUG] SQLite database initialized.")


def is_url_downloaded(url: str, db_path: str = DB_PATH) -> bool:
    """
    Check if a URL has already been downloaded (URL is unique).
    """
    logging.debug(f"[DEBUG] Checking if URL is already downloaded: {url}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM downloads WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def record_successful_download(url: str, title: str, db_path: str = DB_PATH):
    """
    Record a successfully downloaded URL in the database.
    """
    logging.debug(f"[DEBUG] Recording successful download: URL={url}, Title={title}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO downloads (url, title) VALUES (?, ?)", (url, title))
    conn.commit()
    conn.close()

###############################################################################
#                           FILENAME UTILITIES                                #
###############################################################################
def safe_filename(input_str: str, max_length: int = 150) -> str:
    """
    Convert `input_str` into a filesystem-safe string:
    - Trim to max_length characters
    - Remove or replace characters invalid on most filesystems
    - Return the sanitized string (does not include extension)
    """
    # Basic sanitation to remove path separators and forbidden chars
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', input_str.strip())
    # Also remove leading/trailing dots or spaces
    sanitized = sanitized.strip('. ').strip()
    # Enforce length limit
    sanitized = sanitized[:max_length]
    # If string is empty or only invalid chars, use a fallback
    if not sanitized:
        sanitized = "untitled"
    return sanitized


def get_unique_filepath(directory: str, base_name: str, extension: str = ".mp4") -> str:
    """
    If `base_name.mp4` exists, append incremental suffix (_1, _2, etc.) until a unique name is found.
    Returns the final absolute path to the file.
    """
    os.makedirs(directory, exist_ok=True)
    candidate = os.path.join(directory, base_name + extension)
    if not os.path.exists(candidate):
        return candidate

    # If it exists, increment suffix
    counter = 1
    while True:
        candidate = os.path.join(directory, f"{base_name}_{counter}{extension}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1

###############################################################################
#                               CORE DOWNLOAD                                 #
###############################################################################
def download_instagram_video(
    url: str,
    output_dir: str,
    fallback_title: str,
    retries: int = 3,
    db_path: str = DB_PATH
) -> bool:
    """
    Reusable function to download a single Instagram video using the REST API endpoint.

    Steps:
    1. Check if URL is already downloaded (skip if yes).
    2. Hit the API to get videoUrl + description.
    3. Use the first 150 chars of description as the base filename, sanitized.
       If no description, fallback to fallback_title.
    4. Ensure we never overwrite existing files by auto-incrementing suffixes if needed.
    5. Record success in the DB upon successful download.

    Args:
        url (str): The Instagram post URL.
        output_dir (str): Directory to store the downloaded MP4 file.
        fallback_title (str): A fallback name if description is missing or empty.
        retries (int): Number of attempts on failure.
        db_path (str): Path to the SQLite DB.

    Returns:
        bool: True if download succeeded (or already downloaded), False otherwise.
    """
    # 1) Check DB for existing record
    if is_url_downloaded(url, db_path=db_path):
        logging.info(f"[i] URL already downloaded: {url}. Skipping.")
        return True

    api_endpoint = "http://instagram.speakes/api/video"
    query_params = {"postUrl": url}
    full_url = f"{api_endpoint}?{urlencode(query_params)}"

    logging.info(f"[i] Initiating REST API request for: {url}")
    logging.debug(f"[DEBUG] Full API URL: {full_url}")

    for attempt in range(1, retries + 1):
        try:
            logging.info(f"[i] Attempt {attempt}/{retries} for {url}")
            response = requests.get(full_url)
            response.raise_for_status()

            data_json = response.json()
            logging.debug(f"[DEBUG] API response: {data_json}")

            # 2) Validate success + retrieve videoUrl
            if data_json.get("status") == "success" and "videoUrl" in data_json.get("data", {}):
                video_url = data_json["data"]["videoUrl"]
                logging.info(f"[i] Video URL retrieved: {video_url}")

                # 3) Retrieve up to 150 chars from description if present
                #    If no "description" in data, fallback to fallback_title
                desc = data_json["data"].get("description", "").strip()
                if desc:
                    base_name = safe_filename(desc, 150)
                else:
                    base_name = safe_filename(fallback_title, 150)

                # 4) Download video content
                video_resp = requests.get(video_url)
                video_resp.raise_for_status()

                # 5) Create unique file path
                final_path = get_unique_filepath(output_dir, base_name, ".mp4")
                with open(final_path, "wb") as f:
                    f.write(video_resp.content)
                logging.info(f"[i] Video saved as {final_path}")

                # 6) Record success in DB
                record_successful_download(url, base_name, db_path=db_path)
                return True
            else:
                logging.warning(f"[!] Unexpected response structure or 'videoUrl' missing: {data_json}")

        except requests.RequestException as exc:
            logging.error(f"[x] Error during download attempt {attempt} for {url}: {exc}")
            if 'response' in locals():
                logging.debug(f"[DEBUG] Response content: {response.content}")

        if attempt < retries:
            backoff = random.uniform(1, 3)
            logging.info(f"[i] Retrying in {backoff:.2f} seconds...")
            time.sleep(backoff)

    logging.error(f"[x] All {retries} attempts failed for {url}. Giving up.")
    return False


###############################################################################
#                             CLI MAIN FUNCTION                               #
###############################################################################
def main():
    """
    Original CLI logic: allows usage like:
      python3 instagram_downloader.py <URL|comma-URLs|file> [-r N]
    """
    initialize_database(DB_PATH)
    parser = argparse.ArgumentParser(
        description="CLI script to download videos from Instagram using a REST API."
    )
    parser.add_argument(
        "input",
        help="A single URL, comma-separated URLs, or a file path to a text file containing URLs and titles."
    )
    parser.add_argument(
        "-r", "--retries",
        type=int,
        default=3,
        help="Number of retries for each URL in case of failure. Default is 3."
    )
    args = parser.parse_args()

    input_arg = args.input
    urls_with_titles = []

    # Decide how to parse the input
    if "," in input_arg:
        # Comma-delimited => each URL gets a generic 'DefaultTitle'
        for u in input_arg.split(","):
            u = u.strip()
            if u:
                urls_with_titles.append((u, "DefaultTitle"))
    else:
        # Check if it's a file
        p = Path(input_arg)
        if p.is_file():
            with open(p, "r") as f:
                for line in f:
                    line = line.strip()
                    if "," in line:
                        url, title = line.split(",", 1)
                        urls_with_titles.append((url.strip(), title.strip()))
        else:
            # Single URL
            urls_with_titles.append((input_arg.strip(), "DefaultTitle"))

    if not urls_with_titles:
        logging.error("[x] No valid URLs provided.")
        return

    logging.info(f"[i] Starting download process for {len(urls_with_titles)} URL(s).")
    for url, fallback_title in urls_with_titles:
        success = download_instagram_video(
            url=url,
            output_dir=".",   # By default CLI saves in current directory
            fallback_title=fallback_title,
            retries=args.retries,
            db_path=DB_PATH
        )
        if not success:
            logging.error(f"[x] Download failed for {url}.")
        else:
            # random backoff
            backoff = random.uniform(1, 3)
            logging.info(f"[i] Waiting {backoff:.2f} seconds before the next request...")
            time.sleep(backoff)

    logging.info("[i] Download process completed.")


if __name__ == "__main__":
    main()
