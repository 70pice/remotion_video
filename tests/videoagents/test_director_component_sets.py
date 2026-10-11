import json
from pathlib import Path

from videoagents.nodes import director

SET_IDS = [f"A{index:02d}" for index in range(1, 13)] + [f"B{index:02d}" for index in range(1, 19)]
REGISTRY_PATH = Path("docs/component-set-registry.json")


def _registry_payload(*, suffix: str = "one", a10_requirement: str | None = None) -> dict:
    sets = []
    for index, set_id in enumerate(SET_IDS):
        is_a = set_id.startswith("A")
        requirement = (
            a10_requirement
            if set_id == "A10" and a10_requirement is not None
            else f"asset-requirement-{set_id}-{suffix}"
        )
        sets.append(
            {
                "id": set_id,
                "name": f"name-{set_id}",
                "category": "has_material" if is_a else "no_material",
                "registration_status": "registered",
                "review_status": "approved" if index == 0 else "registered_pending_review",
                "usable_scope": f"scope-{set_id}",
                "when_to_use": [f"when-{set_id}-{suffix}"],
                "not_for": [f"not-for-{set_id}-{suffix}"],
                "components": {
                    "native_ids": [f"Native-{set_id}"],
                    "semantic_ids": [f"semantic-{set_id}"] if not is_a else [],
                    "adapter_capabilities": [f"adapter-{set_id}"],
                },
                "asset_requirements": {
                    "asset_id_required": is_a,
                    "accepted_media": ["image/png"] if is_a else [],
                    "requirements": requirement,
                },
                "director_guidance": {
                    "visual_sequence": [f"visual-{set_id}-{suffix}-1", f"visual-{set_id}-{suffix}-2"],
                    "production_adaptation": f"adapt-{set_id}-{suffix}",
                    "content_constraints": [f"constraint-{set_id}-{suffix}"],
                },
                "component_demo_request": {
                    "required": ["base_revision", "idempotency_key", "set_id", "asset_id"],
                    "forbidden": ["tutorial_steps"],
                    "fixed_boundaries": [f"sample-constraint-{set_id}-{suffix}"],
                    "asset_id": f"asset-instance-{set_id}-{suffix}",
                    "job_id": f"job-instance-{set_id}-{suffix}",
                },
                "component_sample": {
                    "job_id": f"sample-job-{set_id}-{suffix}",
                    "asset_id": f"sample-asset-{set_id}-{suffix}",
                    "duration_seconds": 18,
                },
                "content_input": {
                    "common": ["title", "body", "takeaway"],
                    "specific": {
                        "items": "field-items",
                        "metric": {
                            "label": "field-metric-label",
                            "value": "field-metric-value",
                            "detail": "field-metric-detail",
                        },
                        "numeric_items": "field-numeric-items",
                    },
                    "limits": {"title": 18, "body": 60, "takeaway": 18},
                    "example": {
                        "title": f"example-title-{set_id}-{suffix}",
                        "body": "FAKE_AMOUNT_133 plus FAKE_AMOUNT_399",
                        "metric": {
                            "label": "FAKE_METRIC_LABEL",
                            "value": "FAKE_AMOUNT_399",
                            "detail": "FAKE_AMOUNT_133+FAKE_AMOUNT_133+FAKE_AMOUNT_133",
                        },
                    },
                    "sample_payload": {
                        "asset_id": f"content-asset-{set_id}-{suffix}",
                        "job_id": f"content-job-{set_id}-{suffix}",
                    },
                },
            }
        )
    return {"sets": sets}


def _write_registry(path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _actual_registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _line_for(summary: str, set_id: str) -> str:
    return next(line for line in summary.splitlines() if line.lstrip().startswith(f"- {set_id} "))


def test_component_set_registry_injects_unique_director_guidance_for_all_thirty_sets(tmp_path):
    path = tmp_path / "component-set-registry.json"
    _write_registry(path, _registry_payload(suffix="unique"))

    summary = director.prompt_component_set_registry(path)

    for set_id in SET_IDS:
        assert f"visual-{set_id}-unique-1" in summary
        assert f"visual-{set_id}-unique-2" in summary
        assert f"adapt-{set_id}-unique" in summary
        assert f"constraint-{set_id}-unique" in summary
        assert f"when-{set_id}-unique" in summary
        assert f"not-for-{set_id}-unique" in summary
        assert f"asset-requirement-{set_id}-unique" in summary


def test_component_set_registry_registration_does_not_imply_review_approval(tmp_path):
    path = tmp_path / "component-set-registry.json"
    _write_registry(path, _registry_payload(suffix="status"))

    summary = director.prompt_component_set_registry(path)

    approved_line = _line_for(summary, "A01")
    pending_line = _line_for(summary, "A02")
    assert "registration_status=registered" in approved_line
    assert "review_status=approved" in approved_line
    assert "registration_status=registered" in pending_line
    assert "review_status=registered_pending_review" in pending_line
    assert "review_status=approved" not in pending_line


def test_component_set_registry_reads_latest_file_without_cache(tmp_path):
    path = tmp_path / "component-set-registry.json"
    _write_registry(path, _registry_payload(suffix="first"))
    assert "adapt-A10-first" in director.prompt_component_set_registry(path)

    _write_registry(path, _registry_payload(suffix="second"))
    summary = director.prompt_component_set_registry(path)

    assert "adapt-A10-second" in summary
    assert "adapt-A10-first" not in summary


def test_component_set_registry_omits_sample_instance_values_and_keeps_content_field_names(tmp_path):
    path = tmp_path / "component-set-registry.json"
    _write_registry(path, _registry_payload(suffix="sample"))

    summary = director.prompt_component_set_registry(path)

    for leaked in [
        "sample-job-A10-sample",
        "sample-asset-A10-sample",
        "asset-instance-A10-sample",
        "job-instance-A10-sample",
        "content-asset-A10-sample",
        "content-job-A10-sample",
        "example-title-A10-sample",
        "FAKE_AMOUNT_133",
        "FAKE_AMOUNT_399",
        "FAKE_METRIC_LABEL",
    ]:
        assert leaked not in summary
    for field_name in [
        "title",
        "body",
        "takeaway",
        "items",
        "metric.label",
        "metric.value",
        "metric.detail",
        "numeric_items",
    ]:
        assert field_name in summary or f"content.{field_name}" in summary
    assert "sample-constraint-A10-sample" in summary


def test_component_set_registry_does_not_truncate_a10_asset_requirements(tmp_path):
    path = tmp_path / "component-set-registry.json"
    long_requirement = (
        "A10 must preserve the source bill layout and manual scan targets; "
        "this intentionally long requirement keeps its final sentinel "
        "A10_REQUIREMENT_END_SENTINEL"
    )
    _write_registry(path, _registry_payload(suffix="long", a10_requirement=long_requirement))

    summary = director.prompt_component_set_registry(path)

    a10_line = _line_for(summary, "A10")
    assert "A10_REQUIREMENT_END_SENTINEL" in a10_line


def test_component_set_registry_degrades_safely_for_missing_invalid_or_malformed_files(tmp_path):
    missing = tmp_path / "missing.json"
    missing_summary = director.prompt_component_set_registry(missing)
    assert missing_summary.strip()
    assert "Traceback" not in missing_summary

    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")
    invalid_summary = director.prompt_component_set_registry(invalid_json)
    assert invalid_summary.strip()
    assert "Traceback" not in invalid_summary

    malformed = tmp_path / "malformed.json"
    _write_registry(malformed, {"sets": {"A01": {}}})
    malformed_summary = director.prompt_component_set_registry(malformed)
    assert malformed_summary.strip()
    assert "A01" not in malformed_summary
    assert "Traceback" not in malformed_summary


def test_actual_component_set_registry_has_exactly_thirty_registered_production_sets():
    registry = _actual_registry()
    sets = registry["sets"]
    ids = [item["id"] for item in sets]

    assert len(ids) == 30
    assert len(set(ids)) == 30
    assert set(ids) == set(SET_IDS)
    assert {item["registration_status"] for item in sets} == {"registered"}
    assert [item["id"] for item in sets if item["review_status"] == "approved"] == ["A01"]
    assert registry["production_contract"]["mode"] == "typed_production_selection"
    assert registry["production_contract"]["whole_set_rendering"] == "production_and_component_sample"

    for item in sets:
        assert item["name"]
        assert item.get("when_to_use")
        assert item.get("not_for")
        guidance = item.get("director_guidance")
        assert isinstance(guidance, dict), item["id"]
        assert guidance.get("visual_sequence"), item["id"]
        assert guidance.get("production_adaptation"), item["id"]
        assert guidance.get("content_constraints"), item["id"]


def test_actual_component_set_registry_summary_keeps_production_contract_and_all_titles():
    registry = _actual_registry()

    summary = director.prompt_component_set_registry(REGISTRY_PATH)

    assert "component_sample" in summary
    assert "set_design" in json.dumps(registry["production_contract"], ensure_ascii=False)
    for item in registry["sets"]:
        line = _line_for(summary, item["id"])
        assert item["name"] in line
        assert item["registration_status"] in line
        assert item["review_status"] in line


def test_actual_material_rich_summary_uses_example_field_names_without_sample_values():
    registry = _actual_registry()
    by_id = {item["id"]: item for item in registry["sets"]}

    summary = director.prompt_component_set_registry(REGISTRY_PATH)

    for set_id in [f"A{index:02d}" for index in range(7, 13)]:
        item = by_id[set_id]
        line = _line_for(summary, set_id)
        for field_name in ["content.title", "content.body", "content.takeaway", "content.items"]:
            assert field_name in line
        if set_id in {"A09", "A10"}:
            for field_name in ["content.metric.label", "content.metric.value", "content.metric.detail"]:
                assert field_name in line

        sample = item.get("component_sample", {})
        for instance_value in [sample.get("asset_id"), sample.get("job_id")]:
            if instance_value:
                assert instance_value not in summary

        example = item.get("content_input", {}).get("example", {})
        for example_value in [example.get("title"), example.get("takeaway")]:
            if example_value:
                assert example_value not in summary
        content_input = item.get("content_input", {})
        metric = example.get("metric") if isinstance(example.get("metric"), dict) else {}
        rules_text = str(content_input.get("rules") or "")
        if metric.get("value") and metric["value"] not in rules_text:
            assert metric["value"] not in summary
