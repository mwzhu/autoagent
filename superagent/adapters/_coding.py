"""Shared helpers for coding-focused adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from superagent.config import BuiltinAdapterConfig, SimpleCoderAdapterConfig
from superagent.models import FileEdit
from superagent.utils import ensure_dir


ALLOWED_WRITE_PREFIX = "src/"

SIMPLE_CODER_MUTABLE_PATHS = [
    "system_prompt",
    "orchestration.planning",
    "orchestration.decomposition",
    "orchestration.self_check",
    "execution.max_repair_loops",
    "execution.test_budget",
    "execution.file_read_budget",
    "execution.context_budget",
]


def collect_source_files(worktree: Path, limit: int) -> Dict[str, str]:
    files: Dict[str, str] = {}
    for path in sorted((worktree / "src").rglob("*.py"))[:limit]:
        files[str(path.relative_to(worktree))] = path.read_text(encoding="utf-8")
    return files


def builtin_repair(
    adapter_config: BuiltinAdapterConfig | SimpleCoderAdapterConfig,
    task_prompt: str,
    working_dir: Path,
    metadata: Dict[str, object],
) -> Tuple[str, List[FileEdit]]:
    del task_prompt, working_dir
    required_capabilities = [str(item) for item in metadata.get("required_capabilities", [])]
    min_test_budget = int(metadata.get("min_test_budget", 1))
    min_file_read_budget = int(metadata.get("min_file_read_budget", 1))
    fixed_dir = Path(str(metadata["fixed_dir"]))
    if not meets_requirements(
        adapter_config,
        required_capabilities=required_capabilities,
        min_test_budget=min_test_budget,
        min_file_read_budget=min_file_read_budget,
    ):
        return "Configuration does not satisfy the task requirements.", []
    edits: List[FileEdit] = []
    for path in sorted((fixed_dir / "src").rglob("*.py")):
        edits.append(FileEdit(path=str(path.relative_to(fixed_dir)), content=path.read_text(encoding="utf-8")))
    return "Builtin solver copied the known fix for a satisfied task.", edits


def meets_requirements(
    adapter_config: BuiltinAdapterConfig | SimpleCoderAdapterConfig,
    required_capabilities: List[str],
    min_test_budget: int,
    min_file_read_budget: int,
) -> bool:
    checks = {
        "planning": adapter_config.orchestration.planning,
        "decomposition": adapter_config.orchestration.decomposition,
        "self_check": adapter_config.orchestration.self_check,
    }
    for capability in required_capabilities:
        assert capability in checks, "Unknown capability: {}".format(capability)
        if not checks[capability]:
            return False
    if adapter_config.execution.test_budget < min_test_budget:
        return False
    if adapter_config.execution.file_read_budget < min_file_read_budget:
        return False
    return True


def apply_edits(worktree: Path, edits: List[FileEdit]) -> Tuple[bool, List[str], List[str]]:
    files_written: List[str] = []
    integrity_flags: List[str] = []
    if not edits:
        integrity_flags.append("warning:zero_edit_fix")
        return False, files_written, integrity_flags
    for edit in edits:
        relative = edit.path.replace("\\", "/")
        if not relative.startswith(ALLOWED_WRITE_PREFIX):
            integrity_flags.append("blocking:write_outside_src:" + relative)
            return False, files_written, integrity_flags
        if "/tests/" in relative or relative.startswith("tests/"):
            integrity_flags.append("blocking:test_edit_attempt:" + relative)
            return False, files_written, integrity_flags
        target = worktree / relative
        ensure_dir(target.parent)
        target.write_text(edit.content, encoding="utf-8")
        files_written.append(relative)
    return True, files_written, integrity_flags
