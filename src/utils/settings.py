import json
import os
from uuid import uuid4

from src.utils.app_paths import user_data_dir


SETTINGS_FILE = user_data_dir() / "settings.json"
DEFAULT_SETTINGS = {
    "ollama_model": "llama3:8b",
    "dark": True,
    "motion": None,
    "ocr": False,
    "screen_documents_on_upload": True,
    "starfield": False,
    "logo_glow": True,
}


def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return settings
        if isinstance(saved, dict):
            settings.update(saved)
    return settings


def save_settings(settings: dict) -> None:
    temporary = SETTINGS_FILE.with_suffix(f".{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(temporary, SETTINGS_FILE)
