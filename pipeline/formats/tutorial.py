"""
Tutorial format handler.

Expected job folder layout:
  selfie.mp4     — talking-head intro clip
  ableton.mp4    — screen recording of Ableton session (with audio)
  dance.mp4      — movement/dancing clip
  template.json  — { "format": "tutorial", "artist_name": "THEY." }

Output sequence:
  1. selfie    → 9:16, "How I made this for <artist>" overlay
  2. ableton   → silence >2s removed, segments hard-cut together
  3. spinner   → 1s animated "..." on black
  4. dance     → 9:16
"""

import re
import subprocess
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config

MIN_SILENCE_DB = -40   # dB threshold below which audio is considered silent
MIN_SILENCE_SEC = 2.0  # minimum silence duration to cut


def _find_clip(job_dir: Path, stems: list[str]) -> Path | None:
    for stem in stems:
        for ext in (".mp4", ".mov", ".MP4", ".MOV"):
            p = job_dir / (stem + ext)
            if p.exists():
                return p
    return None


def _detect_speech_segments(clip_path: Path) -> list[dict]:
    """Run ffmpeg silencedetect and return non-silent {start, end} segments."""
    result = subprocess.run(
        [
            config.FFMPEG_BIN, "-i", str(clip_path),
            "-af", f"silencedetect=noise={MIN_SILENCE_DB}dB:d={MIN_SILENCE_SEC}",
            "-f", "null", "-",
        ],
        capture_output=True, text=True,
    )
    stderr = result.stderr

    silence_starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", stderr)]
    silence_ends   = [float(x) for x in re.findall(r"silence_end: ([\d.]+)",   stderr)]

    # Total duration from ffmpeg header
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", stderr)
    if not m:
        raise ValueError(f"Could not read duration of {clip_path.name}")
    total = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    # Invert silence intervals → speech segments
    segments = []
    cursor = 0.0
    for s_start, s_end in zip(silence_starts, silence_ends):
        if s_start > cursor + 0.05:
            segments.append({"start": round(cursor, 3), "end": round(s_start, 3)})
        cursor = s_end

    if cursor < total - 0.05:
        segments.append({"start": round(cursor, 3), "end": round(total, 3)})

    return segments or [{"start": 0.0, "end": total}]


def _generate_spinner(out_path: Path):
    """1-second animated '...' on black, 9:16."""
    W, H, FPS = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS
    font_path = config.DEFAULT_FONT if Path(config.DEFAULT_FONT).exists() else ""
    ff = f":fontfile='{font_path}'" if font_path else ""
    base = f"fontcolor=white:fontsize=160:x=(w-text_w)/2:y=(h-text_h)/2"

    vf = (
        f"drawtext=text='.'{ff}:{base}:enable='lt(t,0.333)',"
        f"drawtext=text='..'{ff}:{base}:enable='between(t,0.333,0.667)',"
        f"drawtext=text='...'{ff}:{base}:enable='gte(t,0.667)'"
    )

    subprocess.run(
        [
            config.FFMPEG_BIN, "-y",
            "-f", "lavfi", "-i", f"color=c=black:size={W}x{H}:rate={FPS}",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-vf", vf,
            "-t", "1",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(out_path),
        ],
        check=True, capture_output=True,
    )


def _prepare_clip(src: Path, out: Path, overlay_text: str = ""):
    """Scale to 9:16, apply loudnorm, optionally burn in text overlay."""
    W, H, FPS = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT, config.OUTPUT_FPS

    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},setsar=1,fps={FPS}"
    )

    if overlay_text:
        fp = config.DEFAULT_FONT if Path(config.DEFAULT_FONT).exists() else ""
        ff = f":fontfile='{fp}'" if fp else ""
        escaped = overlay_text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
        pad = config.CAPTION_BOX_PADDING * 3
        vf += (
            f",drawtext=text='{escaped}'{ff}"
            f":fontcolor=white:fontsize={config.CAPTION_FONT_SIZE}"
            f":shadowcolor=black@0.7:shadowx=2:shadowy=2"
            f":x=(w-text_w)/2:y=h-text_h-{pad}"
        )

    af = (
        f"loudnorm=I={config.LOUDNORM_TARGET_I}"
        f":TP={config.LOUDNORM_TARGET_TP}"
        f":LRA={config.LOUDNORM_TARGET_LRA}:linear=true"
    )

    subprocess.run(
        [
            config.FFMPEG_BIN, "-y", "-i", str(src),
            "-vf", vf,
            "-af", af,
            "-c:v", "libx264", "-preset", "fast",
            "-crf", str(config.OUTPUT_CRF), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(out),
        ],
        check=True, capture_output=True,
    )


def _extract_segment(src: Path, start: float, end: float, out: Path):
    """Fast stream-copy extract of a time segment."""
    subprocess.run(
        [
            config.FFMPEG_BIN, "-y",
            "-ss", str(start), "-to", str(end),
            "-i", str(src),
            "-c", "copy", str(out),
        ],
        check=True, capture_output=True,
    )


def render(job_dir: Path, template: dict, out_path: Path) -> tuple[Path, dict]:
    """
    Build tutorial video. Returns (out_path, manifest_for_meta_writer).
    """
    artist_name = template.get("artist_name", "").strip()
    overlay = "How I made this" + (f" for {artist_name}" if artist_name else "")

    selfie = _find_clip(job_dir, ["selfie"])
    ableton = _find_clip(job_dir, ["ableton", "screen", "recording"])
    dance   = _find_clip(job_dir, ["dance", "dancing"])

    missing = [n for n, c in [("selfie", selfie), ("ableton", ableton), ("dance", dance)] if c is None]
    if missing:
        raise FileNotFoundError(
            f"Tutorial format missing: {missing}\n"
            f"Expected filenames: selfie.mp4, ableton.mp4, dance.mp4"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tutorial_") as tmp:
        tmp = Path(tmp)

        # 1 — Selfie with overlay
        print("  [tutorial] selfie...")
        selfie_out = tmp / "01_selfie.mp4"
        _prepare_clip(selfie, selfie_out, overlay_text=overlay)

        # 2 — Ableton: detect silence, extract segments, scale each
        print("  [tutorial] detecting silence in Ableton recording...")
        segments = _detect_speech_segments(ableton)
        print(f"  [tutorial] {len(segments)} segments ({len(segments)-1} silence gaps removed)")

        ableton_scaled = []
        for i, seg in enumerate(segments):
            raw = tmp / f"02_abl_raw_{i:02d}.mp4"
            scaled = tmp / f"02_abl_{i:02d}.mp4"
            _extract_segment(ableton, seg["start"], seg["end"], raw)
            _prepare_clip(raw, scaled)
            ableton_scaled.append(scaled)

        # 3 — Spinner
        print("  [tutorial] generating spinner...")
        spinner_out = tmp / "03_spinner.mp4"
        _generate_spinner(spinner_out)

        # 4 — Dance
        print("  [tutorial] dance...")
        dance_out = tmp / "04_dance.mp4"
        _prepare_clip(dance, dance_out)

        # 5 — Concat all parts
        parts = [selfie_out] + ableton_scaled + [spinner_out, dance_out]
        concat_txt = tmp / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{p}'" for p in parts))

        print(f"  [tutorial] concatenating {len(parts)} segments...")
        result = subprocess.run(
            [
                config.FFMPEG_BIN, "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_txt),
                "-c", "copy", str(out_path),
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed:\n{result.stderr[-2000:]}")

    manifest = {
        "format": "tutorial",
        "title": f"How I made this{f' for {artist_name}' if artist_name else ''}",
        "artist_name": artist_name,
        "ableton_segments_cut": len(segments),
        "caption": template.get("caption_hint", f"How I built this track layer by layer 🎹 Follow for more."),
        "hashtags": template.get("hashtag_hint", ["musicproduction", "ableton", "behindthescenes", "newmusic", "indieartist"]),
        "notes": f"{len(segments)} Ableton segments after silence removal",
    }

    print(f"  [tutorial] done → {out_path}")
    return out_path, manifest
