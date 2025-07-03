#!/usr/bin/env python3

import os
import sys
import json
import shutil
import subprocess
import logging
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

PROMPT = (
    "The following is a direct transcription of a video. Your job is to analyze every factual claim, assumption, or "
    "statement of consequence and evaluate it with complete honesty and ferocity. Truth is the foundation of all "
    "society, and the decay of truth is the death of civilization. You must ignore all social, political, or emotional "
    "consequences and respond with the integrity of a scientist and philosopher who knows that a society built on lies "
    "is destined to collapse. Analyze every statement. Mark clearly what is true, what is questionable, what is false, "
    "and what requires more context or evidence. If the truth is painful, record it anyway. Do not soften or sugarcoat "
    "the analysis for anyone. Your answer must reflect the importance of truth above all else."
)
DEFAULT_MODEL = "base"  # whisper model

def check_prerequisites():
    if not shutil.which("ffmpeg"):
        print("\n[!] ffmpeg is required but not found in your PATH.")
        print("    Install with:")
        print("      sudo apt-get install ffmpeg    # On Ubuntu/Debian")
        print("      brew install ffmpeg            # On Mac (Homebrew)")
        sys.exit(1)
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

def is_file_stable(file_path: Path, stable_seconds=10):
    try:
        initial_stat = file_path.stat()
        initial_size = initial_stat.st_size
        initial_mtime = initial_stat.st_mtime
        time.sleep(stable_seconds)
        current_stat = file_path.stat()
        return (current_stat.st_size == initial_size) and (current_stat.st_mtime == initial_mtime)
    except Exception as e:
        logging.warning(f"Could not stat file {file_path}: {e}")
        return False

def extract_audio(video_path: Path, audio_path: Path, log_prefix=""):
    if audio_path.exists():
        logging.info(f"{log_prefix}Audio already exists: {audio_path}")
        return True
    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-ar", "16000",
        "-ac", "1",
        "-vn",
        "-y",
        str(audio_path)
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info(f"{log_prefix}Extracted audio: {audio_path}")
        return True
    except subprocess.CalledProcessError:
        logging.error(f"{log_prefix}Failed to extract audio from {video_path}")
        return False

def transcribe_audio(audio_path: Path, transcript_path: Path, model_size=DEFAULT_MODEL, log_prefix=""):
    import whisper
    if transcript_path.exists():
        logging.info(f"{log_prefix}Transcript already exists: {transcript_path}")
        return True
    model = whisper.load_model(model_size)
    logging.info(f"{log_prefix}Transcribing {audio_path} with Whisper model '{model_size}'...")
    result = model.transcribe(str(audio_path))
    text = result['text'].strip()
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(text)
    logging.info(f"{log_prefix}Wrote transcript: {transcript_path}")
    return True

def get_platform_from_path(path: Path):
    for p in path.parts:
        if p in ("youtube", "tiktok", "instagram"):
            return p
    return "unknown"

def package_json(video_path: Path, audio_path: Path, transcript_path: Path, json_path: Path, downloads_dir: Path, model_name, log_prefix=""):
    def rel(p):
        try:
            return str(p.relative_to(downloads_dir))
        except ValueError:
            return str(p.name)
    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript = f.read().strip()
    metadata = {
        "video_file": rel(video_path),
        "audio_file": rel(audio_path) if audio_path.exists() else "",
        "transcript_file": rel(transcript_path),
        "json_file": rel(json_path),
        "platform": get_platform_from_path(video_path),
        "created_utc": datetime.utcnow().isoformat() + "Z",
        "model": model_name
    }
    obj = {
        "prompt": PROMPT,
        "transcript": transcript,
        "metadata": metadata
    }
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(obj, jf, indent=2, ensure_ascii=False)
    logging.info(f"{log_prefix}Wrote {json_path}")

def process_single_video(video: Path, base_dir: Path, model_size=DEFAULT_MODEL, stable_seconds=10):
    log_prefix = f"[{video.name}] "
    try:
        if str(video).endswith(".part"):
            logging.info(f"{log_prefix}Skipping temporary/partial file.")
            return
        if not is_file_stable(video, stable_seconds=stable_seconds):
            logging.info(f"{log_prefix}Not stable (still being written or modified), skipping.")
            return
        audio = video.with_suffix(".wav")
        transcript = video.with_suffix(".txt")
        jsonf = video.with_suffix(".json")
        if jsonf.exists():
            logging.info(f"{log_prefix}Already fully processed, skipping.")
            return
        if not extract_audio(video, audio, log_prefix):
            return
        if not transcribe_audio(audio, transcript, model_size, log_prefix):
            return
        package_json(video, audio, transcript, jsonf, base_dir, f"whisper-{model_size}", log_prefix)
    except Exception as e:
        logging.error(f"{log_prefix}Unexpected error: {e}")

def process_videos(downloads_dir: str, model_size=DEFAULT_MODEL, stable_seconds=10, max_workers=2):
    check_prerequisites()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    base_dir = Path(downloads_dir)
    video_files = list(base_dir.rglob("*.mp4"))
    logging.info(f"Found {len(video_files)} video(s) to process. Using up to {max_workers} worker(s).")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_single_video, video, base_dir, model_size, stable_seconds)
            for video in video_files
        ]
        # Optionally, you can iterate as futures complete to print summaries or errors:
        for future in as_completed(futures):
            _ = future.result()  # exceptions will be logged by the worker itself

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Parallel pipeline: audio extraction, transcription, JSON packaging for LLM truth analysis (race-condition safe).")
    parser.add_argument("--downloads_dir", default="downloads", help="Directory containing videos (default: downloads)")
    parser.add_argument("--model_size", default=DEFAULT_MODEL, help="Whisper model size: tiny, base, small, medium, large")
    parser.add_argument("--stable_seconds", type=int, default=10, help="Seconds a file must be unchanged before considered stable (default: 10)")
    parser.add_argument("--max_workers", type=int, default=2, help="How many videos to process in parallel (default: 2)")
    args = parser.parse_args()
    process_videos(args.downloads_dir, args.model_size, args.stable_seconds, args.max_workers)

