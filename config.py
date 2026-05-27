import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# --- Paths ---
ROOT = Path(__file__).parent
INPUT_DIR = ROOT / "input"
EXPORT_DIR = ROOT / "export"
LOGS_DIR = ROOT / "logs"
ASSETS_DIR = ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"
OVERLAYS_DIR = ASSETS_DIR / "overlays"

for _d in (INPUT_DIR, EXPORT_DIR, LOGS_DIR):
    _d.mkdir(exist_ok=True)

# --- API Keys ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# --- Claude model ---
CLAUDE_MODEL = "claude-opus-4-5"

# --- FFmpeg ---
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")

# --- Output format ---
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920   # 9:16 portrait
OUTPUT_FPS = 30
OUTPUT_CRF = 23        # H.264 quality (lower = better)

# --- Captions ---
DEFAULT_FONT = str(FONTS_DIR / "Montserrat-Bold.ttf")
CAPTION_FONT_SIZE = 56
CAPTION_COLOR = "white"
CAPTION_SHADOW_COLOR = "black@0.6"
CAPTION_BOX_PADDING = 12

# --- Crossfades ---
DEFAULT_TRANSITION_DURATION = 0.5   # seconds

# --- Music ---
MUSIC_VOLUME = 0.25   # relative to clip audio
MUSIC_FADE_IN = 1.0
MUSIC_FADE_OUT = 2.0

# --- Audio normalization (loudnorm EBU R128) ---
LOUDNORM_TARGET_I = -16     # integrated loudness (LUFS)
LOUDNORM_TARGET_TP = -1.5   # true peak (dBFS)
LOUDNORM_TARGET_LRA = 11    # loudness range

