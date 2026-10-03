import json
from pathlib import Path

from videoagents.contracts import ComponentEntry
from videoagents.default_config import PROJECT_ROOT

PRODUCTION = [
    ("title", "冲击标题", "主题与开场钩子", "开头与章节"),
    ("keyword", "关键词", "突出旁白重音", "短观点和关键词"),
    ("evidence", "证据截图", "真实截图和来源", "事实证据与原文高亮"),
    ("image_focus", "图片聚焦", "真实图片慢推近", "现场与概念素材"),
    ("comparison", "前后对比", "两个观点或状态并列", "有来源的对比"),
    ("data", "数据卡", "展示已核验数字", "有来源的 1 到 4 个指标"),
    ("steps", "步骤时间线", "顺序呈现过程", "1 到 4 个步骤"),
    ("conclusion", "结论卡", "总结与行动提示", "片尾与段落收束"),
]


def component_catalog(root: Path = PROJECT_ROOT) -> list[ComponentEntry]:
    entries = [ComponentEntry(component_id=component_id, name=name, description=description,
                              use_case=use_case, orientation="both", production_ready=True, min_frames=15,
                              license_note="本项目新增的参数化画面；所用图片/字体须另行核验")
               for component_id, name, description, use_case in PRODUCTION]
    paths = root / "docs" / "component-paths.json"
    guide = root / "docs" / "component-use-guide.json"
    if paths.exists():
        metadata = json.loads(paths.read_text(encoding="utf-8"))
        guidance = {item["compositionId"]: item for item in json.loads(guide.read_text(encoding="utf-8")).get("components", [])} if guide.exists() else {}
        for item in metadata.get("components", []):
            use = guidance.get(item["compositionId"], {})
            entries.append(ComponentEntry(component_id=item["compositionId"], name=item["name"],
                                          description=use.get("description", "现有演示组件"), use_case=use.get("useCase", "仅供选型参考"),
                                          orientation="both", production_ready=False, min_frames=15,
                                          license_note="Talkcraft 仅个人非商业用途；其他组件参见 licenses" if item.get("library") == "Talkcraft" else "演示组件，生产参数和许可待逐项适配"))
    return entries
