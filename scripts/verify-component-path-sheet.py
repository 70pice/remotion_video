"""Verify the live Feishu component path workbook against the target payload."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
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
    FIRST_SHEET_NAME: (5, 187),
    REPO_SHEET_NAME: (9, 7),
    TALKCRAFT_SHEET_NAME: (5, 108),
    INTRO_SHEET_NAME: (2, 12),
}
OBSOLETE_RANGE = "F1:M188"
EXPECTED_CELLS = 1583


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path}: {exc}") from exc


def a1_col(index: int) -> str:
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
        result[str(entry["name"]).strip()] = entry
    return result


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


def validate_payload(payload: dict[str, Any], metadata_path: Path) -> None:
    sheets = payload.get("sheets")
    if not isinstance(sheets, list) or len(sheets) != 4:
        raise SystemExit("target payload must contain exactly 4 sheets")
    names = [sheet.get("name") for sheet in sheets]
    expected_names = list(EXPECTED_SHAPES)
    if names != expected_names:
        raise SystemExit(f"target sheets must be ordered {expected_names!r}; got {names!r}")
    by_name = {sheet["name"]: sheet for sheet in sheets}
    metadata_by_name = load_metadata_by_name(metadata_path)
    validate_path_rows(by_name[FIRST_SHEET_NAME], expected_rows=187, metadata_by_name=metadata_by_name)
    validate_path_rows(by_name[TALKCRAFT_SHEET_NAME], expected_rows=108, metadata_by_name=None)
    for name, (columns, rows) in EXPECTED_SHAPES.items():
        sheet = by_name[name]
        if len(sheet["columns"]) != columns or len(sheet["data"]) != rows:
            raise SystemExit(f"{name} must be {columns} columns x {rows} rows")


def lark_env() -> dict[str, str]:
    return {
        **os.environ,
        "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
        "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
    }


def run_lark(args: list[str]) -> dict[str, Any]:
    process = subprocess.run(
        ["lark-cli.cmd", *args, "--as", "bot", "--json"],
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


def stringify_matrix(rows: list[list[Any]]) -> list[list[str]]:
    return [["" if cell is None else str(cell) for cell in row] for row in rows]


def verify_values(sheet: dict[str, Any]) -> int:
    expected = stringify_matrix([sheet["columns"], *sheet["data"]])
    def read_window(start: int) -> list[list[str]]:
        end = min(start + 10, len(expected))
        cell_range = f"A{start + 1}:{a1_col(len(sheet['columns']))}{end}"
        reply = csv_get(SHEET_IDS[sheet["name"]], cell_range)
        data = reply['data']
        if data.get('has_more') or data.get('row_indices') != list(range(start + 1, end + 1)):
            raise SystemExit(f"incomplete readback: {sheet['name']} {cell_range}")
        result = csv_rows(reply)
        if len(result) != end - start:
            raise SystemExit(f"missing readback rows: {sheet['name']} {cell_range}")
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:
        actual = [row for window in pool.map(read_window, range(0, len(expected), 10)) for row in window]
    if actual != expected:
        for row_index, (actual_row, expected_row) in enumerate(zip(actual, expected), start=1):
            if actual_row != expected_row:
                raise SystemExit(f"{sheet['name']} row {row_index} mismatch: expected {expected_row!r}, got {actual_row!r}")
        raise SystemExit(f"{sheet['name']} row count mismatch: expected {len(expected)}, got {len(actual)}")
    return len(expected) * len(sheet["columns"])


def verify_obsolete_range_empty() -> int:
    rows = csv_rows(csv_get(SHEET_IDS[FIRST_SHEET_NAME], OBSOLETE_RANGE))
    nonempty = [
        (row_index, col_index, cell)
        for row_index, row in enumerate(rows, start=1)
        for col_index, cell in enumerate(row, start=6)
        if str(cell).strip()
    ]
    if nonempty:
        raise SystemExit(f"{OBSOLETE_RANGE} still has content: {nonempty[:5]}")
    return 153 * 8


def verify_table_get_shape(table_reply: dict[str, Any]) -> dict[str, tuple[int, int]]:
    sheets = table_reply["data"]["sheets"]
    by_name = {sheet["name"]: sheet for sheet in sheets}
    shapes: dict[str, tuple[int, int]] = {}
    for name, (columns, rows) in EXPECTED_SHAPES.items():
        sheet = by_name.get(name)
        if not sheet:
            raise SystemExit(f"table-get missing sheet: {name}")
        # Some CLI table-get responses silently omit rows while reporting the
        # full used range. Prove every row using bounded csv-get windows instead.
        actual_columns = len(sheet["columns"])
        expected_used_range = f"A1:{a1_col(columns)}{rows + 1}"
        if actual_columns != columns or sheet.get('range') != expected_used_range:
            raise SystemExit(f"table-get extent mismatch for {name}: {sheet.get('range')}")
        shapes[name] = (actual_columns, rows)
    return shapes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, default=DEFAULT_PAYLOAD)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    args = parser.parse_args()

    payload = load_json(args.payload)
    validate_payload(payload, args.metadata)
    table_reply = table_get()
    shapes = verify_table_get_shape(table_reply)

    cells_compared = sum(verify_values(sheet) for sheet in payload["sheets"])
    if cells_compared != EXPECTED_CELLS:
        raise SystemExit(f"expected {EXPECTED_CELLS} compared cells, got {cells_compared}")
    obsolete_cells = verify_obsolete_range_empty()

    report = {
        "status": "passed",
        "payload": str(args.payload.relative_to(ROOT)),
        "metadata": str(args.metadata.relative_to(ROOT)),
        "cellsCompared": cells_compared,
        "comparison": "every expected cell read in bounded windows with exact row indices",
        "obsoleteRange": OBSOLETE_RANGE,
        "obsoleteCellsChecked": obsolete_cells,
        "tableGetShapes": shapes,
        "sheets": {sheet["name"]: len(sheet["data"]) for sheet in payload["sheets"]},
        "url": "https://icnpfyu4nynj.feishu.cn/sheets/UPpgsQJnLhgA0WtzlU2crIXqnOe",
    }
    out_path = ROOT / ".runtime" / "component-path-sheet-verification.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
