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
)


def test_manifest_contains_all_adapters_and_component_pairs():
    entries = component_manifest()
    assert len(entries) == 160
    assert len(SEMANTIC_COMPONENT_IDS) == 8
    assert len(COMMUNITY_COMPONENT_IDS) == 152
    assert len(PRODUCTION_COMPONENT_IDS) == len(set(PRODUCTION_COMPONENT_IDS))
    assert set(SEMANTIC_COMPONENT_IDS) == {
        "title", "keyword", "evidence", "image_focus",
        "comparison", "data", "steps", "conclusion",
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
    assert len(catalog) == 160
    assert all(entry.production_ready for entry in catalog)
    assert {entry.component_id for entry in catalog} == set(PRODUCTION_COMPONENT_IDS)
    talkcraft = [entry for entry in catalog if entry.library == "Talkcraft"]
    assert len(talkcraft) == 108
    assert all(entry.kind == "preset" and entry.allowed_usages == ["personal", "unspecified"] for entry in talkcraft)


def test_commercial_schema_excludes_only_noncommercial_talkcraft_presets():
    unspecified = set(available_component_ids("unspecified"))
    commercial = set(available_component_ids("commercial"))
    assert unspecified == set(PRODUCTION_COMPONENT_IDS)
    assert len(commercial) == 52
    assert all(not component_id.startswith("Talkcraft-") for component_id in commercial)


def test_manifest_is_wheel_package_data():
    resource = importlib.resources.files("videoagents").joinpath("component-manifest.json")
    payload = json.loads(resource.read_text(encoding="utf-8"))
    assert len(payload["entries"]) == 160
