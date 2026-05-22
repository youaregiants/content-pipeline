"""
Renders a manifest.json → final MP4 via FFmpeg filter graph.
"""

import json
import subprocess
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def _resolve_font() -> str:
    font = Path(config.DEFAULT_FONT)
    if font.exists():
        return str(font)
    # Fallback system fonts
    for fallback in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        if Path(fallback).exists():
            return fallback
    return ""  # ffmpeg will use default


def _find_music(mood: str) -> Path | None:
    mood_keywords = {
        "energetic": ["energetic", "hype", "upbeat", "pump"],
        "chill": ["chill", "lo-fi", "lofi", "relax", "calm"],
        "emotional": ["emotional", "sad", "melancholy", "tender"],
        "hype": ["hype", "bass", "drop", "energetic"],
        "cinematic": ["cinematic", "epic", "orchestral", "atmospheric"],
    }
    keywords = mood_keywords.get(mood, [mood])
    music_files = (
        list(config.MUSIC_DIR.glob("*.mp3"))
        + list(config.MUSIC_DIR.glob("*.wav"))
        + list(config.MUSIC_DIR.glob("*.m4a"))
    )
    for kw in keywords:
        for f in music_files:
            if kw.lower() in f.name.lower():
                return f
    return music_files[0] if music_files else None


def _escape_drawtext(text: str) -> str:
    """Escape special chars for ffmpeg drawtext filter."""
    return (
        text
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace("%", "\\%")
    )


def render(job_dir: Path, manifest: dict, out_path: Path) -> Path:
    """
    Build and execute an FFmpeg filter graph from manifest.
    Returns path to rendered MP4.
    """
    clips = manifest.get("clips", [])
    if not clips:
        raise ValueError("Manifest has no clips")

    music_mood = manifest.get("music_mood", "chill")
    music_file = _find_music(music_mood)
    font_path = _resolve_font()

    # ── Inputs ─────────────────────────────────────────────────────────────
    # Input 0..N-1 = video clips, Input N = music (if any)
    input_args: list[str] = []
    for clip in clips:
        clip_path = job_dir / clip["filename"]
        if not clip_path.exists():
            raise FileNotFoundError(f"Clip not found: {clip_path}")
        input_args += ["-i", str(clip_path)]

    music_input_idx = len(clips)
    if music_file:
        input_args += ["-i", str(music_file)]

    # ── Filter graph ────────────────────────────────────────────────────────
    # Phase 1: trim + scale + pad each clip to canvas → [v0], [v1], ...
    # Phase 2: chain xfade between consecutive clips
    # Phase 3: drawtext captions on final composed stream
    # Phase 4: audio mix (clip audio + music)

    td = config.DEFAULT_TRANSITION_DURATION  # xfade duration
    W, H = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT
    fps = config.OUTPUT_FPS

    filter_parts: list[str] = []

    # ── Phase 1: Per-clip prepare ──────────────────────────────────────────
    clip_durations: list[float] = []
    for i, clip in enumerate(clips):
        start = float(clip.get("trim_start", 0.0))
        end = float(clip.get("trim_end", 0.0))
        if end <= start:
            raise ValueError(f"Clip {i} trim_end ({end}) must be > trim_start ({start})")
        duration = end - start
        clip_durations.append(duration)

        # trim → scale to fill canvas → pad to exact canvas → setsar → fps
        f = (
            f"[{i}:v]"
            f"trim=start={start}:end={end},"
            f"setpts=PTS-STARTPTS,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},"
            f"setsar=1,"
            f"fps={fps}"
            f"[vprep{i}]"
        )
        filter_parts.append(f)

    # ── Phase 2: xfade chain ───────────────────────────────────────────────
    # offset for xfade[i] = sum of durations[0..i] - td * i  - td
    #
    # For N clips there are N-1 transitions.
    # xfade offset = start-time (in the first stream's timeline) when the
    # transition begins. After each xfade the output timeline advances by
    # (duration_of_first_input - td).
    #
    # Running total of "output time consumed so far":
    #   after transition 0: clip_durations[0] - td
    #   after transition 1: clip_durations[0] + clip_durations[1] - 2*td
    #   ...
    # So offset[i] = sum(clip_durations[0..i]) - td*(i+1)

    if len(clips) == 1:
        composed_label = "vprep0"
    else:
        prev_label = "vprep0"
        time_consumed = 0.0  # output time consumed before current transition

        for i in range(1, len(clips)):
            transition = clips[i - 1].get("transition_out", "fade")
            xfade_type = "fade" if transition == "fade" else "fade"  # extend here for more types

            time_consumed += clip_durations[i - 1]
            offset = time_consumed - td  # when the overlap begins in the composed timeline
            offset = max(offset, 0.0)

            out_label = f"xf{i}"
            f = (
                f"[{prev_label}][vprep{i}]"
                f"xfade=transition={xfade_type}:duration={td}:offset={offset:.4f}"
                f"[{out_label}]"
            )
            filter_parts.append(f)

            # After this transition, time_consumed shrinks by td (the overlap)
            time_consumed -= td
            prev_label = out_label

        composed_label = prev_label

    # ── Phase 3: captions ──────────────────────────────────────────────────
    # Captions are drawn sequentially on the composed stream.
    # Each clip's caption is visible for that clip's duration window.
    # We calculate the start/end time of each clip in the *output* timeline.

    # Output timeline start times after all xfades:
    #   clip 0 starts at 0
    #   clip 1 starts at clip_durations[0] - td
    #   clip 2 starts at clip_durations[0] + clip_durations[1] - 2*td
    #   ...
    clip_start_times: list[float] = [0.0]
    running = 0.0
    for i in range(len(clips) - 1):
        running += clip_durations[i] - td
        clip_start_times.append(max(running, 0.0))

    caption_label = composed_label
    font_arg = f":fontfile='{font_path}'" if font_path else ""

    for i, clip in enumerate(clips):
        text = clip.get("caption_text", "").strip()
        if not text:
            continue

        t_start = clip_start_times[i]
        # For non-last clips, end the caption at the start of the next xfade so
        # it doesn't bleed through the transition into the adjacent clip.
        if i < len(clips) - 1:
            t_end = clip_start_times[i + 1]
        else:
            t_end = t_start + clip_durations[i]
        position = clip.get("caption_position", "bottom")

        if position == "bottom":
            x_expr = f"(w-text_w)/2"
            y_expr = f"h-text_h-{config.CAPTION_BOX_PADDING * 3}"
        elif position == "top":
            x_expr = f"(w-text_w)/2"
            y_expr = str(config.CAPTION_BOX_PADDING * 3)
        else:  # center
            x_expr = f"(w-text_w)/2"
            y_expr = f"(h-text_h)/2"

        escaped = _escape_drawtext(text)
        alpha_expr = (
            f"if(lt(t,{t_start}),0,"
            f"if(lt(t,{t_start+0.3:.4f}),(t-{t_start:.4f})/0.3,"
            f"if(lt(t,{t_end-0.3:.4f}),1,"
            f"if(lt(t,{t_end:.4f}),({t_end:.4f}-t)/0.3,0))))"
        )

        new_label = f"cap{i}"
        f = (
            f"[{caption_label}]"
            f"drawtext=text='{escaped}'"
            f"{font_arg}"
            f":fontsize={config.CAPTION_FONT_SIZE}"
            f":fontcolor={config.CAPTION_COLOR}"
            f":shadowcolor={config.CAPTION_SHADOW_COLOR}"
            f":shadowx=2:shadowy=2"
            f":x={x_expr}:y={y_expr}"
            f":alpha='{alpha_expr}'"
            f"[{new_label}]"
        )
        filter_parts.append(f)
        caption_label = new_label

    video_out_label = caption_label

    # ── Phase 4: audio ─────────────────────────────────────────────────────
    audio_filter_parts: list[str] = []
    audio_inputs: list[str] = []

    # Mix clip audio tracks
    for i in range(len(clips)):
        # Trim audio to match video trim
        start = float(clips[i].get("trim_start", 0.0))
        end = float(clips[i].get("trim_end", 0.0))
        f = (
            f"[{i}:a]"
            f"atrim=start={start}:end={end},"
            f"asetpts=PTS-STARTPTS,"
            f"loudnorm=I={config.LOUDNORM_TARGET_I}:TP={config.LOUDNORM_TARGET_TP}:LRA={config.LOUDNORM_TARGET_LRA}:linear=true"
            f"[aprep{i}]"
        )
        audio_filter_parts.append(f)
        audio_inputs.append(f"[aprep{i}]")

    if len(clips) > 1:
        # Chain acrossfade between each prepared audio track to match the video xfades.
        prev_audio = "aprep0"
        for i in range(1, len(clips)):
            out_audio = f"acf{i}"
            audio_filter_parts.append(
                f"[{prev_audio}][aprep{i}]acrossfade=d={td}[{out_audio}]"
            )
            prev_audio = out_audio
        clip_audio_label = prev_audio
    else:
        clip_audio_label = "aprep0"

    total_duration = sum(clip_durations) - td * (len(clips) - 1)

    if music_file:
        fade_out_start = max(total_duration - config.MUSIC_FADE_OUT, 0)
        audio_filter_parts.append(
            f"[{music_input_idx}:a]"
            f"afade=t=in:st=0:d={config.MUSIC_FADE_IN},"
            f"afade=t=out:st={fade_out_start:.2f}:d={config.MUSIC_FADE_OUT},"
            f"volume={config.MUSIC_VOLUME}"
            f"[amusic]"
        )
        audio_filter_parts.append(
            f"[{clip_audio_label}][amusic]amix=inputs=2:duration=first[afinal]"
        )
        audio_out_label = "afinal"
    else:
        audio_out_label = clip_audio_label

    # ── Assemble full filter graph ─────────────────────────────────────────
    all_filters = filter_parts + audio_filter_parts
    filter_complex = ";".join(all_filters)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = (
        ["ffmpeg", "-y"]
        + input_args
        + [
            "-filter_complex", filter_complex,
            "-map", f"[{video_out_label}]",
            "-map", f"[{audio_out_label}]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", str(config.OUTPUT_CRF),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", str(total_duration),
            "-movflags", "+faststart",
            str(out_path),
        ]
    )

    print(f"  [renderer] Running FFmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr[-3000:]}")

    print(f"  [renderer] Rendered → {out_path}")
    return out_path
