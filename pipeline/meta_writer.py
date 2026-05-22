"""
Writes job_caption.txt from manifest — copy-paste ready for TikTok/Instagram/YouTube.
"""

from pathlib import Path


def write(job_dir: Path, manifest: dict, video_path: Path) -> Path:
    job_name = job_dir.name
    caption = manifest.get("caption", "")
    hashtags = manifest.get("hashtags", [])
    hashtag_str = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
    notes = manifest.get("notes", "")
    title = manifest.get("title", job_name)

    lines = [
        f"TITLE: {title}",
        "",
        "─" * 50,
        "CAPTION",
        "─" * 50,
        caption,
        "",
        "─" * 50,
        "HASHTAGS",
        "─" * 50,
        hashtag_str,
        "",
    ]

    if notes:
        lines += [
            "─" * 50,
            "NOTES",
            "─" * 50,
            notes,
            "",
        ]

    lines += [
        "─" * 50,
        "PLATFORM TIPS",
        "─" * 50,
        "TikTok     — paste caption + hashtags into description",
        "Instagram  — paste caption into caption field, hashtags at the end or first comment",
        "YouTube    — paste title into title field, caption into description, hashtags at the bottom",
        "",
        f"VIDEO: {video_path}",
    ]

    text = "\n".join(lines)

    caption_path = video_path.parent / f"{job_name}_caption.txt"
    caption_path.write_text(text)
    print(f"  [meta_writer] Caption written → {caption_path}")
    return caption_path
