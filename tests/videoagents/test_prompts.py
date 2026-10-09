"""File-backed role prompts: loading, rendering and contract wording.

Prompts live as standalone markdown under ``videoagents/prompts`` so they can
be tuned without touching node code. These tests pin the loader behaviour and
spot-check the wording the model contracts depend on; they do not attempt to
judge creative quality.
"""

import ast
import importlib.resources

import pytest

from videoagents.contracts import Brief
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

REPO_ROOT = PROMPTS_DIR.parents[1]
AGENT_NODE_FILES = [
    REPO_ROOT / "videoagents/nodes/materials.py",
    REPO_ROOT / "videoagents/nodes/screenwriter.py",
    REPO_ROOT / "videoagents/nodes/script_reviewer.py",
    REPO_ROOT / "videoagents/nodes/voice.py",
    REPO_ROOT / "videoagents/nodes/director.py",
    REPO_ROOT / "videoagents/nodes/editing.py",
    REPO_ROOT / "videoagents/nodes/reviewers.py",
]


def _field_tuple(expr: ast.expr, env: dict[str, tuple[str, ...]]) -> tuple[str, ...] | None:
    if isinstance(expr, ast.Name):
        return env.get(expr.id)
    if not isinstance(expr, ast.Tuple):
        return None

    fields: list[str] = []
    for item in expr.elts:
        if isinstance(item, ast.Starred) and isinstance(item.value, ast.Name):
            previous = env.get(item.value.id)
            if previous is None:
                return None
            fields.extend(previous)
        elif isinstance(item, ast.Constant) and isinstance(item.value, str):
            fields.append(item.value)
        else:
            return None
    return tuple(fields)


def _field_env(function: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, tuple[str, ...]]:
    env: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign):
            continue
        value = _field_tuple(node.value, env)
        if value is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                env[target.id] = value
    return env


PROMPT_FILES = [
    "materials",
    "screenwriter",
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


def test_legacy_programmer_focused_root_prompt_does_not_return():
    assert not (PROMPTS_DIR.parents[1] / "screenwriter-prompt-v2.md").exists()


def test_new_jobs_default_to_ordinary_people_and_preserve_explicit_audience():
    assert (
        Brief(topic="AI 新闻").audience
        == "关心 AI 如何影响自己的钱、工作和生活的普通人，无需技术背景"
    )
    assert (
        Brief(topic="AI 编程", audience="专业程序员").audience
        == "专业程序员"
    )


def test_repository_rules_pin_ordinary_people_audience_and_video_isolation():
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    implementation_contract = (
        REPO_ROOT / "docs/videoagents-implementation-contract.md"
    ).read_text(encoding="utf-8")
    metrics = (REPO_ROOT / "docs/videoagents-short-video-metrics.md").read_text(
        encoding="utf-8"
    )
    storytelling = (
        REPO_ROOT / "docs/videoagents-storytelling-standard.md"
    ).read_text(encoding="utf-8")

    assert "面向关心 AI 如何影响自己的钱、工作和生活的普通人" in readme
    assert "普通人与 AI" in agents
    assert "不再以“前20%”筛选观众" in agents
    assert "audience \"关心 AI 如何影响自己的钱、工作和生活的普通人，无需技术背景\"" in (
        implementation_contract
    )
    assert "普通人与 AI" in metrics
    assert "面向关心自身处境的普通人" in storytelling
    for text in (readme, metrics, storytelling):
        assert "愿意了解前沿进展并尝试工具的人" not in text
    assert "每个视频一条独立分支" in agents
    assert "video/<job_id>" in agents
    assert "视频与视频之间不得复用未显式导入的 state、素材、产物或运行目录" in agents


def test_docs_list_agent_final_field_handoff_contract():
    nodes_doc = (REPO_ROOT / "docs/videoagents-nodes.md").read_text(encoding="utf-8")
    context_doc = (REPO_ROOT / "docs/videoagents-context.md").read_text(encoding="utf-8")
    prompt_design = (REPO_ROOT / "docs/videoagents-prompt-design.md").read_text(
        encoding="utf-8"
    )

    assert "模型输入字段总表" in nodes_doc
    for role, fields in [
        ("materials", "`brief`, `assets`, `settings`"),
        ("screenwriter", "`brief`, `research`, `assets`"),
        ("script_reviewer", "`brief`, `script`, `script_discussion`, `research`, `assets`"),
        ("voice", "`brief`, `script`, `settings`"),
        (
            "director",
            "`brief`, `script`, `timeline`, `research`, `assets`, `asset_metadata`, `extras`",
        ),
        ("editing", "`brief`, `script`, `timeline`, `assets`, `asset_metadata`, `action`"),
        ("review", "`brief`, `script`, `timeline`, `assets`, `research`, `alignment`"),
    ]:
        assert f"`{role}`" in nodes_doc
        assert fields in nodes_doc
    assert "`fields` 只能选择最终业务字段" in context_doc
    assert "不会携带中间过程、工具日志、搜索过程或历史聊天消息" in context_doc
    assert "assets、research、alignment" in prompt_design
    assert "成片复核 | brief、script、timeline、research、assets、reviews" not in prompt_design
    assert "compose 在角色 Prompt 前拼接" not in prompt_design
    assert "所有运行时角色经 `compose` 自动继承" not in prompt_design


def test_every_agent_model_call_uses_explicit_final_fields_and_brief():
    runtime_fields = {"messages", "chat_history", "tool_calls", "tool_results",
                      "intermediate_steps", "search_results", "operations"}

    for path in AGENT_NODE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        functions = [
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        seen_invokes: set[int] = set()
        for function in functions:
            env = _field_env(function)
            for node in ast.walk(function):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "invoke":
                    continue
                fields_keyword = next(
                    (keyword for keyword in node.keywords if keyword.arg == "fields"),
                    None,
                )
                assert fields_keyword is not None, f"{path}:{node.lineno} must pass explicit fields"
                fields = _field_tuple(fields_keyword.value, env)
                assert fields is not None, f"{path}:{node.lineno} fields must resolve statically"
                assert "brief" in fields, f"{path}:{node.lineno} must include the current brief"
                leaked = sorted(set(fields) & runtime_fields)
                assert not leaked, (
                    f"{path}:{node.lineno} leaks runtime history into agent input: {leaked}"
                )
                seen_invokes.add(id(node))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == "invoke":
                assert id(node) in seen_invokes, f"{path}:{node.lineno} invoke outside a function"


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
    assert compose("screenwriter", "screenwriter-rewrite") == (
        load_prompt("screenwriter") + "\n\n" + load_prompt("screenwriter-rewrite")
    )


def test_render_substitutes_every_placeholder():
    text = render(
        "director",
        component_props='{"title": {}}',
        component_scene_playbook="先定场景，再选组件",
        component_catalog="Snapcn-TextReveal | Snapcn | 固定预设 | 标题 | 开场",
    )
    assert "{{" not in text and "component_props" not in text
    assert '{"title": {}}' in text


def test_director_prompt_requires_native_slots_for_all_community_presets():
    text = load_prompt("director")
    assert "material_capability=native_slots" in text
    assert "196 个生产组件全部为" in text
    assert "9 个适配器 + 187 个社区预设" in text
    assert "所有社区预设都不能退回纯覆盖层思路" in text
    assert "device、gallery、pip、data、workspace" in text
    assert "material_capability=overlay" not in text


def test_render_rejects_missing_and_unknown_variables():
    with pytest.raises(ValueError, match="component_scene_playbook"):
        render("director")
    with pytest.raises(ValueError, match="component_catalog"):
        render("director", component_props="x", component_scene_playbook="y")
    with pytest.raises(ValueError, match="component_scene_playbook"):
        render("director", component_props="x")
    with pytest.raises(ValueError, match="未使用"):
        render("director", component_props="x", component_scene_playbook="y", component_catalog="z", unexpected="w")


@pytest.mark.parametrize("bad_name", ["", "UPPER", "has space", "a/b", "a.b", "../screenwriter"])
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


@pytest.mark.parametrize("actual,names", [
    (materials.PROMPT, ("materials",)),
    (screenwriter.NARRATIVE_PROMPT, ("screenwriter",)),
    (screenwriter.PROMPT, ("screenwriter",)),
    (screenwriter.REWRITE_PROMPT, ("screenwriter", "screenwriter-rewrite")),
    (script_reviewer.PROMPT, ("script-reviewer",)),
    (voice.PROMPT, ("voice",)),
    (editing.PROMPT, ("editing",)),
    (reviewers.PROMPT, ("review",)),
], ids=["materials", "narrative", "draft", "rewrite", "script-reviewer", "voice", "editing", "review"])
def test_runtime_prompts_use_only_their_own_role_files(actual, names):
    assert actual == "\n\n".join(load_prompt(name) for name in names)


def test_shared_style_file_is_absent_and_not_loaded_by_runtime_nodes():
    assert not (PROMPTS_DIR / "shared-style.md").exists()
    assert "shared-style" not in materials.PROMPT
    assert "shared-style" not in screenwriter.PROMPT
    assert "shared-style" not in script_reviewer.PROMPT


def test_director_prompt_injects_props_examples():
    import json

    expected = json.dumps(
        director.COMPONENT_PROPS_EXAMPLES,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert expected in director.PROMPT
    assert all(component_id in director.PROMPT for component_id in COMMUNITY_COMPONENT_IDS)


def test_component_study_prompt_has_been_folded_into_director_prompt():
    assert not (PROMPTS_DIR / "component-study.md").exists()
    assert "component-study" not in director.PROMPT
    assert "extras.component_study" not in director.PROMPT
    assert "先读组件知识库" in director.PROMPT
    assert "docs/knowledge/remotion-shot-library.md" in director.PROMPT
    assert "再设计 shots" in director.PROMPT


def test_director_prompt_contains_visual_palette_contract():
    prompt = director.PROMPT
    assert "页面底色 `#0C0F14`" in prompt
    assert "薄荷绿 `#8CFFB8` 仅表示" in prompt
    assert "信息、选手 A、官方内容用蓝 `#5B8CFF`" in prompt
    assert "推断、选手 B 用紫" in prompt
    assert "顶部约 150 px、底部约 280 px" in prompt
    assert "颜色不能单独承担信息" in prompt
    assert "不得新增 theme、background、CSS、坐标等字段" in prompt


def test_director_prompt_defines_half_open_contiguous_frame_ranges():
    prompt = director.PROMPT

    assert "[start_frame, end_frame)" in prompt
    assert "shots[i].start_frame == shots[i-1].end_frame" in prompt
    assert "绝不能在上一镜" in prompt
    assert "end_frame == duration_in_frames" in prompt
    assert "[0,140)`、`[140,279)" in prompt
    assert "[0,140)`、`[141,279)" in prompt


def test_director_and_editing_prompts_block_flash_shots():
    director_prompt = director.PROMPT
    editing_prompt = editing.PROMPT

    assert "ceil(1.5*fps)" in director_prompt
    assert "30 fps 时至少 45 帧" in director_prompt
    assert "ceil(2.5*fps)" in director_prompt
    assert "30 fps 时至少 75 帧" in director_prompt
    assert "不得为转场或组件入场单独创建" in director_prompt
    assert "不能让组件只出现一下就切走" in director_prompt

    assert "普通镜头少于 `ceil(1.5*fps)` 帧" in editing_prompt
    assert "时少于 45 帧）就是闪现镜头" in editing_prompt
    assert "`ceil(2.5*fps)` 帧" in editing_prompt
    assert "时少于 75 帧）就是不可读镜头" in editing_prompt
    assert "severity=error、owner=director、blocking=true" in editing_prompt
    assert "最低可读下限不等于统一切镜秒数" in editing_prompt
    assert "cue + 15 + ceil(2.5*fps)" in director_prompt
    assert "30 fps 时 cue 后至少留" in director_prompt
    assert "至少保留 90 帧" in editing_prompt
    assert "最后一张卡" in director_prompt and "最后一张卡" in editing_prompt


def test_director_prompt_forbids_empty_optional_props_text():
    prompt = director.PROMPT

    assert "没有 body 或 detail 时必须直接省略该键" in prompt
    assert '不能输出 `body: ""`、`detail: ""`' in prompt
    assert "“可选”绝不表示可以填写空字符串" in prompt


def test_editing_prompt_allows_verified_image_crop():
    # 图片裁剪已由时间轴验证与渲染器支持，预检不能再按旧白名单误拒绝。
    assert "image_focus.crop{x,y,width,height}" in editing.PROMPT


def test_editing_prompt_treats_current_timeline_as_authoritative():
    assert "timeline` 是当前待渲染分镜的唯一现状来源" in editing.PROMPT
    assert "该数值必须与当前" in editing.PROMPT
    assert "旧值写成现状或据此阻断" in editing.PROMPT


def test_script_prompts_limit_repetition_without_dropping_necessary_evidence_boundaries():
    assert "不是本期事实或预设推荐" in screenwriter.PROMPT
    assert "什么任务优先选谁" in screenwriter.PROMPT
    assert "不是文案审查任务，不能返回 ScriptCritique" in screenwriter.REWRITE_PROMPT
    assert "旧稿的通过结论不能沿用" in screenwriter.REWRITE_PROMPT
    assert "必要事实条件不受字数压制" in screenwriter.PROMPT
    assert "同一边界只说一次" in screenwriter.PROMPT
    assert "APPROVE 空" in script_reviewer.PROMPT
    assert "REVISE 非空" in script_reviewer.PROMPT


RUNTIME_PROMPTS = [
    materials.PROMPT,
    screenwriter.PROMPT,
    screenwriter.REWRITE_PROMPT,
    script_reviewer.PROMPT,
    voice.PROMPT,
    director.PROMPT,
    editing.PROMPT,
    reviewers.PROMPT,
]


@pytest.mark.parametrize("prompt", RUNTIME_PROMPTS, ids=[
    "materials", "screenwriter", "screenwriter-rewrite", "script-reviewer",
    "voice", "director", "editing", "reviewers",
])
def test_runtime_prompts_do_not_reintroduce_old_ai_interest_audience(prompt):
    assert "前20%" not in prompt
    assert "主动关注 AI、愿意探索新能力和新工具的人" not in prompt
    assert "愿意了解前沿进展并尝试工具的人" not in prompt


@pytest.mark.parametrize("prompt", [
    materials.PROMPT,
    screenwriter.PROMPT,
    screenwriter.REWRITE_PROMPT,
    script_reviewer.PROMPT,
    director.PROMPT,
], ids=["materials", "screenwriter", "screenwriter-rewrite", "script-reviewer", "director"])
def test_creative_prompts_target_ordinary_people_unless_brief_overrides(prompt):
    assert "普通人" in prompt
    assert "brief.audience" in prompt or "brief 另有指定才按 brief" in prompt
    assert (
        "不默认观众懂编程" in prompt
        or "不会编程" in prompt
        or "不懂技术" in prompt
        or "默认观众会编程" in prompt
    )


def test_prompt_chain_keeps_developer_scenarios_tied_to_topic():
    # 编程工具也可以是主题；禁止用作者身份把所有选题变成编程教程。
    assert "brief 指定程序员受众时按 brief" in screenwriter.PROMPT
    assert "不虚构" in screenwriter.PROMPT and "内部消息" in screenwriter.PROMPT
    assert "本期主题确实相关" in director.PROMPT
    assert "示例文案、图表或图片" in director.PROMPT
    assert "不能被当作本视频的" in director.PROMPT
    assert "事实证据" in director.PROMPT


def test_director_catalog_retains_developer_presets_with_topic_boundary():
    # 导演 Prompt 末尾的完整组件清单必然列出 Talkcraft-claude-code 等预设
    # ID；正文继续要求主题相关，不能当作通用 AI 氛围。
    body, _, catalog = director.PROMPT.partition("## 本任务允许的完整组件清单")
    assert "本期主题确实相关" in body
    assert "Talkcraft-claude-code" in catalog


@pytest.mark.parametrize("label,phrase", [
    ("materials", "难直观感知、又影响判断的数字"),
    ("materials", "不用类比"),
    ("screenwriter", "数字可口语化"),
    ("screenwriter", "不能损坏统计口径"),
    ("script_reviewer", "难懂数字裸抛"),
    ("reviewers", "被强行类比"),
])
def test_life_scale_only_required_for_hard_numbers(label, phrase):
    # 生活尺度只用于难懂且影响判断的数字；日期、价格、次数等直观数字不
    # 强行类比，避免模板化和编造参照。
    prompts = {
        "materials": materials.PROMPT,
        "screenwriter": screenwriter.PROMPT,
        "script_reviewer": script_reviewer.PROMPT,
        "reviewers": reviewers.PROMPT,
    }
    assert phrase in prompts[label]


def test_director_chain_keeps_developer_preset_boundary():
    # 开发者/代码界面预设的选择边界必须保留在导演主 Prompt。
    for phrase in [
        "终端、代码、光标走读类开发者预设",
        "本期主题确实相关",
        "普通观众不用读代码也能理解",
        "能当本期事实证据",
        "开发者界面边界",
    ]:
        assert phrase in director.PROMPT


@pytest.mark.parametrize(
    "label,phrase",
    [
        ("materials", "MaterialResearch"),
        ("materials", "所有对象都能做的**共同任务**"),
        ("materials", "[证据缺口]"),
        ("materials", "[未完成平台]"),
        ("materials", "白话怎么说"),
        ("materials", "生活尺度"),
        ("materials", "command_execution"),
        ("materials", "shell 落盘（不用补丁工具）"),
        ("materials", "PNG、JPEG、WebP"),
        ("materials", "SVG/HTML/PDF/GIF/AVIF 不能作为"),
        ("screenwriter", "每段 `source_refs` 必填真实来源 URL"),
        ("screenwriter", "结尾判断也要有依据"),
        ("screenwriter", "一个本期受众都能进入的具体任务"),
        ("screenwriter", "成本与上手门槛"),
        ("screenwriter", "不从产品定义、行业背景、功能清单起笔"),
        ("screenwriter", "不虚构第一人称经历"),
        ("screenwriter", "`creative_direction` 本期方向"),
        ("screenwriter", "research.sources"),
        ("screenwriter", "title_hook"),
        ("screenwriter", "opening_visual"),
        ("screenwriter", "final_answer"),
        ("screenwriter", "先用动作或结果解释"),
        ("script_reviewer", "全稿问题用空字符串"),
        ("script_reviewer", "script_discussion.rounds[-1].script"),
        ("script_reviewer", "不用范围、组合 ID 或新 ID"),
        ("script_reviewer", "新 ID"),
        ("script_reviewer", "观众会不会看完、看不看得懂、信不信、有没有收获"),
        ("script_reviewer", "模板腔"),
        ("script_reviewer", "issues **只放 blocker，2–4 个**"),
        ("script_reviewer", "禁止要求编剧编造"),
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
