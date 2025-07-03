#!/usr/bin/env python3

import os
import sys
import subprocess
import logging
from pathlib import Path
import shutil

def check_prerequisites():
    # Check for ffmpeg in PATH
    if not shutil.which("ffmpeg"):
        print("\n[!] ffmpeg is required but was not found in your PATH.")
        print("    Install with:")
        print("      sudo apt-get install ffmpeg    # On Ubuntu/Debian")
        print("      brew install ffmpeg            # On Mac (Homebrew)")
        sys.exit(1)

    # Check for whisper and torch packages
    missing = []
    try:
        import whisper
    except ImportError:
        missing.append("openai-whisper")
    try:
        import torch
    except ImportError:
        missing.append("torch")

    if missing:
        print(f"\n[!] Missing required Python package(s): {', '.join(missing)}")
        print("    Install all dependencies with:")
        print("      pip3 install --user -r requirements.txt")
        sys.exit(1)

def extract_audio(video_path, audio_path):
    """Extract audio from video as wav using ffmpeg."""
    if audio_path.exists():
        logging.info(f"Audio already exists: {audio_path}")
        return True
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-ar", "16000",        # Whisper expects 16kHz mono
        "-ac", "1",
        "-vn",                 # No video
        "-y",                  # Overwrite if needed
        str(audio_path)
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"Extracted audio: {audio_path}")
        return True
    except subprocess.CalledProcessError:
        logging.error(f"Failed to extract audio from {video_path}")
        return False

def transcribe_audio(audio_path, transcript_path, model_size="base"):
    import whisper
    if transcript_path.exists():
        logging.info(f"Transcript already exists: {transcript_path}")
        return True
    model = whisper.load_model(model_size)
    logging.info(f"Transcribing {audio_path}...")
    result = model.transcribe(str(audio_path))
    text = result['text'].strip()
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(text)
    logging.info(f"Wrote transcript: {transcript_path}")
    return True

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

def main(downloads_dir="downloads", model_size="base"):
    check_prerequisites()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    factcheck_dirs = load_factcheck_dirs()
    if not factcheck_dirs:
        logging.info("[i] No factcheck directories to process. Exiting.")
        return

    # Only look for videos in the listed factcheck directories
    video_files = []
    for d in factcheck_dirs:
        d_path = Path(d)
        if d_path.exists() and d_path.is_dir():
            found = list(d_path.glob("*.mp4"))
            logging.info(f"Found {len(found)} video(s) in {d}")
            video_files.extend(found)
        else:
            logging.warning(f"[!] Directory not found or not a directory: {d}")

    logging.info(f"Total factcheck videos to process: {len(video_files)}")
    for video in video_files:
        audio = video.with_suffix(".wav")
        transcript = video.with_suffix(".txt")
        if not extract_audio(video, audio):
            continue
        transcribe_audio(audio, transcript, model_size=model_size)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Transcribe factcheck videos using Whisper.")
    parser.add_argument("--downloads_dir", default="downloads", help="(ignored) Directory to search for videos.")
    parser.add_argument("--model_size", default="base", help="Whisper model size: tiny, base, small, medium, large")
    args = parser.parse_args()
    main(args.downloads_dir, args.model_size)

