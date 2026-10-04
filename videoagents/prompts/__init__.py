"""Load role prompts from standalone, debuggable markdown files.

Prompts live next to this module as ``<name>.md`` so they can be reviewed and
tuned without reading node code. Nodes keep module-level constants built with
:func:`load_prompt`, which preserves the previous call sites and runtime
contract; only the storage of the text has changed.
"""

import re
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent

# {{name}} placeholders are rendered explicitly; stray {braces} in prose must
# never be fed to str.format, so the template language is intentionally tiny.
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


@cache
def _read(name: str) -> str:
    if not re.fullmatch(r"[a-z0-9_-]+", name) or ".." in name:
        raise ValueError("Prompt 文件名只能包含小写字母、数字、连字符和下划线")
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt 文件不存在：{path}")
    # One trailing newline is trimmed so concatenation controls spacing; all
    # inner blank lines and indentation are kept exactly as written.
    return path.read_text(encoding="utf-8").rstrip("\n")


def load_prompt(name: str) -> str:
    """Return the prompt text for ``name`` (cached, read-only)."""
    return _read(name)


def compose(*names: str) -> str:
    """Join several prompt files with a single blank line between them."""
    return "\n\n".join(load_prompt(name) for name in names)


def render(name: str, **variables: object) -> str:
    """Load ``name`` and substitute every ``{{var}}`` placeholder.

    Every placeholder must receive a value; unknown variables are rejected so
    that a typo cannot leave literal braces in a model instruction.
    """
    text = load_prompt(name)
    used: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in variables:
            raise ValueError(f"Prompt {name} 的占位符 {key} 未提供渲染值")
        used.add(key)
        return str(variables[key])

    rendered = _PLACEHOLDER.sub(replace, text)
    unknown = set(variables) - used
    if unknown:
        raise ValueError(f"Prompt {name} 收到未使用的渲染变量：{', '.join(sorted(unknown))}")
    return rendered
