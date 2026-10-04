"""可用检索技能清单；安装不等于平台已登录或服务 Key 已配置。"""

import os
from pathlib import Path

SKILLS = {
    "agent-reach": "互联网、社交平台、视频、RSS 的检索与读取路由",
    "playwright": "公开页面交互、资料读取和网页截图",
    "screenshot": "截图操作指南；浏览器画面优先使用 Playwright",
    "transcribe": "本地音视频转写；需要配置其语音转写服务",
}


def research_skill_catalog() -> list[dict]:
    """只返回技能名与指南位置，不扫描凭据或执行技能脚本。"""
    home = Path.home()
    roots = [Path(os.getenv("CODEX_HOME", str(home / ".codex"))) / "skills", home / ".agents" / "skills"]
    result = []
    for name, detail in SKILLS.items():
        path = next((root / name / "SKILL.md" for root in roots if (root / name / "SKILL.md").is_file()), None)
        result.append({"name": name, "path": str(path) if path else "", "installed": path is not None, "detail": detail})
    return result
