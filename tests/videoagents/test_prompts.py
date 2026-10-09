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


def test_legacy_programmer_focused_root_prompt_does_not_return():
    assert not (PROMPTS_DIR.parents[1] / "screenwriter-prompt-v2.md").exists()


def test_new_jobs_default_to_ai_interested_audience_and_preserve_explicit_audience():
    assert (
        Brief(topic="AI 新闻").audience
        == "对 AI 感兴趣、愿意了解前沿进展并尝试工具的人"
    )
    assert (
        Brief(topic="AI 新闻", audience="没有技术背景的普通大众").audience
        == "没有技术背景的普通大众"
    )


def test_repository_rules_pin_ai_interested_audience_and_video_isolation():
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

    assert "面向对 AI 感兴趣、愿意了解前沿进展并尝试工具的人" in readme
    assert "普通大众的 AI 科普" not in readme
    assert "audience \"对 AI 感兴趣、愿意了解前沿进展并尝试工具的人\"" in (
        implementation_contract
    )
    assert "面向对 AI 感兴趣、愿意了解前沿进展并尝试工具的人" in metrics
    assert "面向对 AI 感兴趣、愿意了解前沿进展并尝试工具的人" in storytelling
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
    assert compose("shared-style", "materials") == (
        load_prompt("shared-style") + "\n\n" + load_prompt("materials")
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
    with pytest.raises(ValueError, match="component_props"):
        render("director")
    with pytest.raises(ValueError, match="component_catalog"):
        render("director", component_props="x", component_scene_playbook="y")
    with pytest.raises(ValueError, match="component_scene_playbook"):
        render("director", component_props="x")
    with pytest.raises(ValueError, match="未使用"):
        render("director", component_props="x", component_scene_playbook="y", component_catalog="z", unexpected="w")


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
    assert "合计不超过 10%" in screenwriter.PROMPT
    assert "不是本期事实或预设推荐" in screenwriter.PROMPT
    assert "什么任务优先选谁" in screenwriter.PROMPT
    assert "不是文案审查任务，不能返回 ScriptCritique" in screenwriter.REWRITE_PROMPT
    assert "旧稿的通过结论不能沿用" in screenwriter.REWRITE_PROMPT
    assert "同一必要边界只说一次" in screenwriter.REWRITE_PROMPT
    assert "不受这个预算压制" in screenwriter.PROMPT
    assert "不能仅因占比就逼编剧删除" in script_reviewer.PROMPT
    assert "不能因为稿件“很谨慎”就 APPROVE" in script_reviewer.PROMPT


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
def test_every_runtime_prompt_inherits_ai_interested_audience(prompt):
    # 主动关注 AI 不等于会编程；具体深度来自本期 brief，而非作者身份。
    assert "主动关注 AI、愿意探索新能力和新工具的人" in prompt
    assert "不预设他们会编程" in prompt
    assert "编辑取向" in prompt
    assert "brief.audience" in prompt


@pytest.mark.parametrize("prompt", [
    screenwriter.PROMPT,
    screenwriter.REWRITE_PROMPT,
    script_reviewer.PROMPT,
    voice.PROMPT,
    editing.PROMPT,
    reviewers.PROMPT,
], ids=["screenwriter", "screenwriter-rewrite", "script-reviewer", "voice", "editing", "reviewers"])
def test_noncatalog_prompts_keep_developer_scenarios_tied_to_topic(prompt):
    # 编程工具也可以是主题；禁止用作者身份把所有选题变成编程教程。
    assert "博主是程序员不等于观众是程序员" in prompt
    assert "本期主题确实相关" in prompt
    assert "预设内置的演示代码" in prompt


def test_director_catalog_retains_developer_presets_with_topic_boundary():
    # 导演 Prompt 末尾的完整组件清单必然列出 Talkcraft-claude-code 等预设
    # ID；正文继续要求主题相关，不能当作通用 AI 氛围。
    body, _, catalog = director.PROMPT.partition("## 本任务允许的完整组件清单")
    assert "本期主题确实相关" in body
    assert "Talkcraft-claude-code" in catalog


@pytest.mark.parametrize("label,phrase", [
    ("materials", "难以直观理解、且影响判断的数字"),
    ("materials", "不用类比"),
    ("screenwriter", "难以直观理解、且会影响判断的数字"),
    ("screenwriter", "不强行类比"),
    ("script_reviewer", "直观数字不要求类比"),
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


def test_shared_style_carries_softened_number_rule():
    style = load_prompt("shared-style")
    assert "不强行类比" in style
    assert "难以直观理解、且会影响判断的数字" in style


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
        ("materials", "一个所有对象都能参与的共同任务"),
        ("materials", "[证据缺口]"),
        ("materials", "[未完成平台]"),
        ("materials", "白话怎么说"),
        ("materials", "生活尺度"),
        ("materials", "command_execution"),
        ("materials", "不能把一次补丁工具失败误报为整个工作目录不可写"),
        ("materials", "PNG、JPEG 或 WebP"),
        ("materials", "SVG、HTML、PDF、GIF、AVIF 不能作为"),
        ("screenwriter", "每段 source_refs 必须有真实来源"),
        ("screenwriter", "不要单独宣布“我的观点”"),
        ("screenwriter", "结尾的判断也要有依据"),
        ("screenwriter", "一个本期受众都能进入的具体任务"),
        ("screenwriter", "成本与上手门槛"),
        ("screenwriter", "来源和 limitations 是写作边界"),
        ("screenwriter", "不要从产品定义、行业背景、能力清单起笔"),
        ("screenwriter", "不假装第一人称经历"),
        ("screenwriter", "brief.creative_direction"),
        ("screenwriter", "research.sources"),
        ("screenwriter", "title_hook"),
        ("screenwriter", "opening_visual"),
        ("screenwriter", "final_answer"),
        ("screenwriter", "先用动作或结果解释"),
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
