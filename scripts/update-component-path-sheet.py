"""Update the Feishu component path catalogue from a target payload.

The online workbook is the source of truth for the pre-update baseline. This
script always captures the current workbook with table-get/csv-get before
building operations. Default mode is dry-run; pass --execute to write.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAYLOAD = ROOT / ".runtime" / "component-path-workbook.json"
DEFAULT_METADATA = ROOT / "docs" / "component-paths.json"
TOKEN = "UPpgsQJnLhgA0WtzlU2crIXqnOe"

FIRST_SHEET_NAME = "组件目录"
REPO_SHEET_NAME = "仓库说明"
TALKCRAFT_SHEET_NAME = "video-talkcraft"
INTRO_SHEET_NAME = "使用说明"
SHEET_IDS = {
    FIRST_SHEET_NAME: "aa0d33",
    REPO_SHEET_NAME: "Z1PGqC",
    TALKCRAFT_SHEET_NAME: "9m13RU",
    INTRO_SHEET_NAME: "jdNBUs",
}

PATH_COLUMNS = ["组件名称", "竖版相对文件路径", "横版相对文件路径", "适合表达的内容", "适用场景"]
EXPECTED_SHAPES = {
    FIRST_SHEET_NAME: (5, 152),
    REPO_SHEET_NAME: (9, 6),
    TALKCRAFT_SHEET_NAME: (5, 108),
    INTRO_SHEET_NAME: (2, 12),
}
OBSOLETE_RANGE = "F1:M153"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc


def a1_col(index: int) -> str:
    if index < 1:
        raise ValueError(index)
    value = ""
    while index:
        index, rem = divmod(index - 1, 26)
        value = chr(65 + rem) + value
    return value


def normalize_rel_path(value: str) -> str:
    return value.strip().replace("\\", "/")


def as_path(value: str) -> Path:
    return ROOT / Path(PureWindowsPath(value)) if "\\" in value else ROOT / Path(PurePosixPath(value))


def path_has_oriented_component_folder(rel_path: str, orientation: str) -> bool:
    parts = [p.lower() for p in normalize_rel_path(rel_path).split("/") if p]
    needles = ("portrait", "vertical", "竖") if orientation == "portrait" else ("landscape", "horizontal", "横")
    return any(part.startswith("component") and any(needle in part for needle in needles) for part in parts)


def validate_path_rows(sheet: dict[str, Any], *, expected_rows: int, metadata_by_name: dict[str, Any] | None) -> None:
    if sheet.get("columns") != PATH_COLUMNS:
        raise SystemExit(f"{sheet.get('name')} columns must be {PATH_COLUMNS!r}")
    data = sheet.get("data")
    if not isinstance(data, list) or len(data) != expected_rows:
        raise SystemExit(f"{sheet.get('name')} must contain exactly {expected_rows} data rows")
    seen: set[str] = set()
    for row_number, row in enumerate(data, start=2):
        if not isinstance(row, list) or len(row) != 5:
            raise SystemExit(f"{sheet.get('name')} row {row_number} must have 5 cells")
        name, vertical_path, horizontal_path, description, usage = [str(cell or "").strip() for cell in row]
        if not all([name, vertical_path, horizontal_path, description, usage]):
            raise SystemExit(f"{sheet.get('name')} row {row_number} has empty required cell")
        if name in seen:
            raise SystemExit(f"{sheet.get('name')} duplicate component name: {name}")
        seen.add(name)
        for label, rel_path, orientation in (
            ("vertical", vertical_path, "portrait"),
            ("horizontal", horizontal_path, "landscape"),
        ):
            normalized = normalize_rel_path(rel_path)
            if Path(normalized).is_absolute() or normalized.startswith("../"):
                raise SystemExit(f"{sheet.get('name')} row {row_number} {label} path must be repo-relative: {rel_path}")
            if not path_has_oriented_component_folder(normalized, orientation):
                raise SystemExit(f"{sheet.get('name')} row {row_number} {label} path is not under an oriented component* folder: {rel_path}")
            if not as_path(normalized).exists():
                raise SystemExit(f"{sheet.get('name')} row {row_number} {label} path does not exist: {rel_path}")
        if metadata_by_name is not None:
            entry = metadata_by_name.get(name)
            if not entry:
                raise SystemExit(f"metadata missing component: {name}")
            if normalize_rel_path(vertical_path) != normalize_rel_path(str(entry["verticalPath"])):
                raise SystemExit(f"{sheet.get('name')} row {row_number} vertical path does not match metadata for {name}")
            if normalize_rel_path(horizontal_path) != normalize_rel_path(str(entry["horizontalPath"])):
                raise SystemExit(f"{sheet.get('name')} row {row_number} horizontal path does not match metadata for {name}")


def load_metadata_by_name(metadata_path: Path) -> dict[str, Any]:
    metadata = load_json(metadata_path)
    entries = metadata.get("components") if isinstance(metadata, dict) else metadata
    if not isinstance(entries, list) or len(entries) != EXPECTED_SHAPES[FIRST_SHEET_NAME][1]:
        raise SystemExit(f"{metadata_path} must list exactly {EXPECTED_SHAPES[FIRST_SHEET_NAME][1]} component entries")
    result: dict[str, Any] = {}
    required = ("compositionId", "name", "library", "verticalPath", "horizontalPath", "verticalSourcePath", "horizontalSourcePath")
    for entry in entries:
        if not isinstance(entry, dict):
            raise SystemExit(f"{metadata_path} contains a non-object metadata entry")
        missing = [key for key in required if not str(entry.get(key) or "").strip()]
        if missing:
            raise SystemExit(f"{metadata_path} entry missing required keys {missing}: {entry}")
        name = str(entry["name"]).strip()
        if name in result:
            raise SystemExit(f"duplicate metadata component name: {name}")
        result[name] = entry
    return result


def validate_target_payload(payload: dict[str, Any], metadata_path: Path) -> None:
    sheets = payload.get("sheets")
    if not isinstance(sheets, list) or len(sheets) != 4:
        raise SystemExit("target payload must contain exactly 4 sheets")
    names = [sheet.get("name") for sheet in sheets]
    expected_names = list(EXPECTED_SHAPES)
    if names != expected_names:
        raise SystemExit(f"target sheets must be ordered {expected_names!r}; got {names!r}")

    metadata_by_name = load_metadata_by_name(metadata_path)
    by_name = {sheet["name"]: sheet for sheet in sheets}
    validate_path_rows(by_name[FIRST_SHEET_NAME], expected_rows=152, metadata_by_name=metadata_by_name)
    validate_path_rows(by_name[TALKCRAFT_SHEET_NAME], expected_rows=108, metadata_by_name=None)
    for name in (REPO_SHEET_NAME, INTRO_SHEET_NAME):
        columns, rows = EXPECTED_SHAPES[name]
        sheet = by_name[name]
        if len(sheet.get("columns", [])) != columns or len(sheet.get("data", [])) != rows:
            raise SystemExit(f"{name} must remain {columns} columns x {rows} rows")


def lark_env() -> dict[str, str]:
    return {
        **os.environ,
        "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
        "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
    }


def run_lark(args: list[str], *, stdin: Any | None = None) -> dict[str, Any]:
    encoded = None if stdin is None else json.dumps(stdin, ensure_ascii=False).encode("utf-8")
    process = subprocess.run(
        ["lark-cli.cmd", *args, "--as", "bot", "--json"],
        input=encoded,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=ROOT,
        env=lark_env(),
        check=False,
    )
    stdout = process.stdout.decode("utf-8-sig", errors="replace")
    stderr = process.stderr.decode("utf-8-sig", errors="replace")
    if process.returncode:
        raise RuntimeError(f"lark-cli failed ({process.returncode}): {stderr.strip() or stdout.strip()}")
    reply = json.loads(stdout)
    if not reply.get("ok"):
        raise RuntimeError(f"lark-cli returned ok=false: {json.dumps(reply, ensure_ascii=False)[:1000]}")
    return reply


def table_get() -> dict[str, Any]:
    return run_lark(["sheets", "+table-get", "--spreadsheet-token", TOKEN])


def csv_get(sheet_id: str, cell_range: str) -> dict[str, Any]:
    return run_lark(
        [
            "sheets",
            "+csv-get",
            "--spreadsheet-token",
            TOKEN,
            "--sheet-id",
            sheet_id,
            "--range",
            cell_range,
            "--max-chars",
            "500000",
        ]
    )


def csv_rows(reply: dict[str, Any]) -> list[list[str]]:
    annotated = reply["data"].get("annotated_csv", "")
    plain = re.sub(r"^\[row=\d+\] ", "", annotated, flags=re.MULTILINE)
    if not plain.strip():
        return []
    return list(csv.reader(io.StringIO(plain)))


def expected_range(sheet: dict[str, Any]) -> str:
    return f"A1:{a1_col(len(sheet['columns']))}{len(sheet['data']) + 1}"


def backup_current_workbook(payload: dict[str, Any]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / ".runtime" / "component-path-sheet-baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    current: dict[str, Any] = {
        "capturedAt": timestamp,
        "spreadsheetToken": TOKEN,
        "tableGet": table_get(),
        "sheets": {},
    }
    for sheet in payload["sheets"]:
        cell_range = expected_range(sheet)
        if sheet["name"] == FIRST_SHEET_NAME:
            cell_range = "A1:M153"
        current["sheets"][sheet["name"]] = {
            "sheet_id": SHEET_IDS[sheet["name"]],
            "range": cell_range,
            "readback": csv_get(SHEET_IDS[sheet["name"]], cell_range),
        }
        if sheet["name"] in (FIRST_SHEET_NAME, TALKCRAFT_SHEET_NAME):
            sheet_id = SHEET_IDS[sheet["name"]]
            snapshot = current["sheets"][sheet["name"]]
            snapshot["structure"] = run_lark([
                "sheets", "+sheet-info", "--spreadsheet-token", TOKEN,
                "--sheet-id", sheet_id, "--include", "merges,row_heights,col_widths,frozen",
            ])
            snapshot["styleSample"] = run_lark([
                "sheets", "+cells-get", "--spreadsheet-token", TOKEN,
                "--sheet-id", sheet_id, "--range", "A1:E3",
                "--include", "value,formula,style,data_validation",
            ])
    path = out_dir / f"{timestamp}.json"
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def cells_matrix(values: list[list[Any]]) -> list[list[dict[str, Any]]]:
    return [[{"value": "" if value is None else value} for value in row] for row in values]


def baseline_rows(baseline: dict[str, Any], sheet_name: str) -> list[list[str]]:
    return csv_rows(baseline["sheets"][sheet_name]["readback"])


def assert_repo_sheet_preserved(payload_sheet: dict[str, Any], current_rows: list[list[str]]) -> None:
    expected = [payload_sheet["columns"], *payload_sheet["data"]]
    if current_rows != [[str(cell) if cell is not None else "" for cell in row] for row in expected]:
        raise SystemExit(f"{REPO_SHEET_NAME} differs from target; refusing to edit protected sheet")


def assert_talkcraft_names_stable(payload_sheet: dict[str, Any], current_rows: list[list[str]]) -> None:
    target = [payload_sheet["columns"], *payload_sheet["data"]]
    if len(current_rows) != len(target):
        raise SystemExit(f"{TALKCRAFT_SHEET_NAME} row count changed: live={len(current_rows)} target={len(target)}")
    if current_rows[0][0] != str(target[0][0]):
        raise SystemExit(f"{TALKCRAFT_SHEET_NAME} first column header changed")
    for index, (live, wanted) in enumerate(zip(current_rows[1:], target[1:], strict=True), start=2):
        if live[0] != str(wanted[0]):
            raise SystemExit(f"{TALKCRAFT_SHEET_NAME} row {index} component name changed: {live[0]!r} -> {wanted[0]!r}")


def build_sheet_update(sheet: dict[str, Any]) -> dict[str, Any]:
    values = [sheet["columns"], *sheet["data"]]
    cells = cells_matrix(values)
    if sheet['name'] in (FIRST_SHEET_NAME, TALKCRAFT_SHEET_NAME):
        for index, row in enumerate(cells):
            style = {
                'font_size':11, 'font_weight':'bold' if index == 0 else 'normal',
                'font_color':'#FFFFFF' if index == 0 else '#172033',
                'background_color':'#1E3A5F' if index == 0 else '#EBF1F8' if index % 2 == 0 else '#FFFFFF',
                'horizontal_alignment':'center' if index == 0 else 'left',
                'vertical_alignment':'middle', 'word_wrap':'auto-wrap',
            }
            for cell in row:
                cell['cell_styles'] = style
    return {
        "shortcut": "+cells-set",
        "input": {
            "sheet_id": SHEET_IDS[sheet["name"]],
            "range": expected_range(sheet),
            "cells": cells,
        },
    }


def obsolete_range_has_content(baseline: dict[str, Any]) -> bool:
    rows = baseline_rows(baseline, FIRST_SHEET_NAME)
    for row in rows:
        for cell in row[5:13]:
            if str(cell).strip():
                return True
    return False


def build_operations(payload: dict[str, Any], baseline_path: Path) -> list[dict[str, Any]]:
    baseline = load_json(baseline_path)
    by_name = {sheet["name"]: sheet for sheet in payload["sheets"]}
    assert_repo_sheet_preserved(by_name[REPO_SHEET_NAME], baseline_rows(baseline, REPO_SHEET_NAME))
    assert_talkcraft_names_stable(by_name[TALKCRAFT_SHEET_NAME], baseline_rows(baseline, TALKCRAFT_SHEET_NAME))

    operations: list[dict[str, Any]] = [
        build_sheet_update(by_name[FIRST_SHEET_NAME]),
        build_sheet_update(by_name[TALKCRAFT_SHEET_NAME]),
    ]
    intro_current = baseline_rows(baseline, INTRO_SHEET_NAME)
    intro_target = [[str(cell) if cell is not None else "" for cell in row] for row in [by_name[INTRO_SHEET_NAME]["columns"], *by_name[INTRO_SHEET_NAME]["data"]]]
    if intro_current != intro_target:
        operations.append(build_sheet_update(by_name[INTRO_SHEET_NAME]))
    if obsolete_range_has_content(baseline):
        operations.append(
            {
                "shortcut": "+cells-clear",
                "input": {"sheet_id": SHEET_IDS[FIRST_SHEET_NAME], "range": OBSOLETE_RANGE, "scope": "all"},
            }
        )
    catalogues = [by_name[FIRST_SHEET_NAME], by_name[TALKCRAFT_SHEET_NAME]]
    for sheet in catalogues:
        widths = {}
        for index, heading in enumerate(sheet['columns']):
            values = [heading, *(row[index] for row in sheet['data'])]
            longest = max(sum(2 if ord(char) > 255 else 1 for char in str(value)) for value in values)
            widths[a1_col(index + 1)] = min(400, max(90, longest * 8 + 20))
        operations.extend({"shortcut": "+cols-resize", "input": {
            "sheet_id": SHEET_IDS[sheet['name']], "range":column, "width":width,
        }} for column, width in widths.items())
        operations.extend([
            {"shortcut": "+rows-resize", "input": {"sheet_id": SHEET_IDS[sheet['name']], "range":"1", "height":42}},
            {"shortcut": "+rows-resize", "input": {"sheet_id": SHEET_IDS[sheet['name']], "range":f"2:{len(sheet['data']) + 1}", "type":"auto"}},
            {"shortcut": "+dim-freeze", "input": {"sheet_id": SHEET_IDS[sheet['name']], "dimension":"row", "count":1}},
        ])
    return operations


def execute_batch(operations: list[dict[str, Any]], execute: bool) -> dict[str, Any]:
    command = ["sheets", "+batch-update", "--spreadsheet-token", TOKEN, "--operations", "-"]
    mode = "execute" if execute else "dry-run"
    command.append("--yes" if execute else "--dry-run")
    reply = run_lark(command, stdin=operations)
    out_path = ROOT / ".runtime" / f"component-path-sheet-{mode}.json"
    out_path.write_text(json.dumps(reply, ensure_ascii=False, indent=2), encoding="utf-8")
    return reply


def write_metadata_snapshot(payload: dict[str, Any], execute: bool) -> Path | None:
    if not execute:
        return None
    snapshot = {
        "ok": True,
        "identity": "bot",
        "data": {
            "sheets": [
                {
                    "name": sheet["name"],
                    "sheet_id": SHEET_IDS[sheet["name"]],
                    "columns": len(sheet["columns"]),
                    "data_rows": len(sheet["data"]),
                    "range": expected_range(sheet),
                    "mode": "overwrite",
                    "writes": 1,
                }
                for sheet in payload["sheets"]
            ],
            "spreadsheet": {
                "spreadsheet_token": TOKEN,
                "url": "https://icnpfyu4nynj.feishu.cn/sheets/UPpgsQJnLhgA0WtzlU2crIXqnOe",
                "title": "Remotion组件库与video-talkcraft调研（2026-10-02）",
                "folder_token": "",
            },
        },
    }
    path = ROOT / ".runtime" / "component-workbook-created-current.json"
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--execute", action="store_true", help="write to Feishu; default is dry-run")
    args = parser.parse_args()

    payload = load_json(args.payload)
    validate_target_payload(payload, args.metadata)
    baseline_path = backup_current_workbook(payload)
    operations = build_operations(payload, baseline_path)
    if not (9 <= len(operations) <= 30):
        raise SystemExit(f"unexpected operation count: {len(operations)}")
    operations_path = ROOT / ".runtime" / "component-path-sheet-operations.json"
    operations_path.write_text(json.dumps(operations, ensure_ascii=False, indent=2), encoding="utf-8")
    reply = execute_batch(operations, args.execute)
    metadata_path = write_metadata_snapshot(payload, args.execute)
    print(
        json.dumps(
            {
                "ok": True,
                "mode": "execute" if args.execute else "dry-run",
                "operations": len(operations),
                "baseline": str(baseline_path.relative_to(ROOT)),
                "metadataSnapshot": str(metadata_path.relative_to(ROOT)) if metadata_path else None,
                "larkOk": bool(reply.get("ok")),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
