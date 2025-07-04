import re
import sqlite3
import logging

DB_PATH = "downloads.db"


def initialize_database(db_path: str = DB_PATH):
    """Create the downloads table if it does not exist."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def is_url_downloaded(url: str, db_path: str = DB_PATH) -> bool:
    """Return True if the URL already exists in the DB."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM downloads WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def record_successful_download(url: str, title: str, db_path: str = DB_PATH):
    """Insert a successfully downloaded URL and title into the DB."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO downloads (url, title) VALUES (?, ?)",
            (url, title),
        )
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"[x] DB record error for {url}: {e}")
    finally:
        conn.close()


def safe_filename(input_str: str, max_length: int = 150) -> str:
    """Return a filesystem-safe representation of ``input_str``."""
    sanitized = re.sub(r"[\\/*?:\"<>|]", "_", input_str.strip())
    sanitized = sanitized.strip(". ").strip()[:max_length]
    return sanitized or "untitled"
