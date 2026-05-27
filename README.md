# content-pipeline

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![FFmpeg required](https://img.shields.io/badge/ffmpeg-required-orange)
![Claude Vision](https://img.shields.io/badge/claude-opus--4--5-purple)

On-demand AI video editing pipeline for a music artist's social media content.
Drop raw clips into a job folder, run one command, get two files back:

```
export/my-post/
  my-post_final.mp4      ← upload to TikTok / Instagram / YouTube
  my-post_caption.txt    ← copy-paste caption, hashtags, and platform tips
```

---

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install FFmpeg
brew install ffmpeg          # macOS
# sudo apt install ffmpeg    # Linux

# 3. Configure
cp .env.example .env
# edit .env — add your ANTHROPIC_API_KEY

# 4. Drop clips into a job folder and run
./run.sh
```

---

## Usage

```bash
./run.sh
```

Processes every pending job folder in `input/` and exits. Run it again whenever you have new jobs ready.

To reprocess a completed job, delete its `.done` marker:
```bash
rm input/my-post/.done
./run.sh
```

---

## Job Folder Format

```
input/
  my-post-name/
    [video clips]
    template.json     ← required — declares format and post details
```

### Generic format (Claude Vision edits)

```json
{
  "format": "generic",
  "style_notes": "Fast-paced performance cuts. Lead with the hook at 0:08 of clip2.",
  "caption_hint": "new single out now — link in bio",
  "hashtag_hint": ["newmusic", "indieartist", "musicvideo"],
  "music_mood": "energetic",
  "max_duration": 30
}
```

Drop any `.mp4` / `.mov` clips into the folder. Claude Vision analyzes a frame from each, picks the best moments, and generates a full edit manifest.

### Tutorial format (deterministic, no Claude needed)

Fixed 4-part sequence: selfie intro → Ableton layers (silence auto-removed) → `...` spinner → dance clip.

```json
{
  "format": "tutorial",
  "artist_name": "THEY.",
  "caption_hint": "How I built this track layer by layer 🎹",
  "hashtag_hint": ["musicproduction", "ableton", "behindthescenes", "newmusic"]
}
```

Required filenames:
```
input/my-tutorial/
  selfie.mp4      ← talking-head intro
  ableton.mp4     ← screen recording with audio (silence gaps auto-cut)
  dance.mp4       ← movement clip
  template.json
```

Copy `assets/template.tutorial.json` as a starter.

---

## File Structure

```
content-pipeline/
  config.py              Paths, render settings, Claude model
  watcher.py             Orchestrator — finds and runs all pending jobs
  run.sh                 Single entrypoint
  requirements.txt
  .env.example
  pipeline/
    analyzer.py          Claude Vision keyframe analysis → manifest.json
    renderer.py          manifest.json → FFmpeg filter graph → MP4
    meta_writer.py       manifest → caption.txt
    formats/
      tutorial.py        Tutorial format handler (silence detection, spinner)
  assets/
    fonts/               Drop .ttf files here (Montserrat Bold recommended)
    music/               Background audio (.mp3 / .wav / .m4a)
    overlays/            Logos / watermarks
    template.example.json     Generic format starter
    template.tutorial.json    Tutorial format starter
  input/                 Job folders go here (gitignored)
  export/                Rendered MP4s + caption files (gitignored)
  logs/                  Pipeline logs (gitignored)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (generic format) | Anthropic API key |
| `FFMPEG_BIN` | No | Path to ffmpeg (default: `ffmpeg`) |
| `FFPROBE_BIN` | No | Path to ffprobe (default: `ffprobe`) |

---

## Known Gaps

- Audio normalization uses single-pass `loudnorm` (accurate; true two-pass requires a separate ffprobe analysis step)
- YouTube Shorts thumbnail not auto-generated
- No unit tests yet
