"""
Orchestrator — scans input/ for job folders, dispatches each through the pipeline.
Usage:
  python watcher.py          # process all pending jobs once
  python watcher.py --watch  # continuous watch mode
"""

import argparse
import logging
import time
from pathlib import Path

import config
from pipeline import analyzer, renderer, meta_writer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.LOGS_DIR / "watcher.log"),
    ],
)
log = logging.getLogger(__name__)

DONE_MARKER = ".done"
ERROR_MARKER = ".error"
MAX_RETRIES = 2


def pending_jobs() -> list[Path]:
    jobs = []
    for d in sorted(config.INPUT_DIR.iterdir()):
        if not d.is_dir():
            continue
        if (d / DONE_MARKER).exists() or (d / ERROR_MARKER).exists():
            continue
        if not any(d.glob("*.mp4")) and not any(d.glob("*.mov")):
            continue
        jobs.append(d)
    return jobs


def process_job(job_dir: Path) -> bool:
    log.info(f"▶ Processing job: {job_dir.name}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log.info(f"  [attempt {attempt}] Analyzing clips...")
            manifest = analyzer.analyze(job_dir)

            job_name = job_dir.name
            out_path = config.OUTPUT_DIR / job_name / f"{job_name}.mp4"

            log.info(f"  [attempt {attempt}] Rendering...")
            video_path = renderer.render(job_dir, manifest, out_path)

            log.info(f"  [attempt {attempt}] Writing metadata...")
            meta_writer.write(job_dir, manifest, video_path)

            (job_dir / DONE_MARKER).write_text("done")
            log.info(f"✓ Job complete: {job_dir.name}")
            return True

        except Exception as e:
            log.warning(f"  [attempt {attempt}] Failed: {e}")
            if attempt == MAX_RETRIES:
                (job_dir / ERROR_MARKER).write_text(str(e))
                log.error(f"✗ Job failed after {MAX_RETRIES} attempts: {job_dir.name}")
                return False

    return False


def run_once():
    jobs = pending_jobs()
    if not jobs:
        log.info("No pending jobs found.")
        return
    log.info(f"Found {len(jobs)} pending job(s).")
    for job in jobs:
        process_job(job)


def run_watch():
    log.info(f"Watch mode: scanning every {config.WATCH_INTERVAL}s. Ctrl-C to stop.")
    while True:
        run_once()
        time.sleep(config.WATCH_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Content pipeline watcher")
    parser.add_argument("--watch", action="store_true", help="Continuous watch mode")
    args = parser.parse_args()

    if args.watch:
        run_watch()
    else:
        run_once()
