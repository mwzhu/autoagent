"""Task execution coordination and receipt capture."""

from __future__ import annotations

import time
from pathlib import Path

from superagent.adapters import AgentAdapter
from superagent.config import RunConfig
from superagent.evals import EvalBackend
from superagent.models import RunReceipt, TaskResult, EvalTask
from superagent.utils import write_json


def evaluate_task(
    config: RunConfig,
    adapter: AgentAdapter,
    backend: EvalBackend,
    task: EvalTask,
    candidate_id: str,
    output_dir: Path,
    evaluate_hidden: bool,
) -> TaskResult:
    started = time.time()
    run_input = backend.prepare_run(task, candidate_id, output_dir)
    run_input.budget_steps = adapter.budget_steps(config.agent.config)
    agent_result = adapter.run(run_input, config.agent.config)
    task_result = backend.score_task(task, run_input, agent_result, evaluate_hidden)
    receipt = RunReceipt(
        task_id=task.task_id,
        candidate_id=candidate_id,
        split=task.split,
        commands=list(agent_result.commands) + list(task_result.commands),
        files_read=list(agent_result.files_read),
        files_written=list(agent_result.files_written),
        final_worktree_diff=agent_result.patch_diff,
        final_submission={
            "adapter": config.agent.adapter,
            "backend": config.eval.backend,
            "status": agent_result.status,
            "final_message": agent_result.final_message,
        },
        visible_passed=task_result.visible_passed,
        hidden_result=task_result.hidden_result,
        integrity_flags=sorted(set(task_result.integrity_flags)),
    )
    receipt.integrity_flags = sorted(set(receipt.integrity_flags + _receipt_requirement_flags(config, receipt)))
    receipt_path = output_dir / "receipts" / candidate_id / (task.task_id + ".json")
    write_json(receipt_path, receipt.to_dict())
    task_result.receipt_path = str(receipt_path)
    task_result.duration_seconds = time.time() - started
    task_result.integrity_flags = list(receipt.integrity_flags)
    task_result.task_cost_usd = agent_result.cost_usd
    return task_result


def _receipt_requirement_flags(config: RunConfig, receipt: RunReceipt) -> list[str]:
    required = set(config.guards.receipt_requirements)
    flags: list[str] = []
    if "commands" in required and not receipt.commands:
        flags.append("warning:missing_agent_commands")
    if "files_written" in required and not receipt.files_written:
        flags.append("warning:missing_files_written")
    if "final_worktree_diff" in required and receipt.files_written and not receipt.final_worktree_diff:
        flags.append("warning:missing_diff")
    return flags
