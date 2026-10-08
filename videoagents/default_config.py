"""Process configuration; no credential is ever placed in the graph State."""

import os
from pathlib import Path

from videoagents.contracts import RoleModelConfig, RoleModels

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(os.getenv("VIDEOAGENTS_RUNTIME_DIR", str(PROJECT_ROOT / ".runtime" / "videoagents"))).resolve()
DEFAULT_VOICE_STYLE = (
    "像真正理解内容的人在给朋友讲一个值得关注的新发现，不要播音腔、朗诵腔或逐字念稿。"
    "开头带克制的好奇，问题句自然上扬；解释段放松、清楚，给长句留出呼吸；"
    "遇到转折和反常识信息时先收一下，再加重真正关键的内容；结论坚定收住。"
    "不要字字加重，不要全程兴奋，也不要一口气读完。"
)
DEFAULT_SCRIPT_MODEL = "doubao-seed-2-1-pro-260915"
DEFAULT_ROLE_MODELS = RoleModels(
    voice=RoleModelConfig(enabled=True),
    screenwriter=RoleModelConfig(
        enabled=True, provider="claude_code_cli", model=DEFAULT_SCRIPT_MODEL, timeout_seconds=900
    ),
    script_reviewer=RoleModelConfig(
        enabled=True, provider="claude_code_cli", model=DEFAULT_SCRIPT_MODEL, timeout_seconds=900
    ),
).model_dump()
DEFAULT_SETTINGS = {
    "role_models": DEFAULT_ROLE_MODELS, "search_provider": "none",
    "google_search_engine_id": "",
    "research_platforms": ["web", "x", "youtube", "zhihu", "reddit", "bilibili", "google"],
    "research_results_per_platform": 3, "research_max_searches": 8, "research_max_sources": 12,
    "research_download_images": True,
    "script_discussion_max_rounds": 1,
    "voice_provider": "none", "voice_app_id": "", "voice_resource_id": "", "voice_id": "",
    "voice_endpoint": "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
    "voice_model": "seed-tts-2.0-expressive",
    "voice_style": DEFAULT_VOICE_STYLE, "voice_speech_rate": 0,
    "aligner_url": "", "capture_enabled": True, "max_llm_calls": 20,
    "max_voice_chars": 10000, "render_timeout_seconds": 1800,
}
SECRET_FIELDS = {"llm_api_key", "search_api_key", "voice_access_token", "voice_api_key", "aligner_api_key", "ark_api_key"}
