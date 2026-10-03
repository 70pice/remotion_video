"""Tavily search is discovery; raw source receipts and images remain separate."""

import httpx

from videoagents.providers.llm import CapabilityMissing
from videoagents.providers.network import public_transport
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint, now


def search(repository: Repository, query: str, job_id: str = "", revision: int = 1) -> dict:
    settings = SettingsService(repository).internal()
    if settings.get("search_provider") != "tavily" or not settings.get("search_api_key"):
        raise CapabilityMissing("主题创作需要配置搜索服务，或补充来源链接及真实证据图片", ["search", "source_urls", "assets"])
    command_id = repository.active_command_id(job_id)
    digest = fingerprint({"query": query, "revision": revision})
    previous = repository.operation(job_id, digest, "tavily") if job_id else None
    if previous:
        if previous["status"] == "COMPLETED":
            return previous["result"]
        if previous["status"] != "REJECTED" or not command_id or previous.get("command_id") == command_id:
            raise CapabilityMissing("此搜索已有未决提交，未自动重试；请核对搜索配置或补充来源链接", ["search_operation"])
    operation, ledger = None, {"command_id": command_id}
    if job_id:
        repository.reserve_metric(job_id, revision, "search_calls", 1, 4)
        operation = repository.retry_rejected_operation(previous["operation_id"], command_id, ledger) if previous else repository.start_operation(job_id, digest, "tavily", ledger)
        if not operation.get("new"):
            raise CapabilityMissing("相同搜索已被其他记录提交，未重复调用", ["search_operation"])
    try:
        with httpx.Client(timeout=45, trust_env=False, transport=public_transport()) as client:
            response = client.post("https://api.tavily.com/search", headers={"Authorization": "Bearer " + settings["search_api_key"]}, json={
            "query": query, "search_depth": "basic", "max_results": 5, "include_answer": False,
            "include_raw_content": True, "include_images": True, "include_image_descriptions": True,
            })
            if response.is_error:
                if operation:
                    repository.finish_operation(operation["operation_id"], "UNKNOWN" if response.status_code >= 500 or response.status_code == 408 else "REJECTED", {**ledger, "http_status": response.status_code})
                raise CapabilityMissing(f"搜索服务返回 HTTP {response.status_code}", ["search"])
            result = response.json()
        if operation:
            repository.finish_operation(operation["operation_id"], "COMPLETED", {**ledger, "result": result, "retrieved_at": now()})
        return result
    except CapabilityMissing:
        raise
    except Exception as exc:
        if operation:
            repository.finish_operation(operation["operation_id"], "UNKNOWN", {**ledger, "reason": type(exc).__name__})
        raise CapabilityMissing("搜索提交后的响应状态未知，未自动重复调用", ["search_operation"]) from exc
