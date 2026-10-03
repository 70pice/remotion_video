"""Search providers are discovery; raw source receipts and images remain separate."""

import httpx

from videoagents.providers.llm import CapabilityMissing
from videoagents.providers.network import public_transport
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint, now


def normalize_google(value: dict) -> dict:
    results, images = [], []
    for item in value.get("items", []) or []:
        if not isinstance(item, dict) or not item.get("link"):
            continue
        pagemap = item.get("pagemap") if isinstance(item.get("pagemap"), dict) else {}
        cse_images = pagemap.get("cse_image") if isinstance(pagemap.get("cse_image"), list) else []
        images.extend({"url": entry.get("src"), "source_url": item["link"], "description": item.get("title", "")}
                      for entry in cse_images if isinstance(entry, dict) and entry.get("src"))
        results.append({"title": item.get("title", ""), "url": item["link"], "content": item.get("snippet", "")})
    unique_images = []
    seen = set()
    for image in images:
        if image["url"] not in seen:
            seen.add(image["url"])
            unique_images.append(image)
    return {"results": results, "images": unique_images}


def search(repository: Repository, query: str, job_id: str = "", revision: int = 1, *,
           domains: list[str] | None = None, limit: int | None = None,
           platform: str = "web", max_results: int = 5) -> dict:
    settings = SettingsService(repository).internal()
    provider_name = settings.get("search_provider")
    if provider_name not in {"tavily", "google_cse"} or not settings.get("search_api_key"):
        raise CapabilityMissing("主题创作需要配置搜索服务，或补充来源链接及真实证据图片", ["search", "source_urls", "assets"])
    if provider_name == "google_cse" and not settings.get("google_search_engine_id"):
        raise CapabilityMissing("Google CSE 需要同时配置 API Key 和搜索引擎 ID", ["search", "google_search_engine_id"])
    if domains and any(not domain or "/" in domain or ":" in domain or len(domain) > 255 for domain in domains):
        raise CapabilityMissing("站内检索域名配置无效", ["search"])
    max_results = limit if limit is not None else max_results
    max_results = max(1, min(10, int(max_results)))
    scoped_query = query
    if domains and provider_name == "google_cse":
        scoped_query = query + " (" + " OR ".join(f"site:{domain}" for domain in domains) + ")"
    command_id = repository.active_command_id(job_id)
    digest = fingerprint({"query": scoped_query, "revision": revision, "provider": provider_name,
                          "platform": platform, "domains": domains or [], "max_results": max_results})
    previous = repository.operation(job_id, digest, provider_name) if job_id else None
    # 结果上限可变，但逻辑查询的未决提交不能因此消失；不同域名仍是独立搜索。
    search_scope = fingerprint({"query": query, "domains": sorted(domains or [])})
    if previous and previous["status"] == "COMPLETED":
        return previous["result"]
    if job_id and repository.unsettled_operation(job_id, provider_name, revision, search_scope):
        raise CapabilityMissing("此范围的搜索已有未决提交，调整结果数量不能重复提交；请对账或补充来源", ["search_operation"])
    if previous:
        if previous["status"] == "COMPLETED":
            return previous["result"]
        if previous["status"] != "REJECTED" or not command_id or previous.get("command_id") == command_id:
            raise CapabilityMissing("此搜索已有未决提交，未自动重试；请核对搜索配置或补充来源链接", ["search_operation"])
    operation, ledger = None, {"command_id": command_id, "revision": revision,
                              "platform": platform, "search_scope": search_scope}
    if job_id:
        repository.reserve_metric(job_id, revision, "search_calls", 1, settings["research_max_searches"])
        operation = (repository.retry_rejected_operation(previous["operation_id"], command_id, ledger)
                     if previous else repository.start_operation(job_id, digest, provider_name, ledger))
        if not operation.get("new"):
            raise CapabilityMissing("相同搜索已被其他记录提交，未重复调用", ["search_operation"])
    try:
        with httpx.Client(timeout=45, trust_env=False, transport=public_transport()) as client:
            if provider_name == "tavily":
                body = {
                    "query": query, "search_depth": "basic", "max_results": max_results, "include_answer": False,
                    "include_raw_content": True, "include_images": True, "include_image_descriptions": True,
                }
                if domains:
                    body["include_domains"] = domains
                response = client.post("https://api.tavily.com/search",
                    headers={"Authorization": "Bearer " + settings["search_api_key"]}, json=body)
            else:
                response = client.get("https://customsearch.googleapis.com/customsearch/v1", params={
                    "key": settings["search_api_key"], "cx": settings["google_search_engine_id"],
                    "q": scoped_query, "num": max_results,
                })
            if response.is_error:
                if operation:
                    repository.finish_operation(operation["operation_id"],
                        "UNKNOWN" if response.status_code >= 500 or response.status_code == 408 else "REJECTED",
                        {**ledger, "http_status": response.status_code})
                raise CapabilityMissing(f"搜索服务返回 HTTP {response.status_code}", ["search"])
            result = normalize_google(response.json()) if provider_name == "google_cse" else response.json()
        if operation:
            repository.finish_operation(operation["operation_id"], "COMPLETED",
                                        {**ledger, "result": result, "retrieved_at": now()})
        return result
    except CapabilityMissing:
        raise
    except Exception as exc:
        if operation:
            repository.finish_operation(operation["operation_id"], "UNKNOWN", {**ledger, "reason": type(exc).__name__})
        raise CapabilityMissing("搜索提交后的响应状态未知，未自动重复调用", ["search_operation"]) from exc
