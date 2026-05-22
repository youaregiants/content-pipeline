"""
Batch-schedules approved posts to TikTok, Instagram, YouTube via Ayrshare.
Usage:
  python scheduler.py --dry-run   # preview schedule, write schedule_summary.json
  python scheduler.py             # actually post to Ayrshare
"""

import argparse
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import requests
import pytz

import config

TZ = pytz.timezone(config.TIMEZONE)


def _load_approved() -> list[dict]:
    approved = []
    for meta_file in sorted(config.OUTPUT_DIR.rglob("post_meta.json")):
        try:
            meta = json.loads(meta_file.read_text())
            if meta.get("status") == "approved":
                meta["_meta_path"] = str(meta_file)
                approved.append(meta)
        except Exception:
            pass
    return approved


def _generate_schedule(n_posts: int) -> list[datetime]:
    """
    Spread n_posts across SCHEDULE_DAYS days using POSTING_WINDOWS.
    Returns list of timezone-aware datetimes in ET.
    """
    windows = config.POSTING_WINDOWS
    days = config.SCHEDULE_DAYS

    slots_per_day = len(windows)
    total_slots = days * slots_per_day

    # Distribute evenly: pick every nth slot
    step = max(1, math.floor(total_slots / n_posts))

    now = datetime.now(TZ)
    start_date = now.date() + timedelta(days=1)  # start tomorrow

    all_slots: list[datetime] = []
    for day_offset in range(days):
        date = start_date + timedelta(days=day_offset)
        for window in windows:
            hh, mm = map(int, window.split(":"))
            dt = TZ.localize(datetime(date.year, date.month, date.day, hh, mm, 0))
            all_slots.append(dt)

    selected = [all_slots[i * step] for i in range(n_posts) if i * step < len(all_slots)]
    return selected[:n_posts]


def _ayrshare_post(meta: dict, scheduled_at: datetime) -> dict:
    video_path = meta["video_path"]
    caption = meta["caption"] + "\n\n" + " ".join(meta.get("hashtags", []))
    iso_time = scheduled_at.isoformat()

    # Step 1: Upload video to Ayrshare
    with open(video_path, "rb") as f:
        upload_resp = requests.post(
            f"{config.AYRSHARE_BASE_URL}/media/upload",
            headers={"Authorization": f"Bearer {config.AYRSHARE_API_KEY}"},
            files={"file": (Path(video_path).name, f, "video/mp4")},
            timeout=120,
        )
    upload_resp.raise_for_status()
    media_url = upload_resp.json()["url"]

    # Step 2: Create scheduled post
    payload = {
        "post": caption,
        "platforms": config.PLATFORMS,
        "mediaUrls": [media_url],
        "scheduleDate": iso_time,
        "shortenLinks": False,
    }
    post_resp = requests.post(
        f"{config.AYRSHARE_BASE_URL}/post",
        headers={
            "Authorization": f"Bearer {config.AYRSHARE_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    post_resp.raise_for_status()
    return post_resp.json()


def run(dry_run: bool = False):
    approved = _load_approved()
    if not approved:
        print("No approved posts found. Approve some in the QA server first.")
        return

    schedule = _generate_schedule(len(approved))
    summary = []

    for meta, dt in zip(approved, schedule):
        entry = {
            "job_id": meta["job_id"],
            "video": meta["video_path"],
            "caption_preview": meta["caption"][:80] + "...",
            "platforms": config.PLATFORMS,
            "scheduled_at": dt.isoformat(),
        }

        if not dry_run:
            try:
                result = _ayrshare_post(meta, dt)
                entry["ayrshare_id"] = result.get("id", "")
                entry["status"] = "scheduled"

                # Update meta file
                meta_path = Path(meta["_meta_path"])
                meta["status"] = "scheduled"
                meta["scheduled_at"] = dt.isoformat()
                meta["ayrshare_post_id"] = entry["ayrshare_id"]
                meta_path.write_text(json.dumps(meta, indent=2))

                print(f"  ✓ Scheduled: {meta['job_id']} → {dt.strftime('%b %d %I:%M%p ET')}")
            except Exception as e:
                entry["status"] = "error"
                entry["error"] = str(e)
                print(f"  ✗ Failed: {meta['job_id']} — {e}")
        else:
            entry["status"] = "dry_run"
            print(f"  [dry-run] {meta['job_id']} → {dt.strftime('%b %d %Y %I:%M%p ET')} ({', '.join(config.PLATFORMS)})")

        summary.append(entry)

    summary_path = config.OUTPUT_DIR / "schedule_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"\n{'Dry-run' if dry_run else 'Schedule'} summary → {summary_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't post")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
