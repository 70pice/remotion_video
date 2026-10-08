"""Validate the production inputs of configurable community components."""

import math
import re
from urllib.parse import urlparse

from videoagents.tools.components import COMPONENT_BY_ID

BINDINGS = {
    component_id: entry["production_binding"]
    for component_id, entry in COMPONENT_BY_ID.items()
    if "production_binding" in entry
}


def validate_binding_value(value, schema, name="props") -> None:
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{name} 必须是对象")
        properties = schema["properties"]
        if set(value) - set(properties) or set(schema.get("required", [])) - set(value):
            raise ValueError(f"{name} 缺少必填字段或包含未知字段")
        for key, item in value.items():
            validate_binding_value(item, properties[key], f"{name}.{key}")
    elif kind == "array":
        if not isinstance(value, list) or not schema["minItems"] <= len(value) <= schema["maxItems"]:
            raise ValueError(f"{name} 数组长度无效")
        for index, item in enumerate(value):
            validate_binding_value(item, schema["items"], f"{name}[{index}]")
    elif kind == "string":
        if not isinstance(value, str) or not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", 2048):
            raise ValueError(f"{name} 文字类型或长度无效")
        if schema.get("minLength", 0) and not value.strip():
            raise ValueError(f"{name} 不能为空白")
        if any(ord(char) < 32 and char not in "\t\r\n" for char in value):
            raise ValueError(f"{name} 不能含控制字符")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            raise ValueError(f"{name} 格式无效")
    elif kind in {"number", "integer"}:
        if (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
                or (kind == "integer" and int(value) != value)
                or not schema.get("minimum", -math.inf) <= value <= schema.get("maximum", math.inf)):
            raise ValueError(f"{name} 数值无效")
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{name} 必须是布尔值")
    else:
        raise RuntimeError(f"不支持的组件契约类型：{kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{name} 不在允许的选项中")


def validate_component_binding(shot) -> None:
    binding = BINDINGS[shot.component_id]
    if shot.asset_src:
        raise ValueError("参数化社区组件不接受 asset_src")
    validate_binding_value(shot.props, binding["schema"])
    if (binding["chart"] or binding.get("sourced")) and not shot.source_label.strip():
        raise ValueError("真实数字组件必须标注 source_label")
    source_ref = shot.props.get("source_ref")
    if source_ref is not None:
        parsed = urlparse(source_ref)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
            raise ValueError("组件 source_ref 必须是 HTTP/HTTPS URL")
    if shot.component_id == "Rve-PieChart":
        if abs(sum(item["value"] for item in shot.props["segments"]) - 100) > 0.000001:
            raise ValueError("饼图必须是同一整体的百分比，合计100")
    if shot.component_id == "Bits-ChatConversation" and shot.props["semantics"] == "quotation":
        if not source_ref or not shot.source_label.strip():
            raise ValueError("引用聊天必须标注真实 source_ref 和 source_label")
    if "reveal_frame" in shot.props:
        if shot.props["reveal_frame"] > shot.end_frame - shot.start_frame - 15:
            raise ValueError("组件揭示帧超出镜头区间")


def is_bound_chart(shot) -> bool:
    return bool(shot.props and BINDINGS.get(shot.component_id, {}).get("chart"))
