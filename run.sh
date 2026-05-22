#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Load .env ──────────────────────────────────────────────────────────────
if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# ── Guards ─────────────────────────────────────────────────────────────────
check_ffmpeg() {
  if ! command -v ffmpeg &>/dev/null; then
    echo "ERROR: ffmpeg not found. Install it first:"
    echo "  macOS:  brew install ffmpeg"
    echo "  Linux:  sudo apt install ffmpeg"
    exit 1
  fi
}

check_env() {
  if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "WARNING: ANTHROPIC_API_KEY is not set"
    echo "  → Copy .env.example to .env and add your key."
    echo ""
  fi
}

# ── Commands ───────────────────────────────────────────────────────────────
CMD="${1:-help}"

case "$CMD" in
  pipeline)
    check_ffmpeg
    check_env
    echo "Running pipeline (single pass)..."
    python3 watcher.py
    ;;

  watch)
    check_ffmpeg
    check_env
    echo "Starting watcher (continuous mode)..."
    python3 watcher.py --watch
    ;;

  cron-install)
    CRON_CMD="0 2 * * * cd $SCRIPT_DIR && ./run.sh pipeline >> logs/cron.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "content-pipeline"; echo "$CRON_CMD") | crontab -
    echo "✓ Cron job installed: pipeline runs nightly at 2am"
    echo "  Entry: $CRON_CMD"
    echo "  View with: crontab -l"
    echo "  Remove with: ./run.sh cron-remove"
    ;;

  cron-remove)
    crontab -l 2>/dev/null | grep -v "content-pipeline" | crontab -
    echo "✓ Cron job removed."
    ;;

  help|*)
    cat <<'EOF'
Content Pipeline — run.sh

Usage:
  ./run.sh pipeline       Process all pending jobs in input/ (single pass)
  ./run.sh watch          Continuous mode — scans input/ every 30s
  ./run.sh cron-install   Install nightly 2am cron job
  ./run.sh cron-remove    Remove the cron job

Workflow:
  1. Drop a job folder into input/
       input/my-post/clip1.mp4
       input/my-post/clip2.mp4
       input/my-post/template.json   ← optional hints for Claude

  2. ./run.sh pipeline

  3. Find your output in export/my-post/
       my-post_final.mp4    ← upload this
       my-post_caption.txt  ← copy-paste into each platform
EOF
    ;;
esac
