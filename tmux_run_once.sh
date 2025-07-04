#!/usr/bin/env bash
# tmux_run_once.sh
# Launch run_once_pipeline.sh inside a tmux session for remote use.

set -euo pipefail

SESSION_NAME="${1:-tell_me_truth_once}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v tmux >/dev/null 2>&1; then
    echo "[x] tmux is not installed. Please install it first." >&2
    exit 1
fi

# Start new detached session running the pipeline once
TMUX_CMD="bash \"$SCRIPT_DIR/run_once_pipeline.sh\""

# shellcheck disable=SC2086
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "[i] Session $SESSION_NAME already exists. Attaching..."
    tmux attach -t "$SESSION_NAME"
else
    tmux new-session -d -s "$SESSION_NAME" "$TMUX_CMD"
    echo "[i] Started tmux session '$SESSION_NAME'. Attach with: tmux attach -t $SESSION_NAME"
fi
