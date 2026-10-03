"""Process configuration; no credential is ever placed in the graph State."""

import os
from pathlib import Path

from videoagents.contracts import RoleModels

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(os.getenv("VIDEOAGENTS_RUNTIME_DIR", str(PROJECT_ROOT / ".runtime" / "videoagents"))).resolve()
DEFAULT_SETTINGS = {
    "role_models": RoleModels().model_dump(), "search_provider": "none",
    "voice_provider": "none", "voice_app_id": "", "voice_resource_id": "", "voice_id": "",
    "voice_endpoint": "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
    "aligner_url": "", "capture_enabled": False, "max_llm_calls": 12,
    "max_voice_chars": 10000, "render_timeout_seconds": 1800,
}
SECRET_FIELDS = {"llm_api_key", "search_api_key", "voice_access_token", "voice_api_key", "aligner_api_key"}
