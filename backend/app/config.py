from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DOWNLOAD_DIR = PROJECT_ROOT / "downloads"
DEFAULT_CONVERSION_DIR = PROJECT_ROOT / "converted"
DATA_DIR = PROJECT_ROOT / "backend" / "data"

DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_CONVERSION_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "media_tool.db"
LOG_PATH = DATA_DIR / "media_tool.log"

HOST = os.getenv("UMT_HOST", "127.0.0.1")
PORT = int(os.getenv("UMT_PORT", "8000"))

ALLOWED_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

DEFAULT_SETTINGS: Dict[str, Any] = {
    "download_dir": str(DEFAULT_DOWNLOAD_DIR),
    "conversion_dir": str(DEFAULT_CONVERSION_DIR),
    "max_concurrent_downloads": 3,
    "default_video_quality": "1080p",
    "default_audio_format": "mp3",
    "default_audio_bitrate": "320k",
    "duplicate_handling": "rename",  # "skip" | "rename" | "overwrite"
    "theme": "dark",
    "ffmpeg_path": "",
    "ffprobe_path": "",
    "ytdlp_check_updates": True,
    "enable_browser_cookies": False,
    "browser_for_cookies": "edge",
    "embed_thumbnail": True,
    "embed_subtitles": False,
}
