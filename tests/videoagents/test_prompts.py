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
    "component-study",
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


def test_editing_prompt_allows_verified_image_crop():
    # 图片裁剪已由时间轴验证与渲染器支持，预检不能再按旧白名单误拒绝。
    assert "image_focus.crop{x,y,width,height}" in editing.PROMPT


@pytest.mark.parametrize(
    "label,phrase",
    [
        ("materials", "MaterialResearch"),
        ("materials", "一个所有对象都能参与的共同任务"),
        ("materials", "[证据缺口]"),
        ("materials", "[未完成平台]"),
        ("screenwriter", "每段 source_refs 必须有真实来源"),
        ("screenwriter", "不要单独宣布“我的观点”"),
        ("screenwriter", "结尾的解释与使用边界同样填写支撑它的真实 source_refs"),
        ("screenwriter", "双产品或多产品比较题必须先选一个所有对象都能参与的具体任务"),
        ("screenwriter", "三方及以上比较仍沿用同一共同任务矩阵"),
        ("screenwriter", "购买题"),
        ("screenwriter", "付费增量"),
        ("screenwriter", "现有方案已经够用的人"),
        ("screenwriter", "来源和 limitations 是写作边界，不是旁白内容"),
        ("screenwriter", "前两段禁止从产品定义、产品分类、背景沿革或能力清单起笔"),
        ("screenwriter", "不要把“没有实测”“不能证明”“按……理解”写成固定口播免责声明"),
        ("screenwriter", "第一段直接进入一个正在发生的具体任务"),
        ("screenwriter", "像一个人在讲一件事，不像六张产品介绍卡"),
        ("screenwriter", "悬念不能靠藏住所有答案"),
        ("screenwriter", "不虚构第一人称体验"),
        ("screenwriter", "同一套任务和判断口径"),
        ("screenwriter", "不要把下面的方法写成固定模板"),
        ("script_reviewer", "全稿问题使用空字符串"),
        ("script_reviewer", "script_discussion.rounds[-1].script.segments"),
        ("script_reviewer", "不得使用范围"),
        ("script_reviewer", "新 ID"),
        ("script_reviewer", "事实正确不等于值得看"),
        ("script_reviewer", "模板腔"),
        ("script_reviewer", "最影响成片成立的 2～4 个问题"),
        ("script_reviewer", "不能要求编剧虚构实测"),
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
        ("director", "不是平台算法、合格线或单独拆镜依据"),
        ("voice", "voice_speech_rate"),
        ("voice", "delivery_notes 数组中只放一条"),
        ("voice", "交给 screenwriter"),
        ("editing", "时长本身不能单独决定拆镜"),
        ("editing", "notes 只放非阻断观察"),
        ("reviewers", "购买题是否成对保留付费增量"),
        ("reviewers", "成片仍须由人工完整播放"),
        ("reviewers", "本节点不授予发布资格"),
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
