"""Read CSV, Excel and JSON into text rows. Nothing is type-converted here, so IDs keep leading zeros."""

import csv
import io
import json
from dataclasses import dataclass
from pathlib import PurePath

import pandas as pd

EXTRA_COLUMNS = "__extra__"  # a row with more values than the header has columns


class FileError(ValueError):
    """The whole file is unusable; the message is shown to the user."""


@dataclass
class Sheet:
    name: str | None
    rows: list[tuple[int, dict]]  # (row number in the source file, column -> text or None)


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise FileError("the file is not readable text (expected UTF-8)")


def _parse_csv(content: bytes) -> list[Sheet]:
    text = _decode(content)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect, restkey=EXTRA_COLUMNS)
    try:
        rows = [(reader.line_num, dict(row)) for row in reader]
    except csv.Error as exc:
        raise FileError(f"malformed CSV: {exc}") from None
    return [Sheet(None, rows)]


def _parse_excel(content: bytes) -> list[Sheet]:
    try:
        book = pd.read_excel(io.BytesIO(content), sheet_name=None, dtype=str, keep_default_na=False)
    except Exception as exc:
        raise FileError(f"not a readable Excel workbook: {exc}") from None
    return [Sheet(name, [(i + 2, row) for i, row in enumerate(df.to_dict("records"))]) for name, df in book.items()]


def _flatten(record: dict, prefix: str = "") -> dict:
    out = {}
    for key, value in record.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, f"{name}_"))
        else:
            out[name] = _text(value)
    return out


def _records(items: list, name: str | None) -> Sheet:
    if not all(isinstance(item, dict) for item in items):
        raise FileError("every JSON record must be an object")
    return Sheet(name, [(i + 1, _flatten(item)) for i, item in enumerate(items)])


def _parse_json(content: bytes) -> list[Sheet]:
    try:
        data = json.loads(_decode(content))
    except json.JSONDecodeError as exc:
        raise FileError(f"invalid JSON: {exc}") from None
    if isinstance(data, list):
        return [_records(data, None)]
    if isinstance(data, dict):
        lists = {k: v for k, v in data.items() if isinstance(v, list)}
        if "records" in lists:
            return [_records(lists["records"], None)]
        if lists:
            return [_records(items, key) for key, items in lists.items()]
    raise FileError("expected a JSON array of records, or an object holding one")


PARSERS = {".csv": _parse_csv, ".xlsx": _parse_excel, ".xls": _parse_excel, ".json": _parse_json}


def parse_file(file_name: str, content: bytes) -> list[Sheet]:
    suffix = PurePath(file_name).suffix.lower()
    if suffix not in PARSERS:
        raise FileError(f"unsupported file type '{suffix}'; use CSV, Excel or JSON")
    if not content.strip():
        raise FileError("the file is empty")
    sheets = [s for s in PARSERS[suffix](content) if s.rows]
    if not sheets:
        raise FileError("the file has no data rows")
    return sheets
