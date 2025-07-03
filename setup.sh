#!/bin/bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "[x] This script must be run with sudo (as root)." 1>&2
    exit 1
fi

# Optional: Check for Docker & Docker Compose
if ! command -v docker >/dev/null 2>&1; then
    echo "[!] Docker is not installed or not in your PATH."
    exit 1
fi

if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
    echo "[!] Docker Compose is not installed or not in your PATH."
    exit 1
fi

echo "[i] Building the custom docker engine"
docker compose build --no-cache

echo ""
docker compose run --entrypoint /bin/bash tell_me_truth

echo "[*] Setup complete. You should be ready to go!"

