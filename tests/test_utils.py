import os
import tempfile
import sqlite3
import hashlib

from utils import safe_filename, initialize_database, is_url_downloaded, record_successful_download
from deduplicate_by_md5 import md5_for_file


def test_safe_filename_basic():
    orig = 'Hello<>:"/\\|?* World'
    result = safe_filename(orig)
    assert '<' not in result and '>' not in result
    assert ':' not in result and '"' not in result
    assert '/' not in result and '\\' not in result
    assert '|' not in result and '?' not in result
    assert '*' not in result
    assert result.startswith('Hello')


def test_safe_filename_empty():
    assert safe_filename('  ') == 'untitled'


def test_md5_for_file(tmp_path):
    file_path = tmp_path / 'sample.txt'
    content = b'hello world\n'
    file_path.write_bytes(content)
    expected = hashlib.md5(content).hexdigest()
    assert md5_for_file(file_path) == expected


def test_db_insertion_routines(tmp_path):
    db_path = os.path.join(tmp_path, 'test.db')
    initialize_database(db_path)
    url = 'http://example.com/video'
    title = 'Example Video'
    assert not is_url_downloaded(url, db_path)
    record_successful_download(url, title, db_path)
    assert is_url_downloaded(url, db_path)
    # Duplicate insert should not create new rows
    record_successful_download(url, 'New Title', db_path)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM downloads')
        count = cursor.fetchone()[0]
    finally:
        conn.close()
    assert count == 1
