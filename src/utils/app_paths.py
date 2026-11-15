import os
from pathlib import Path
import sys


def assets_dir() -> Path:
    """Read-only files bundled with the app."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    """Writable files that survive app updates."""
    override = os.environ.get("SECURERAG_DATA_DIR")
    if override:
        result = Path(override).resolve()
        result.mkdir(parents=True, exist_ok=True)
        return result
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"

    result = base / "SecureRAG"
    result.mkdir(parents=True, exist_ok=True)
    return result


FINAL_MODEL = assets_dir() / "models" / "securerag-classifier-FINAL"
DOCUMENT_GUARD_MODEL = assets_dir() / "models" / "securerag-docguard-v3-seed2"
EMBEDDING_MODEL = assets_dir() / "models" / "embeddings" / "all-MiniLM-L6-v2"
