"""Process configuration; no credential is ever placed in the graph State."""

import os
from pathlib import Path

from videoagents.contracts import RoleModels

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(os.getenv("VIDEOAGENTS_RUNTIME_DIR", str(PROJECT_ROOT / ".runtime" / "videoagents"))).resolve()
DEFAULT_SETTINGS = {
    "role_models": RoleModels().model_dump(), "search_provider": "none",
    "google_search_engine_id": "",
    "research_platforms": ["web", "x", "youtube", "zhihu", "reddit", "bilibili", "google"],
    "research_results_per_platform": 3, "research_max_searches": 8, "research_max_sources": 12,
    "research_max_visuals": 8, "research_download_images": True,
    "script_discussion_enabled": False, "script_discussion_max_rounds": 2,
    "voice_provider": "none", "voice_app_id": "", "voice_resource_id": "", "voice_id": "",
    "voice_endpoint": "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
    "voice_model": "seed-tts-2.0-standard",
    "aligner_url": "", "capture_enabled": True, "max_llm_calls": 12,
    "max_voice_chars": 10000, "render_timeout_seconds": 1800,
}
SECRET_FIELDS = {"llm_api_key", "search_api_key", "voice_access_token", "voice_api_key", "aligner_api_key"}
