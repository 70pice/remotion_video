"""Optional configured alignment service. Times are never estimated from character counts."""

from pathlib import Path

import httpx

from videoagents.contracts import Alignment
from videoagents.providers.llm import CapabilityMissing
from videoagents.providers.network import public_transport, validate_url
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


def align(repository: Repository, audio: Path, audio_hash: str, segments: list[dict]) -> Alignment:
    settings = SettingsService(repository).internal()
    if not settings.get("aligner_url"):
        raise CapabilityMissing("缺少可靠音频时间戳；请上传实测 alignment，或配置对齐服务", ["alignment"])
    validate_url(settings["aligner_url"], local_provider=True)
    headers = {"Authorization": "Bearer " + settings["aligner_api_key"]} if settings.get("aligner_api_key") else {}
    with audio.open("rb") as stream, httpx.Client(timeout=180, trust_env=False, transport=public_transport(local_provider=True)) as client:
        import json
        response = client.post(settings["aligner_url"], headers=headers, files={"audio": (audio.name, stream)},
                               data={"segments": json.dumps(segments, ensure_ascii=False), "audio_sha256": audio_hash})
        if response.is_error:
            raise CapabilityMissing(f"对齐服务返回 HTTP {response.status_code}", ["alignment"])
        value = response.json()
    value.update(audio_sha256=audio_hash, origin="aligner")
    return Alignment.model_validate(value)
