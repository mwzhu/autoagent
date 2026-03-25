"""Utility helpers."""

from __future__ import annotations

import difflib
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Set

from superagent.models import CommandRecord


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


def clear_directory(path: Path, preserve_names: Iterable[str] | None = None) -> None:
    preserve = set(preserve_names or [])
    ensure_dir(path)
    for child in path.iterdir():
        if child.name in preserve:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, copy_function=shutil.copy2)


def copytree_contents(src: Path, dst: Path) -> None:
    ensure_dir(dst)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir():
            shutil.copytree(child, target, copy_function=shutil.copy2)
        else:
            shutil.copy2(child, target)


def replace_tree_contents(src: Path, dst: Path, preserve_names: Iterable[str] | None = None) -> None:
    clear_directory(dst, preserve_names=preserve_names)
    copytree_contents(src, dst)


def snapshot_tree(root: Path, ignore_roots: Iterable[str] | None = None) -> Dict[str, str]:
    ignore = set(ignore_roots or [])
    snapshot: Dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] in ignore:
            continue
        snapshot[relative.as_posix()] = path.read_bytes().decode("utf-8", errors="surrogateescape")
    return snapshot


def sync_snapshot(snapshot: Dict[str, str], destination: Path, preserve_paths: Iterable[str] | None = None) -> None:
    preserve = set(preserve_paths or [])
    existing = snapshot_tree(destination)
    for relative_path in sorted(existing):
        if relative_path in snapshot or relative_path in preserve:
            continue
        path = destination / relative_path
        if path.exists():
            path.unlink()
    for relative_path, content in snapshot.items():
        target = destination / relative_path
        ensure_dir(target.parent)
        target.write_bytes(content.encode("utf-8", errors="surrogateescape"))


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


def hash_snapshot(snapshot: Dict[str, str]) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8", errors="surrogateescape")
    ).hexdigest()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="surrogateescape")).hexdigest()


def relative_file_list(root: Path) -> Dict[str, int]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path.stat().st_size
    return files


def summarize_text(text: str, limit: int = 240) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)] + "..."


def run_shell_command(
    command: str,
    cwd: Path,
    env: Dict[str, str] | None = None,
    timeout: int | None = None,
) -> CommandRecord:
    start_time = now_iso()
    shell_command = command.strip()
    if shell_command.startswith("python "):
        shell_command = sys.executable + shell_command[len("python") :]
    completed = subprocess.run(
        ["/bin/sh", "-lc", shell_command],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    end_time = now_iso()
    return CommandRecord(
        command=shell_command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        start_time=start_time,
        end_time=end_time,
        cwd=str(cwd),
    )


def top_level_names(root: Path) -> Set[str]:
    return {child.name for child in root.iterdir()}
