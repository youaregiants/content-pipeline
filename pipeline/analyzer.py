"""
Analyzes video clips in a job folder using Claude Vision and writes manifest.json.
"""

import base64
import json
import re
import subprocess
import tempfile
from pathlib import Path

import anthropic

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config

client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are a professional social media video editor for a music artist.
Analyze the provided video frames and return a structured edit manifest as valid JSON.
Focus on: energy level, best moments, visual quality, caption opportunities, and how clips flow together.
"""

MANIFEST_SCHEMA = """
Return ONLY valid JSON matching this schema:
{
  "title": "short post title (under 60 chars)",
  "caption": "Instagram/TikTok caption (150-220 chars, includes CTA)",
  "hashtags": ["array", "of", "hashtags"],
  "music_mood": "one of: [energetic, chill, emotional, hype, cinematic]",
  "clips": [
    {
      "filename": "original_filename.mp4",
      "trim_start": 0.0,
      "trim_end": 5.0,
      "caption_text": "text overlay for this clip (empty string if none)",
      "caption_position": "bottom",
      "transition_out": "fade"
    }
  ],
  "total_target_duration": 15.0,
  "notes": "any special rendering notes"
}
Transition options: "fade", "none"
Caption position options: "top", "center", "bottom"
"""


def _extract_frame(clip_path: Path, timestamp: float = 1.0) -> str:
    """Extract a frame from a video clip and return as base64 JPEG."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run(
        [
            config.FFMPEG_BIN, "-y",
            "-ss", str(timestamp),
            "-i", str(clip_path),
            "-vframes", "1",
            "-vf", "scale=1280:-1",
            "-q:v", "3",
            tmp_path,
        ],
        check=True,
        capture_output=True,
    )

    with open(tmp_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")

    Path(tmp_path).unlink(missing_ok=True)
    return data


def _get_duration(clip_path: Path) -> float:
    result = subprocess.run(
        [
            config.FFPROBE_BIN, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(clip_path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def analyze(job_dir: Path) -> dict:
    clips = sorted(job_dir.glob("*.mp4")) + sorted(job_dir.glob("*.mov"))
    if not clips:
        raise ValueError(f"No video clips found in {job_dir}")

    template_path = job_dir / "template.json"
    template = {}
    if template_path.exists():
        template = json.loads(template_path.read_text())

    # Build message with one frame per clip
    content = []
    clip_info = []

    for clip in clips:
        try:
            duration = _get_duration(clip)
            frame_b64 = _extract_frame(clip, timestamp=min(1.0, duration * 0.25))
        except Exception as e:
            print(f"  [warn] Could not process {clip.name}: {e}")
            continue

        content.append({
            "type": "text",
            "text": f"Clip: {clip.name} (duration: {duration:.1f}s)",
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": frame_b64,
            },
        })
        clip_info.append({"filename": clip.name, "duration": duration})

    user_prompt = f"Clips available: {json.dumps(clip_info)}\n"
    if template:
        user_prompt += f"Template hints: {json.dumps(template)}\n"
    user_prompt += "\nGenerate the edit manifest now."

    content.append({"type": "text", "text": user_prompt})

    response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT + "\n\n" + MANIFEST_SCHEMA,
        messages=[{"role": "user", "content": content}],
    )

    raw = response.content[0].text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
    if match:
        raw = match.group(1)

    manifest = json.loads(raw)

    # Persist alongside job
    manifest_path = job_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"  [analyzer] Manifest written → {manifest_path}")

    return manifest
