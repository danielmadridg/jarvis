import os
import glob
from dotenv import load_dotenv

load_dotenv()

# ── API Keys (set in .env) ────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Spotify API ──────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"

# ── Wake Word ────────────────────────────────────────────────────────
WAKE_WORD = "jarvis"

# ── Audio ────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000

# ── STT ──────────────────────────────────────────────────────────────
# "base" on GPU is recommended. Falls back to CPU if no CUDA available.
WHISPER_MODEL = "base"

# ── TTS ──────────────────────────────────────────────────────────────
EDGE_TTS_VOICE = "en-GB-RyanNeural"
EDGE_TTS_PITCH = "-12Hz"
EDGE_TTS_RATE = "+25%"

# ── AI Parser (Claude Haiku) ────────────────────────────────────────
AI_PARSER = True

# ── Monitor layout ───────────────────────────────────────────────────
# Adjust to match your setup. Index = position in EnumDisplayMonitors order.
MONITOR_ALIASES = {
    "arriba": 0, "up": 0, "top": 0,
    "centro": 1, "medio": 1, "center": 1, "middle": 1, "principal": 1, "main": 1,
    "izquierda": 2, "left": 2,
    "derecha": 3, "right": 3,
    "abajo": 3, "down": 3, "bottom": 3,
}

# ── Shortcuts folder — auto-scan ─────────────────────────────────────
# Point this to a folder containing .lnk / .url / .exe shortcuts for your apps
SHORTCUTS_DIR = os.getenv("SHORTCUTS_DIR", r"C:\ALL\Shortcuts")


def _scan_shortcuts():
    apps = {}
    if not os.path.isdir(SHORTCUTS_DIR):
        return apps
    for ext in ("*.lnk", "*.url", "*.exe"):
        for path in glob.glob(os.path.join(SHORTCUTS_DIR, "**", ext), recursive=True):
            name = os.path.splitext(os.path.basename(path))[0]
            key = name.lower()
            apps[key] = {"shortcut": path}
    return apps


APPS = _scan_shortcuts()
JARVIS_NAME = "Jarvis"
