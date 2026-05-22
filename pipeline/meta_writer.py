"""
Writes post_meta.json from manifest — consumed by QA server and scheduler.
"""

import json
from pathlib import Path


def write(job_dir: Path, manifest: dict, video_path: Path) -> Path:
    meta = {
        "job_id": job_dir.name,
        "video_path": str(video_path),
        "title": manifest.get("title", ""),
        "caption": manifest.get("caption", ""),
        "hashtags": manifest.get("hashtags", []),
        "music_mood": manifest.get("music_mood", ""),
        "notes": manifest.get("notes", ""),
        "status": "pending",       # pending | approved | rejected | scheduled
        "rejection_reason": "",
        "scheduled_at": "",
        "ayrshare_post_id": "",
    }

    meta_path = job_dir / "post_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    print(f"  [meta_writer] Meta written → {meta_path}")
    return meta_path
