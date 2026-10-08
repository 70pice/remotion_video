"""File-backed role prompts: loading, rendering and contract wording.

Prompts live as standalone markdown under ``videoagents/prompts`` so they can
be tuned without touching node code. These tests pin the loader behaviour and
spot-check the wording the model contracts depend on; they do not attempt to
judge creative quality.
"""

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

PROMPT_FILES = [
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


def test_legacy_programmer_focused_root_prompt_does_not_return():
    assert not (PROMPTS_DIR.parents[1] / "screenwriter-prompt-v2.md").exists()


def test_new_jobs_default_to_ordinary_people_and_preserve_explicit_audience():
    assert Brief(topic="AI 新闻").audience == "关心 AI 如何影响自己的钱、工作和生活的普通人，无需技术背景"
    assert Brief(topic="AI 编程", audience="专业程序员").audience == "专业程序员"


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
    assert compose("screenwriter", "screenwriter-draft") == (
        load_prompt("screenwriter") + "\n\n" + load_prompt("screenwriter-draft")
    )


def test_render_substitutes_every_placeholder():
    text = render(
        "director",
        component_props='{"title": {}}',
        component_catalog="Snapcn-TextReveal | Snapcn | 固定预设 | 标题 | 开场",
    )
    assert "{{" not in text and "component_props" not in text
    assert '{"title": {}}' in text


def test_render_rejects_missing_and_unknown_variables():
    with pytest.raises(ValueError, match="component_catalog"):
        render("director")
    with pytest.raises(ValueError, match="component_catalog"):
        render("director", component_props="x")
    with pytest.raises(ValueError, match="component_props"):
        render("director", component_catalog="y")
    with pytest.raises(ValueError, match="未使用"):
        render("director", component_props="x", component_catalog="y", unexpected="z")


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
    (screenwriter.PROMPT, ("screenwriter", "screenwriter-draft")),
    (screenwriter.REWRITE_PROMPT, ("screenwriter", "screenwriter-rewrite")),
    (script_reviewer.PROMPT, ("script-reviewer",)),
    (voice.PROMPT, ("voice",)),
    (editing.PROMPT, ("editing",)),
    (reviewers.PROMPT, ("review",)),
], ids=["materials", "narrative", "draft", "rewrite", "script-reviewer", "voice", "editing", "review"])
def test_runtime_prompts_use_only_their_own_role_files(actual, names):
    assert actual == "\n\n".join(load_prompt(name) for name in names)


@pytest.mark.parametrize("usage", ["personal", "commercial", "unspecified"])
def test_director_templates_do_not_receive_shared_instructions(usage):
    import json

    assert director.director_prompt(usage) == render(
        "director",
        component_props=json.dumps(director.COMPONENT_PROPS_EXAMPLES, ensure_ascii=False, separators=(",", ":")),
        component_catalog=director.prompt_component_catalog(usage),
    )
    study_prompt, payload = director.component_study_prompt(usage)
    assert study_prompt == render(
        "component-study",
        component_source_guide=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )


def test_shared_style_file_is_absent():
    assert not (PROMPTS_DIR / "shared-style.md").exists()


def test_director_prompt_injects_props_examples():
    import json

    expected = json.dumps(
        director.COMPONENT_PROPS_EXAMPLES,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert expected in director.PROMPT
    assert all(component_id in director.PROMPT for component_id in COMMUNITY_COMPONENT_IDS)


def test_director_prompt_contains_visual_palette_contract():
    prompt = director.PROMPT
    assert "底色 #0C0F14" in prompt
    assert "薄荷绿 #8CFFB8（识别/赢家/成功/关键数字）" in prompt
    assert "蓝 #5B8CFF（信息/A/官方）" in prompt
    assert "紫 #A78BFA（推断/B）" in prompt
    assert "顶部约 150px、底部约 280px" in prompt
    assert "颜色不单独承载信息" in prompt
    assert "不加 theme、background、CSS、坐标等字段" in prompt


def test_director_prompt_defines_half_open_contiguous_frame_ranges():
    prompt = director.PROMPT

    assert "start_frame（含）、end_frame（不含）为半开区间 [start,end)" in prompt
    assert "shots[i].start_frame == shots[i-1].end_frame" in prompt
    assert "绝不在上一镜 end_frame 上加 1" in prompt
    assert "end_frame==duration_in_frames" in prompt
    assert "[0,140)+[140,279) 合法" in prompt
    assert "[0,140)+[141,279) 非法" in prompt


def test_director_and_editing_prompts_block_flash_shots():
    director_prompt = director.PROMPT
    editing_prompt = editing.PROMPT

    assert "ceil(1.5×fps)" in director_prompt
    assert "30fps 时 ≥45 帧" in director_prompt
    assert "ceil(2.5×fps)" in director_prompt
    assert "30fps 时 ≥75 帧" in director_prompt
    assert "不为转场/组件入场建几十帧闪现镜" in director_prompt
    assert "不让组件一闪即走" in director_prompt

    assert "普通镜头少于 `ceil(1.5*fps)` 帧" in editing_prompt
    assert "时少于 45 帧）就是闪现镜头" in editing_prompt
    assert "`ceil(2.5*fps)` 帧" in editing_prompt
    assert "时少于 75 帧）就是不可读镜头" in editing_prompt
    assert "severity=error、owner=director、blocking=true" in editing_prompt
    assert "最低可读下限不等于统一切镜秒数" in editing_prompt
    assert "cue + 15 + ceil(2.5×fps)" in director_prompt
    assert "30fps 时 cue 后至少留 90 帧" in director_prompt
    assert "至少保留 90 帧" in editing_prompt
    assert "不在结束前十几帧才亮最后一卡" in director_prompt
    assert "最后一张卡" in editing_prompt


def test_director_prompt_forbids_empty_optional_props_text():
    prompt = director.PROMPT

    assert "可选文字字段“有内容才提供”，没有就**省略该键**" in prompt
    assert '不输出 `body:""` 或纯空白' in prompt
    assert "已提供的文字必须非空" in prompt


def test_editing_prompt_allows_verified_image_crop():
    # 图片裁剪已由时间轴验证与渲染器支持，预检不能再按旧白名单误拒绝。
    assert "image_focus.crop{x,y,width,height}" in editing.PROMPT


def test_editing_prompt_describes_focus_cues_and_data_reveal_contract():
    prompt = editing.PROMPT

    assert "evidence/image_focus.focus_cues" in prompt
    assert "1～8 项数组" in prompt
    assert "第一项 frame 必须是 0" in prompt
    assert "严格递增" in prompt
    assert "没有 region 表示全图" in prompt
    assert "放大该已核验区域并压暗其他区域" in prompt
    assert "不与同一 shot 的旧 highlight、crop、" in prompt
    assert "旧 highlight/crop/focal_x/focal_y 在没有 focus_cues" in prompt
    assert "cards data.items 的 label 与 detail 开场可见" in prompt
    assert "reveal_frame 只控制 value" in prompt
    assert "bars/donuts 的 label 开场可见，detail 与数值、图形一起" in prompt


def test_editing_prompt_treats_current_timeline_as_authoritative():
    assert "timeline` 是当前待渲染分镜的唯一现状来源" in editing.PROMPT
    assert "可能只保留当前反馈 note、状态和已应用说明" in editing.PROMPT
    assert "已核验 ROI/" in editing.PROMPT
    assert "focus_cues 坐标依据" in editing.PROMPT
    assert "不得写成剪辑模型已经目视图片像素或看过旧版" in editing.PROMPT
    assert "该数值必须与当前" in editing.PROMPT
    assert "旧值写成现状或据此阻断" in editing.PROMPT


def test_script_prompts_limit_repetition_without_dropping_necessary_evidence_boundaries():
    assert "同一边界只说一次" in screenwriter.PROMPT
    assert "不是本期事实或预设推荐" in screenwriter.PROMPT
    assert "什么任务优先选谁" in screenwriter.PROMPT
    assert "不是文案审查任务，不能返回 ScriptCritique" in screenwriter.REWRITE_PROMPT
    assert "旧稿的通过结论不能沿用" in screenwriter.REWRITE_PROMPT
    assert "同一必要边界只说一次" in screenwriter.REWRITE_PROMPT
    assert "必要事实条件不受字数压制" in screenwriter.PROMPT
    assert "口径或样本被损坏" in script_reviewer.PROMPT
    assert "没有把“稳、平”误判为好稿" in script_reviewer.PROMPT


def test_chart_focus_preserves_context_during_series_comparisons():
    assert "讲图表先建立对象、坐标、单位" in director.PROMPT
    assert "后续沿用同一 region 仅更新 label" in director.PROMPT
    assert "提供 region=放大并压暗周边" in director.PROMPT
    assert "同一实测 region 仅更新 label" in editing.PROMPT
    assert "当前字幕正在解释曲线的变化或比较" in editing.PROMPT
    assert "没有像素核验依据时只提示实际预览" in editing.PROMPT


def test_director_uses_current_audio_after_voice_revision():
    assert "本轮实测音频、字幕时间、总帧数" in director.PROMPT
    assert "旧音频、旧字幕、旧切点、旧反馈快照不写回当前时间轴" in director.PROMPT


def test_director_catalog_retains_developer_presets_with_topic_boundary():
    # 完整目录仍保留开发者预设；角色正文限定其使用主题。
    body = load_prompt("director")
    catalog = director.prompt_component_catalog("unspecified")
    assert "仅在主题确实相关" in body
    assert "Talkcraft-claude-code" in catalog and catalog in director.PROMPT


@pytest.mark.parametrize("label,phrase", [
    ("materials", "难直观感知、又影响判断的数字"),
    ("materials", "不用类比"),
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
    # 开发者/代码界面预设的选择边界必须保留在导演链路（学习结论与分镜规则）。
    for phrase in [
        "终端/代码/光标走读类预设",
        "仅在主题确实相关",
        "普通观众不读代码也能理解",
        "预设内置示例文案/图表/图片不是本期事实证据",
    ]:
        assert phrase in director.PROMPT
    assert "开发者界面边界" in load_prompt("component-study")


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
        ("screenwriter", "每段 source_refs 必须有真实来源"),
        ("screenwriter", "不要单独宣布“我的观点”"),
        ("screenwriter", "结尾判断也要有依据"),
        ("screenwriter", "一个本期受众都能进入的具体任务"),
        ("screenwriter", "成本与上手门槛"),
        ("screenwriter", "来源和 limitations 是写作边界"),
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
        ("director", "steps.items：1–4 个对象"),
        ("director", "必填 title（≤48），可选 body（≤96）"),
        ("director", "data.items：1–4 个对象"),
        ("director", "必填 label（≤48）、value（≤40），可选 detail（≤64）"),
        ("director", "必须齐全 left_title/right_title（≤48）与 left_body/right_body（≤160）"),
        ("director", "eyebrow（≤48）"),
        ("director", "keyword（≤40）"),
        ("director", "call_to_action（≤72）"),
        ("director", "x+width≤1、y+height≤1"),
        ("director", "width/height>0"),
        ("director", "已提供的文字必须非空"),
        ("director", "title≤100 字、body≤240 字、source_label≤160 字"),
        ("director", "仅为调度提示，不是算法或合格线"),
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
