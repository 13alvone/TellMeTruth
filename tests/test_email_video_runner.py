import types
import sys

# Provide stub modules so email_video_runner can be imported without the real
# gmailtail dependency installed.
gmailtail = types.ModuleType("gmailtail")
gmailtail_config = types.ModuleType("gmailtail.config")
gmailtail_gmailtail = types.ModuleType("gmailtail.gmailtail")


class DummyConfig:
    def __init__(self):
        self.auth = types.SimpleNamespace(credentials=None, cached_auth_token=None)
        self.filters = types.SimpleNamespace(query=None)
        self.output = types.SimpleNamespace(format=None, include_body=None)
        self.monitoring = types.SimpleNamespace(once=None)


gmailtail_config.Config = DummyConfig


class PlaceholderTail:
    pass


class PlaceholderFormatter:
    pass


gmailtail_gmailtail.GmailTail = PlaceholderTail
gmailtail_gmailtail.OutputFormatter = PlaceholderFormatter
gmailtail.gmailtail = gmailtail_gmailtail
yt_dlp = types.ModuleType("yt_dlp")


class DummyYDL:
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def extract_info(self, url, download=True):
        return {"title": "dummy"}


yt_dlp.YoutubeDL = DummyYDL
sys.modules["gmailtail"] = gmailtail
sys.modules["gmailtail.config"] = gmailtail_config
sys.modules["gmailtail.gmailtail"] = gmailtail_gmailtail
sys.modules["yt_dlp"] = yt_dlp

import email_video_runner as evr
from utils import initialize_database, is_url_downloaded


def test_fetch_and_process_records_urls(monkeypatch, tmp_path):
    sample_messages = [
        {
            "from": {"email": "sender@example.com"},
            "subject": "Video Links",
            "body": "Check https://youtu.be/test1 and https://example.com/video2",
        }
    ]

    class DummyOutputFormatter:
        def __init__(self, cfg):
            pass

    class DummyGmailTail:
        def __init__(self, config):
            self.formatter = None

        def run(self):
            for msg in sample_messages:
                self.formatter.output_message(msg)

    def dummy_download(url, output_dir, fallback_title, retries, db_path):
        # record directly without touching yt_dlp
        evr.record_successful_download(url, fallback_title, db_path)
        return True

    monkeypatch.setenv("GMAILTAIL_CREDENTIALS", "cred.json")
    monkeypatch.setenv("GMAILTAIL_TOKEN", "token.json")
    monkeypatch.setattr(evr, "OutputFormatter", DummyOutputFormatter)
    monkeypatch.setattr(evr, "GmailTail", DummyGmailTail)
    monkeypatch.setattr(evr, "download_with_ytdlp", dummy_download)

    db_path = tmp_path / "test.db"
    url_log = tmp_path / "urls.txt"
    initialize_database(db_path)

    messages = evr.fetch_last_msgs([])
    assert messages == sample_messages

    evr.process_messages(messages, [], url_log, db_path, retries=1)

    assert is_url_downloaded("https://youtu.be/test1", db_path)
    assert is_url_downloaded("https://example.com/video2", db_path)

    with open(url_log, "r", encoding="utf-8") as f:
        logged = [line.strip() for line in f if line.strip()]
    assert "https://youtu.be/test1" in logged
    assert "https://example.com/video2" in logged
