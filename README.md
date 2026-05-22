# content-pipeline

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![FFmpeg required](https://img.shields.io/badge/ffmpeg-required-orange)
![Claude Vision](https://img.shields.io/badge/claude-opus--4--5-purple)

Overnight AI video editing pipeline for a music artist's social media content.
Drop raw clips into a job folder → Claude Vision analyzes them → FFmpeg renders a 9:16 reel → two files land in `export/`:

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

# 4. Create a job folder
mkdir -p input/my-first-reel
cp /path/to/clip1.mp4 input/my-first-reel/
cp /path/to/clip2.mp4 input/my-first-reel/
# optional: copy assets/template.example.json → input/my-first-reel/template.json

# 5. Run
./run.sh pipeline

# 6. Grab your files
open export/my-first-reel/
```

---

## Commands

```
./run.sh pipeline       Process all pending jobs once
./run.sh watch          Continuous mode — scans input/ every 30s
./run.sh cron-install   Install nightly 2am cron job
./run.sh cron-remove    Remove the cron job
```

---

## File Structure

```
content-pipeline/
  config.py              Paths, render settings, Claude model
  watcher.py             Orchestrator — dispatches job folders through pipeline
  run.sh                 CLI entrypoint
  requirements.txt
  .env.example
  pipeline/
    analyzer.py          Claude Vision keyframe analysis → manifest.json
    renderer.py          manifest.json → FFmpeg filter graph → MP4
    meta_writer.py       manifest → caption.txt (caption, hashtags, platform tips)
  assets/
    fonts/               Drop .ttf files here (Montserrat Bold recommended)
    music/               Background audio (.mp3 / .wav / .m4a)
    overlays/            Logos / watermarks
    template.example.json
  input/                 Job folders go here (gitignored)
  export/                Rendered MP4s + caption files (gitignored)
  logs/                  Watcher and cron logs (gitignored)
```

---

## Job Folder Format

```
input/
  my-post-name/
    clip1.mp4
    clip2.mp4
    clip3.mp4
    template.json        ← optional Claude hints (see assets/template.example.json)
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `FFMPEG_BIN` | No | Path to ffmpeg (default: `ffmpeg`) |
| `FFPROBE_BIN` | No | Path to ffprobe (default: `ffprobe`) |

---

## Known Gaps

- Audio normalization uses single-pass `loudnorm` (accurate enough; true two-pass requires a separate ffprobe analysis step)
- YouTube Shorts thumbnail not auto-generated
- No unit tests yet
