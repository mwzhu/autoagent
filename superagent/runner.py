"""Task execution and receipt capture."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from superagent.benchmark import run_benchmark_command
from superagent.config import AgentConfig
from superagent.models import EvalTask, FileEdit, RepairProposal, RunReceipt, TaskResult
from superagent.providers import ProviderClient
from superagent.utils import copytree, diff_snapshots, ensure_dir, snapshot_tree, write_json


ALLOWED_WRITE_PREFIX = "src/"


def evaluate_task(
    config: AgentConfig,
    task: EvalTask,
    candidate_id: str,
    output_dir: Path,
    evaluate_hidden: bool,
) -> TaskResult:
    started = time.time()
    task_dir = Path(task.task_dir)
    receipt = RunReceipt(task_id=task.task_id, candidate_id=candidate_id, split=task.split)
    with tempfile.TemporaryDirectory() as tmp_root:
        worktree = Path(tmp_root) / "worktree"
        copytree(task_dir / "buggy", worktree)
        before_snapshot = snapshot_tree(worktree)
        visible = run_benchmark_command(task.visible_test_cmd, worktree)
        receipt.commands.append(visible)
        read_files = _collect_source_files(worktree, config.execution.file_read_budget)
        receipt.files_read.extend(read_files.keys())
        rationale = ""
        failure_output = visible.stdout + visible.stderr
        for _ in range(config.execution.max_repair_loops):
            proposal = _propose_repair(config, task, read_files, failure_output, worktree, task_dir / "fixed")
            rationale = proposal.rationale
            if not proposal.edits:
                break
            if not _apply_edits(worktree, proposal.edits, receipt):
                break
            visible = run_benchmark_command(task.visible_test_cmd, worktree)
            receipt.commands.append(visible)
            if visible.exit_code == 0:
                break
            failure_output = visible.stdout + visible.stderr
        receipt.final_worktree_diff = diff_snapshots(before_snapshot, snapshot_tree(worktree))
        if evaluate_hidden:
            hidden = run_benchmark_command(task.hidden_test_cmd, worktree)
            receipt.commands.append(hidden)
            receipt.hidden_result = "passed" if hidden.exit_code == 0 else "failed"
    receipt.final_submission = {"rationale": rationale, "task_id": task.task_id}
    receipt.visible_passed = any(command.command == task.visible_test_cmd and command.exit_code == 0 for command in receipt.commands)
    receipt_path = output_dir / "receipts" / candidate_id / (task.task_id + ".json")
    write_json(receipt_path, receipt.to_dict())
    return TaskResult(
        task_id=task.task_id,
        split=task.split,
        visible_passed=receipt.visible_passed,
        hidden_result=receipt.hidden_result,
        integrity_flags=list(receipt.integrity_flags),
        receipt_path=str(receipt_path),
        duration_seconds=time.time() - started,
    )


def _collect_source_files(worktree: Path, limit: int) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted((worktree / "src").rglob("*.py"))[:limit]:
        files[str(path.relative_to(worktree))] = path.read_text(encoding="utf-8")
    return files


def _propose_repair(
    config: AgentConfig,
    task: EvalTask,
    read_files: dict[str, str],
    visible_failure_output: str,
    worktree: Path,
    fixed_dir: Path,
) -> RepairProposal:
    if config.task_provider.provider_type == "builtin":
        return _builtin_repair(config, task, worktree, fixed_dir)
    client = ProviderClient(config.task_provider)
    system_prompt = (
        config.system_prompt.rstrip()
        + "\nReturn JSON with rationale and edits. "
        + "Each edit must have path and content. Only write files under src/."
    )
    user_prompt = (
        "Task prompt:\n{}\n\nCurrent files:\n{}\n\nVisible test failure output:\n{}\n\n"
        "Return JSON with rationale and edits."
    ).format(task.prompt, read_files, visible_failure_output[-4000:])
    data, _ = client.generate_json(system_prompt, user_prompt)
    return RepairProposal(
        rationale=data["rationale"],
        edits=[FileEdit(path=edit["path"], content=edit["content"]) for edit in data["edits"]],
    )


def _builtin_repair(
    config: AgentConfig,
    task: EvalTask,
    worktree: Path,
    fixed_dir: Path,
) -> RepairProposal:
    del worktree
    if not _meets_requirements(config, task):
        return RepairProposal(rationale="Configuration does not satisfy the task requirements.", edits=[])
    edits: list[FileEdit] = []
    for path in sorted((fixed_dir / "src").rglob("*.py")):
        edits.append(FileEdit(path=str(path.relative_to(fixed_dir)), content=path.read_text(encoding="utf-8")))
    return RepairProposal(rationale="Builtin solver copied the known fix for a satisfied task.", edits=edits)


def _meets_requirements(config: AgentConfig, task: EvalTask) -> bool:
    checks = {
        "planning": config.orchestration.planning,
        "decomposition": config.orchestration.decomposition,
        "self_check": config.orchestration.self_check,
    }
    for capability in task.required_capabilities:
        assert capability in checks, "Unknown capability: {}".format(capability)
        if not checks[capability]:
            return False
    if config.execution.test_budget < task.min_test_budget:
        return False
    if config.execution.file_read_budget < task.min_file_read_budget:
        return False
    return True


def _apply_edits(worktree: Path, edits: list[FileEdit], receipt: RunReceipt) -> bool:
    if not edits:
        receipt.integrity_flags.append("warning:zero_edit_fix")
        return False
    for edit in edits:
        relative = edit.path.replace("\\", "/")
        if not relative.startswith(ALLOWED_WRITE_PREFIX):
            receipt.integrity_flags.append("blocking:write_outside_src:" + relative)
            return False
        if "/tests/" in relative or relative.startswith("tests/"):
            receipt.integrity_flags.append("blocking:test_edit_attempt:" + relative)
            return False
        target = worktree / relative
        ensure_dir(target.parent)
        target.write_text(edit.content, encoding="utf-8")
        receipt.files_written.append(relative)
    return True
