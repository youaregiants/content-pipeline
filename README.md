# content-pipeline

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![FFmpeg required](https://img.shields.io/badge/ffmpeg-required-orange)
![Claude Vision](https://img.shields.io/badge/claude-opus--4--5-purple)
![Ayrshare](https://img.shields.io/badge/scheduler-ayrshare-green)

Overnight video editing + social scheduling pipeline for a music artist's content.
Drop raw clips into a job folder → Claude Vision generates an edit manifest → FFmpeg renders the reel → approve in browser → batch-schedule to TikTok, Instagram, and YouTube Shorts via Ayrshare.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
brew install ffmpeg          # macOS
# sudo apt install ffmpeg    # Linux

# 2. Configure
cp .env.example .env
# edit .env — add ANTHROPIC_API_KEY and AYRSHARE_API_KEY

# 3. Create a job folder
mkdir input/my-first-reel
cp /path/to/clip1.mp4 input/my-first-reel/
cp /path/to/clip2.mp4 input/my-first-reel/
# optionally copy assets/template.example.json → input/my-first-reel/template.json

# 4. Run the pipeline
./run.sh pipeline

# 5. Review output
./run.sh qa
# open http://localhost:8765 — approve or reject

# 6. Schedule (dry-run first)
./run.sh schedule --dry-run   # inspect output/schedule_summary.json
./run.sh schedule             # send to Ayrshare
```

---

## File Structure

```
content-pipeline/
  config.py              All settings and env var loading
  watcher.py             Orchestrator — dispatches job folders through pipeline
  qa_server.py           Local browser QA UI (http://localhost:8765)
  scheduler.py           Batch schedules approved posts to Ayrshare
  pipeline/
    analyzer.py          Claude Vision → manifest.json
    renderer.py          manifest.json → FFmpeg filter graph → MP4
    meta_writer.py       manifest → post_meta.json for QA/scheduling
  assets/
    fonts/               Drop .ttf fonts here (Montserrat Bold recommended)
    music/               Background music files (.mp3/.wav/.m4a)
    overlays/            Logo/watermark images
    template.example.json  Copy into job folders as template.json
  input/                 Job folders go here (gitignored)
  output/                Rendered MP4s and meta JSONs (gitignored)
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
    template.json   ← optional hints for Claude
```

Name the job folder whatever you want — it becomes the `job_id` in all metadata.

---

## Automation

Install a nightly 2am cron job:
```bash
./run.sh cron-install
./run.sh cron-remove   # to undo
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `AYRSHARE_API_KEY` | Yes | Ayrshare Business plan API key |
| `FFMPEG_BIN` | No | Path to ffmpeg binary (default: `ffmpeg`) |
| `FFPROBE_BIN` | No | Path to ffprobe binary (default: `ffprobe`) |

---

## Known Gaps

- No audio normalization before render (clips with mismatched levels will be uneven)
- YouTube Shorts thumbnail not auto-generated
- No unit tests yet

---

## Pushing to GitHub

After cloning or init:
```bash
# On github.com: create a new repo (don't initialize with README)
git remote add origin git@github.com:YOUR_USERNAME/content-pipeline.git
git push -u origin main
```
