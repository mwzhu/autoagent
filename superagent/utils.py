"""Utility helpers."""

from __future__ import annotations

import difflib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: object) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)


def read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def snapshot_tree(root: Path) -> Dict[str, str]:
    snapshot = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(root))] = path.read_bytes().decode("utf-8", errors="surrogateescape")
    return snapshot


def diff_snapshots(before: Dict[str, str], after: Dict[str, str]) -> str:
    before_keys = set(before.keys())
    after_keys = set(after.keys())
    lines = []
    for relative_path in sorted(before_keys | after_keys):
        old = before.get(relative_path, "")
        new = after.get(relative_path, "")
        if old == new:
            continue
        diff = difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="a/" + relative_path,
            tofile="b/" + relative_path,
        )
        lines.extend(diff)
    return "".join(lines)


def changed_files(before: Dict[str, str], after: Dict[str, str]) -> Dict[str, str]:
    changed: Dict[str, str] = {}
    for relative_path in sorted(set(before) | set(after)):
        if before.get(relative_path) == after.get(relative_path):
            continue
        changed[relative_path] = after.get(relative_path, "")
    return changed


def relative_file_list(root: Path) -> Dict[str, int]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(root))] = os.path.getsize(path)
    return files
