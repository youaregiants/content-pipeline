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
  local missing=0
  if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "WARNING: ANTHROPIC_API_KEY is not set"
    missing=1
  fi
  if [ -z "${AYRSHARE_API_KEY:-}" ]; then
    echo "WARNING: AYRSHARE_API_KEY is not set"
    missing=1
  fi
  if [ "$missing" -eq 1 ]; then
    echo "  → Copy .env.example to .env and fill in your keys."
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

  qa)
    echo "Starting QA server at http://localhost:8765 ..."
    python3 qa_server.py
    ;;

  schedule)
    check_env
    DRYRUN=""
    if [ "${2:-}" = "--dry-run" ]; then
      DRYRUN="--dry-run"
    fi
    echo "Running scheduler${DRYRUN:+ (dry-run)}..."
    python3 scheduler.py $DRYRUN
    ;;

  cron-install)
    CRON_CMD="0 2 * * * cd $SCRIPT_DIR && ./run.sh pipeline >> logs/cron.log 2>&1"
    (crontab -l 2>/dev/null | grep -v "content-pipeline"; echo "$CRON_CMD") | crontab -
    echo "✓ Cron job installed: pipeline runs nightly at 2am"
    echo "  Entry: $CRON_CMD"
    echo "  View with: crontab -l"
    echo "  Remove with: crontab -e"
    ;;

  cron-remove)
    crontab -l 2>/dev/null | grep -v "content-pipeline" | crontab -
    echo "✓ Cron job removed."
    ;;

  help|*)
    cat <<'EOF'
Content Pipeline — run.sh

Usage:
  ./run.sh pipeline          Run the pipeline once (process all pending jobs)
  ./run.sh watch             Continuous watch mode (scans every 30s)
  ./run.sh qa                Start the QA review server (http://localhost:8765)
  ./run.sh schedule          Schedule approved posts to Ayrshare
  ./run.sh schedule --dry-run Preview schedule without posting
  ./run.sh cron-install      Install nightly 2am cron job
  ./run.sh cron-remove       Remove the cron job

Workflow:
  1. Drop a job folder into input/  (must contain .mp4 or .mov clips)
  2. ./run.sh pipeline
  3. ./run.sh qa              → review and approve in browser
  4. ./run.sh schedule --dry-run  → check schedule_summary.json
  5. ./run.sh schedule            → post to TikTok / Instagram / YouTube
EOF
    ;;
esac
