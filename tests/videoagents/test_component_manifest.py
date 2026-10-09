"""The production manifest exposes every verified community component."""

import importlib.resources
import json

from videoagents.contracts import Shot
from videoagents.default_config import PROJECT_ROOT
from videoagents.tools.catalog import component_catalog
from videoagents.tools.components import (
    COMMUNITY_COMPONENT_IDS,
    PRODUCTION_COMPONENT_IDS,
    SEMANTIC_COMPONENT_IDS,
    available_component_ids,
    component_manifest,
    component_scene_playbook,
    component_study_payload,
    prompt_component_catalog,
    prompt_scene_playbook,
)

EXPECTED_COMMUNITY_PRESETS = 187
EXPECTED_TOTAL_COMPONENTS = 196
NEW_CURATED_COMPONENT_IDS = {
    "RemotionUI-SocialClip",
    "RemotionUI-KanbanMove",
    "Rve-GalleryGrid",
    "Rve-PictureInPicture",
    "RenderComp-PixelCandlestickOhlc",
    "RenderComp-SocialReel",
}
EXPECTED_NATIVE_PRESETS = EXPECTED_COMMUNITY_PRESETS


def test_manifest_contains_all_adapters_and_component_pairs():
    entries = component_manifest()
    assert len(entries) == EXPECTED_TOTAL_COMPONENTS
    assert len(SEMANTIC_COMPONENT_IDS) == 9
    assert len(COMMUNITY_COMPONENT_IDS) == EXPECTED_COMMUNITY_PRESETS
    assert len(PRODUCTION_COMPONENT_IDS) == len(set(PRODUCTION_COMPONENT_IDS))
    assert NEW_CURATED_COMPONENT_IDS <= set(COMMUNITY_COMPONENT_IDS)
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
    assert len(catalog) == EXPECTED_TOTAL_COMPONENTS
    assert all(entry.production_ready for entry in catalog)
    assert {entry.component_id for entry in catalog} == set(PRODUCTION_COMPONENT_IDS)
    assert {entry.material_capability for entry in catalog} == {"native_slots"}
    talkcraft = [entry for entry in catalog if entry.library == "Talkcraft"]
    assert len(talkcraft) == 108
    assert all(entry.kind == "preset" and entry.allowed_usages == ["personal", "unspecified"] for entry in talkcraft)
    assert all(entry.props_mode == "material_slots" for entry in catalog if entry.kind == "preset")
    assert all(entry.material_capability == "native_slots" for entry in catalog if entry.kind == "adapter")
    native_presets = [entry for entry in catalog if entry.kind == "preset" and entry.material_capability == "native_slots"]
    assert len(native_presets) == EXPECTED_NATIVE_PRESETS
    assert NEW_CURATED_COMPONENT_IDS <= {entry.component_id for entry in native_presets}
    assert {entry.component_id for entry in native_presets} == set(COMMUNITY_COMPONENT_IDS)


def test_director_catalog_exposes_material_capability_tiers():
    entries = component_manifest()
    assert all(entry.get("material_capability") in {"native_slots", "overlay"} for entry in entries)
    assert all(entry["material_capability"] == "native_slots" for entry in entries if entry["kind"] == "adapter")
    native_presets = [entry for entry in entries if entry["kind"] == "preset" and entry["material_capability"] == "native_slots"]
    overlay_presets = [entry for entry in entries if entry["kind"] == "preset" and entry["material_capability"] == "overlay"]
    assert len(native_presets) == EXPECTED_NATIVE_PRESETS
    assert len(overlay_presets) == 0

    payload = component_study_payload("unspecified")
    assert {entry["material_capability"] for entry in payload["components"]} == {"native_slots"}

    prompt_catalog = prompt_component_catalog("unspecified")
    assert "title | VideoAgents | 参数化 | native_slots |" in prompt_catalog
    assert "RenderComp-ProductSpotlight | RenderComp | 固定预设 | native_slots |" in prompt_catalog
    assert "Snapcn-TextReveal | Snapcn | 固定预设 | native_slots |" in prompt_catalog


def test_commercial_schema_excludes_only_noncommercial_talkcraft_presets():
    unspecified = set(available_component_ids("unspecified"))
    commercial = set(available_component_ids("commercial"))
    assert unspecified == set(PRODUCTION_COMPONENT_IDS)
    assert len(commercial) == 88
    assert all(not component_id.startswith("Talkcraft-") for component_id in commercial)


def test_manifest_is_wheel_package_data():
    resource = importlib.resources.files("videoagents").joinpath("component-manifest.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == EXPECTED_TOTAL_COMPONENTS


def test_component_study_payload_projects_vertical_usage_and_source_guides():
    payload = component_study_payload("unspecified")
    presets = [entry for entry in payload["components"] if entry["kind"] == "preset"]
    assert len(presets) == EXPECTED_COMMUNITY_PRESETS
    rules = " ".join(payload["selection_rules"])
    assert "9 个参数化适配器和 187 个社区预设" in rules
    assert "35 个 CuratedScene 社区预设" not in rules
    assert "overlay" not in rules
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


def test_component_study_payload_exposes_director_scene_playbooks():
    payload = component_study_payload("unspecified")
    allowed = set(payload["allowed_component_ids"])
    playbooks = payload["scene_playbooks"]
    scene_ids = {item["scene_id"] for item in playbooks}

    assert {"opening_hook", "ai_coding_workflow", "product_demo", "data_claim"} <= scene_ids
    for playbook in playbooks:
        assert playbook["scene"]
        assert playbook["intent"]
        assert playbook["composition"]
        assert playbook["avoid"]
        assert 2 <= len(playbook["shot_flow"]) <= 5
        for step in playbook["shot_flow"]:
            assert step["slot"]
            assert step["purpose"]
            assert step["components"]
            assert set(step["components"]) <= allowed

    coding = next(item for item in playbooks if item["scene_id"] == "ai_coding_workflow")
    flattened = {component for step in coding["shot_flow"] for component in step["components"]}
    assert {"Snapcn-PromptSend", "Snapcn-AgentSteps", "Snapcn-TerminalSimulator"} <= flattened

    commercial_components = {
        component
        for playbook in component_scene_playbook("commercial")
        for step in playbook["shot_flow"]
        for component in step["components"]
    }
    assert all(not component.startswith("Talkcraft-") for component in commercial_components)


def test_prompt_scene_playbook_is_compact_and_actionable():
    text = prompt_scene_playbook("unspecified")
    assert "先定场景，再选组件" in text
    assert "AI Coding / Agent 工作流" in text
    assert "组合节奏" in text
    assert "Snapcn-AgentSteps" in text
    assert "Talkcraft-terminal-typing-log" in text
    assert len(text.encode("utf-8")) < 24 * 1024


def test_component_knowledge_doc_lists_every_production_component_with_scene_and_effect():
    text = (PROJECT_ROOT / "docs" / "knowledge" / "remotion-shot-library.md").read_text(encoding="utf-8")
    assert "196 个生产组件" in text
    assert "适用场景" in text
    assert "画面效果" in text
    assert "## 场景组件组合 Playbook" in text
    assert "先定场景，再选组件" in text
    assert "AI Coding / Agent 工作流" in text
    for component_id in PRODUCTION_COMPONENT_IDS:
        assert f"| `{component_id}` |" in text
