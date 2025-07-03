# Fact Check Pipeline

A robust, end-to-end pipeline to fetch video links from email, download media, transcribe audio, and fact-check content using OpenAI’s ChatGPT API.

## Features

- Polls Gmail via IMAP for new messages containing video URLs.
- Deduplicates links using SQLite.
- Downloads media from YouTube, TikTok, Instagram, and more via `yt-dlp`.
- Supports private or age-restricted videos using a `cookies.txt` (exported from your Firefox session).
- Transcribes audio using OpenAI Whisper.
- Fact-checks transcripts using ChatGPT.
- Fully automated with a master script (`run_pipeline.sh`) or Docker for reliability.
- Minimal setup friction—just plug in your credentials, generate cookies, and go!

## Prerequisites

- Ubuntu Server 22+ (or macOS/Linux for development).
- Python 3.10+ (for local/manual mode).
- `ffmpeg` installed (needed by `yt-dlp` and Whisper).
- Gmail App Password for IMAP access.
- Docker & Docker Compose recommended for reproducible environment.
- Must be logged in to YouTube with Firefox for cookies export (see below).

---

## Quick Start: Dockerized Setup (Recommended)

	1. **Clone this repository:**
		git clone https://github.com/youruser/factcheck.git && cd factcheck

	2. **Log into YouTube in Firefox (with the account you want to use).**
		- Make sure you can play the restricted/private videos in your browser.

	3. **Generate a cookies.txt file:**
		pip3 install browser-cookie3
		python3 dump_firefox_cookies.py
		# This creates ./cookies.txt in your project folder

		[i] If you're running Docker on a different machine, copy cookies.txt to that machine's project directory.

	4. **Copy .env.example to .env and edit your settings:**
		cp .env.example .env
		vim .env    # or use nano, code, etc.

		# Required in .env:
		GMAIL_EMAIL=your@gmail.com
		GMAIL_PASSWD=your_app_password
		GMAIL_DESIRED_SENDERS=cspeakesinfo@gmail.com,thecspeakes@icloud.com
		YTDLP_COOKIES_FILE=/app/cookies.txt

	5. **Build and start the Docker service:**
		sudo docker-compose up -d --build

	6. **Check logs for activity:**
		sudo docker logs -f tell_me_truth

---

## Manual Installation (Non-Docker)

	1. Clone and cd to project directory.
	2. Create and activate a Python virtual environment:
		python3 -m venv venv
		source venv/bin/activate

	3. Install dependencies:
		pip install --no-cache-dir -r requirements.txt

	4. Generate cookies as described above and place them in ./cookies.txt.

	5. Export environment variables:
		export GMAIL_EMAIL=your@gmail.com
		export GMAIL_PASSWD=your_app_password
		export YTDLP_COOKIES_FILE=$(pwd)/cookies.txt

	6. Run the pipeline scripts:
		python3 email_video_runner.py
		python3 transcribe_downloaded_videos.py

---

## Configuration

- Place all variables in `.env` or export in your shell.
- You **must** have a valid `cookies.txt` in your project root for restricted video downloads.
- To change polling interval (in seconds), set `INTERVAL` in `.env`.

	Example .env:

		GMAIL_EMAIL=your@gmail.com
		GMAIL_PASSWD=your_app_password
		GMAIL_DESIRED_SENDERS=cspeakesinfo@gmail.com,thecspeakes@icloud.com
		YTDLP_COOKIES_FILE=/app/cookies.txt
		INTERVAL=3600
		MAX_IMAP_RETRIES=3
		IMAP_RETRY_DELAY=1.0

---

## Usage

### Manual Execution

	Run downloader:  
		python3 email_video_runner.py

	Run transcriber:  
		python3 transcribe_downloaded_videos.py

### Automated Pipeline

	Run everything on a loop (no cron needed):  
		./run_pipeline.sh

### Docker Deployment

	Build image and run container (requires sudo if not in docker group):  
		sudo docker-compose up -d --build

---

## Project Structure

	downloads/                          # Media and transcripts
	email_video_runner.py               # IMAP fetch + media downloader
	transcribe_downloaded_videos.py     # Whisper transcription
	run_pipeline.sh                     # Master pipeline script
	dump_firefox_cookies.py             # Generate cookies.txt from Firefox
	requirements.txt                    # Python dependencies
	Dockerfile                          # Container build instructions
	docker-compose.yml                  # Compose config
	.env.example                        # Example env file (copy to .env)
	extracted_urls.txt                  # Raw URL log
	downloads.db                        # SQLite tracking DB
	venv/                               # Python virtual environment

---

## Troubleshooting

- **IMAP errors:** Verify your `GMAIL_EMAIL` & `GMAIL_PASSWD` in `.env`, and that IMAP is enabled on your Gmail account.
- **Download failures:** Ensure `YTDLP_COOKIES_FILE` exists and is readable by the container or Python script.
- **Permission issues:** Check file ownership/permissions on `downloads.db`, `downloads/`, and `cookies.txt`.
- **Docker issues:** Confirm volumes, `.env`, and file paths are correct. Run with `sudo` if needed.
- **Private/restricted video errors:** Regenerate `cookies.txt` from a fresh Firefox login.

---

## License

MIT License

---

