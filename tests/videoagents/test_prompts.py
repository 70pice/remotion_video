"""File-backed role prompts: loading, rendering and contract wording.

Prompts live as standalone markdown under ``videoagents/prompts`` so they can
be tuned without touching node code. These tests pin the loader behaviour and
spot-check the wording the model contracts depend on; they do not attempt to
judge creative quality.
"""

import importlib.resources

import pytest

from videoagents.nodes import (
    director,
    editing,
    materials,
    reviewers,
    screenwriter,
    script_reviewer,
    voice,
)
from videoagents.prompts import PROMPTS_DIR, compose, load_prompt, render
from videoagents.tools.components import COMMUNITY_COMPONENT_IDS

PROMPT_FILES = [
    "shared-style",
    "materials",
    "screenwriter",
    "screenwriter-draft",
    "screenwriter-rewrite",
    "script-reviewer",
    "voice",
    "director",
    "editing",
    "review",
]


@pytest.mark.parametrize("name", PROMPT_FILES)
def test_every_prompt_file_loads_non_empty(name):
    text = load_prompt(name)
    assert text.strip()
    # Files on disk and loader output must agree; caching must not mutate text.
    assert text == (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").rstrip("\n")


def test_prompt_dir_has_no_orphan_markdown():
    on_disk = sorted(path.stem for path in PROMPTS_DIR.glob("*.md"))
    assert on_disk == sorted(PROMPT_FILES)


def test_markdown_ships_as_package_data():
    # importlib.resources only sees the markdown after a wheel install when the
    # files are included as package data, so this guards the wheel contents.
    bundled = {
        path.name
        for path in importlib.resources.files("videoagents.prompts").iterdir()
        if path.suffix == ".md"
    }
    assert bundled == {f"{name}.md" for name in PROMPT_FILES}


def test_compose_joins_with_single_blank_line():
    assert compose("shared-style", "materials") == load_prompt("shared-style") + "\n\n" + load_prompt("materials")


def test_render_substitutes_every_placeholder():
    text = render(
        "director",
        component_props='{"title": {}}',
        component_catalog="Snapcn-TextReveal | Snapcn | 固定预设 | 标题 | 开场",
    )
    assert "{{" not in text and "component_props" not in text
    assert '{"title": {}}' in text


def test_render_rejects_missing_and_unknown_variables():
    with pytest.raises(ValueError, match="component_props"):
        render("director")
    with pytest.raises(ValueError, match="component_catalog"):
        render("director", component_props="x")
    with pytest.raises(ValueError, match="未使用"):
        render("director", component_props="x", component_catalog="y", unexpected="z")


@pytest.mark.parametrize("bad_name", ["", "UPPER", "has space", "a/b", "a.b", "../shared-style"])
def test_loader_rejects_unsafe_names(bad_name):
    with pytest.raises(ValueError):
        load_prompt(bad_name)


def test_loader_raises_for_missing_file():
    with pytest.raises(FileNotFoundError):
        load_prompt("does-not-exist")


def test_nodes_compose_prompts_without_unrendered_placeholders():
    node_prompts = {
        "materials": materials.PROMPT,
        "screenwriter": screenwriter.PROMPT,
        "rewrite": screenwriter.REWRITE_PROMPT,
        "script_reviewer": script_reviewer.PROMPT,
        "voice": voice.PROMPT,
        "director": director.PROMPT,
        "editing": editing.PROMPT,
        "reviewers": reviewers.PROMPT,
    }
    for label, prompt in node_prompts.items():
        assert prompt.strip(), label
        assert "{{" not in prompt, label
    assert screenwriter.NARRATIVE_PROMPT in screenwriter.PROMPT
    assert screenwriter.NARRATIVE_PROMPT in screenwriter.REWRITE_PROMPT


def test_director_prompt_injects_props_examples():
    import json

    expected = json.dumps(
        director.COMPONENT_PROPS_EXAMPLES,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert expected in director.PROMPT
    assert all(component_id in director.PROMPT for component_id in COMMUNITY_COMPONENT_IDS)


@pytest.mark.parametrize(
    "label,phrase",
    [
        ("materials", "MaterialResearch"),
        ("screenwriter", "每段 source_refs 必须有真实来源"),
        ("screenwriter", "narration 必须以“观点：”或“个人感受：”开头"),
        ("screenwriter", "不能只写“我建议”"),
        ("script_reviewer", "全稿问题使用空字符串"),
        ("script_reviewer", "script_discussion.rounds[-1].script.segments"),
        ("script_reviewer", "不得使用范围"),
        ("script_reviewer", "新 ID"),
        ("director", "research.visuals"),
        ("director", "artifact_url"),
        ("director", "asset_src=null"),
        ("director", "字符串数组"),
        ("director", "steps.items 必须是 1 到 4 个对象"),
        ("director", "必填 title（最多48字），可选 body（最多96字）"),
        ("director", "data.items 必须是 1 到 4 个对象"),
        ("director", "必填 label（最多48字）和 value（最多40字），可选 detail（最多64字）"),
        ("director", "left_title/right_title（最多48字）及 left_body/right_body（最多160字）四项"),
        ("director", "eyebrow（最多48字）"),
        ("director", "keyword（最多40字）"),
        ("director", "call_to_action（最多72字）"),
        ("director", "x + width <= 1 且 y + height <= 1"),
        ("director", "width/height 必须大于0"),
        ("director", "所有文字字段必须非空"),
        ("director", "title 最多100字、body 最多240字、source_label 最多160字"),
        ("voice", "voice_speech_rate"),
    ],
)
def test_contract_wording_survived_prompt_migration(label, phrase):
    prompts = {
        "materials": materials.PROMPT,
        "screenwriter": screenwriter.PROMPT,
        "rewrite": screenwriter.REWRITE_PROMPT,
        "script_reviewer": script_reviewer.PROMPT,
        "voice": voice.PROMPT,
        "director": director.PROMPT,
        "editing": editing.PROMPT,
        "reviewers": reviewers.PROMPT,
    }
    assert phrase in prompts[label]
