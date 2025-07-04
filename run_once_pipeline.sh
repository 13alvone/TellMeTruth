#!/usr/bin/env bash
# run_once_pipeline.sh
# Run the email/video downloader and transcriber exactly once.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
LOG_FILE="$SCRIPT_DIR/tell_me_truth.log"
LOCK_FILE="$SCRIPT_DIR/tell_me_truth.lock"
COOKIES_FILE="$SCRIPT_DIR/cookies.txt"

# Activate virtual environment
if [[ -f "$VENV_DIR/bin/activate" ]]; then
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
else
    echo "[x] Virtual environment not found at $VENV_DIR" | tee -a "$LOG_FILE"
    exit 1
fi

# Ensure cookies file exists
if [[ ! -f "$COOKIES_FILE" ]]; then
    echo "[x] Cookies file not found: $COOKIES_FILE" | tee -a "$LOG_FILE"
    exit 1
fi
export YTDLP_COOKIES_FILE="$COOKIES_FILE"

# Obtain lock to prevent concurrent runs
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "[!] Another instance is already running. Exiting." | tee -a "$LOG_FILE"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ==== Running single pipeline cycle ==== " | tee -a "$LOG_FILE"

if python3 "$SCRIPT_DIR/email_video_runner.py" >> "$LOG_FILE" 2>&1; then
    echo "[i] Video download stage completed successfully." | tee -a "$LOG_FILE"
else
    echo "[x] Video download stage failed." | tee -a "$LOG_FILE"
fi

if python3 "$SCRIPT_DIR/transcribe_downloaded_videos.py" >> "$LOG_FILE" 2>&1; then
    echo "[i] Transcription stage completed successfully." | tee -a "$LOG_FILE"
else
    echo "[x] Transcription stage failed." | tee -a "$LOG_FILE"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ==== Single cycle complete ==== " | tee -a "$LOG_FILE"
