#!/bin/bash

echo "[*] Cleaning environment..."

# Clear logs
> tell_me_truth.log

# Remove lock file if exists
rm -f tell_me_truth.lock

# Optionally clean up any leftover temp files or outputs as needed
# rm -rf output_folder/

# Remove lock file or directory if it exists
if [ -e tell_me_truth.lock ]; then
    rm -rf tell_me_truth.lock
fi
touch tell_me_truth.lock

if [ -e factcheck_dirs_for_transcription.txt ]; then
    rm -rf factcheck_dirs_for_transcription.txt
fi

echo "[i] Removing docker orphans, if any."
sudo docker compose down --remove-orphans

echo "[i] Rebuilding the docker custom image."
sudo docker compose build --no-cache

echo "[*] Environment reset complete."

