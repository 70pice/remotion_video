"""The production manifest exposes every verified community component."""

import importlib.resources
import json

from videoagents.contracts import Shot
from videoagents.tools.catalog import component_catalog
from videoagents.tools.components import (
    COMMUNITY_COMPONENT_IDS,
    PRODUCTION_COMPONENT_IDS,
    SEMANTIC_COMPONENT_IDS,
    available_component_ids,
    component_manifest,
    component_study_payload,
)


def test_manifest_contains_all_adapters_and_component_pairs():
    entries = component_manifest()
    assert len(entries) == 161
    assert len(SEMANTIC_COMPONENT_IDS) == 9
    assert len(COMMUNITY_COMPONENT_IDS) == 152
    assert len(PRODUCTION_COMPONENT_IDS) == len(set(PRODUCTION_COMPONENT_IDS))
    assert set(SEMANTIC_COMPONENT_IDS) == {
        "title", "keyword", "evidence", "image_focus",
        "video", "comparison", "data", "steps", "conclusion",
    }


def test_every_manifest_id_is_accepted_by_the_shot_contract():
    for component_id in PRODUCTION_COMPONENT_IDS:
        shot = Shot(
            shot_id="one", start_frame=0, end_frame=15,
            component_id=component_id, title="测试",
        )
        assert shot.component_id == component_id


def test_catalog_marks_all_entries_production_ready_with_license_context():
    catalog = component_catalog()
    assert len(catalog) == 161
    assert all(entry.production_ready for entry in catalog)
    assert {entry.component_id for entry in catalog} == set(PRODUCTION_COMPONENT_IDS)
    talkcraft = [entry for entry in catalog if entry.library == "Talkcraft"]
    assert len(talkcraft) == 108
    assert all(entry.kind == "preset" and entry.allowed_usages == ["personal", "unspecified"] for entry in talkcraft)


def test_commercial_schema_excludes_only_noncommercial_talkcraft_presets():
    unspecified = set(available_component_ids("unspecified"))
    commercial = set(available_component_ids("commercial"))
    assert unspecified == set(PRODUCTION_COMPONENT_IDS)
    assert len(commercial) == 53
    assert all(not component_id.startswith("Talkcraft-") for component_id in commercial)


def test_manifest_is_wheel_package_data():
    resource = importlib.resources.files("videoagents").joinpath("component-manifest.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == 161


def test_component_study_payload_projects_vertical_usage_and_source_guides():
    payload = component_study_payload("unspecified")
    presets = [entry for entry in payload["components"] if entry["kind"] == "preset"]
    assert len(presets) == 152
    assert payload["source_fingerprint"]
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    assert len(encoded.encode("utf-8")) < 180 * 1024
    assert all(entry["description"] and entry["use_case"] for entry in presets)
    assert "没有逐像素渲染观看全部动画" in " ".join(payload["inspection_limits"])
    talkcraft = next(entry for entry in presets if entry["component_id"] == "Talkcraft-reticle-lock-on")
    assert talkcraft["vertical_source_path"].endswith("reticle-lock-on.tsx")
    summary = talkcraft["source_summary"]
    assert "durationInFrames" in summary["meta_hint"]
    assert "CONFIG" in summary["config_hint"]
    assert "Props" in summary["props_hint"]
