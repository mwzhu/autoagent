"""Mutation proposal logic."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Tuple

from superagent.adapters import AgentAdapter
from superagent.config import BuiltinProviderConfig, RunConfig
from superagent.models import ConfigChange, MutationProposal, ProviderUsage
from superagent.providers import ProviderClient


PROGRAM_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "program.md"


def propose_mutation(
    config: RunConfig,
    adapter: AgentAdapter,
    last_summary: Dict[str, object],
) -> Tuple[MutationProposal, ProviderUsage]:
    if isinstance(config.meta_provider, BuiltinProviderConfig):
        return _builtin_mutation(config, adapter), ProviderUsage()
    return _llm_mutation(config, adapter, last_summary)


def normalize_mutation_proposal(proposal: MutationProposal) -> str:
    payload = {
        "mutation_type": proposal.mutation_type,
        "reason": proposal.reason.strip(),
        "changes": sorted(
            [{"path": change.path, "value": change.value} for change in proposal.changes],
            key=lambda item: item["path"],
        ),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _builtin_mutation(config: RunConfig, adapter: AgentAdapter) -> MutationProposal:
    adapter_config = config.agent.config
    allowed_paths = adapter.mutable_paths(adapter_config)
    current = asdict(adapter_config)
    ordered_changes = [
        ("orchestration.planning", lambda: True, "planning_toggle", "Enable planning to improve structured tasks."),
        ("orchestration.decomposition", lambda: True, "decomposition_toggle", "Enable decomposition for multi-step tasks."),
        ("orchestration.self_check", lambda: True, "self_check_toggle", "Enable self-checking for safer candidate evaluation."),
        ("execution.test_budget", lambda: _bump_numeric(current, "execution.test_budget", 1), "test_budget_change", "Increase the visible-test budget."),
        ("execution.file_read_budget", lambda: _bump_numeric(current, "execution.file_read_budget", 2), "file_read_budget_change", "Increase the file-read budget."),
        ("execution.max_repair_loops", lambda: _bump_numeric(current, "execution.max_repair_loops", 1), "repair_loops_change", "Allow one more repair loop."),
        ("execution.context_budget", lambda: _bump_numeric(current, "execution.context_budget", 2000), "context_budget_change", "Increase context budget."),
        ("instruction_prefix", lambda: _append_text(current, "instruction_prefix", "Summarize the defect before taking action."), "instruction_prefix_edit", "Strengthen the instruction prefix."),
        ("max_steps", lambda: _bump_numeric(current, "max_steps", 4), "max_steps_change", "Allow more external agent steps."),
        ("per_action_timeout_sec", lambda: _bump_numeric(current, "per_action_timeout_sec", 15), "per_action_timeout_change", "Increase the per-action timeout."),
        ("max_observation_chars", lambda: _bump_numeric(current, "max_observation_chars", 2000), "max_observation_change", "Increase observation budget."),
        ("system_prompt", lambda: _append_text(current, "system_prompt", "Always summarize the failing behavior before editing."), "system_prompt_edit", "Add a debugging reminder to the system prompt."),
    ]
    for path, value_factory, mutation_type, reason in ordered_changes:
        if path not in allowed_paths:
            continue
        value = value_factory()
        current_value = _nested_value(current, path)
        if current_value == value:
            continue
        return MutationProposal(
            mutation_type=mutation_type,
            reason=reason,
            changes=[ConfigChange(path=path, value=value)],
        )
    fallback_path = allowed_paths[0]
    fallback_value = _fallback_value(current, fallback_path)
    return MutationProposal(
        mutation_type="fallback_edit",
        reason="Apply a fallback mutation to continue the search.",
        changes=[ConfigChange(path=fallback_path, value=fallback_value)],
    )


def _llm_mutation(
    config: RunConfig,
    adapter: AgentAdapter,
    last_summary: Dict[str, object],
) -> Tuple[MutationProposal, ProviderUsage]:
    client = ProviderClient(config.meta_provider)
    allowed_paths = adapter.mutable_paths(config.agent.config)
    system_prompt = PROGRAM_PROMPT_PATH.read_text(encoding="utf-8").rstrip()
    user_prompt = (
        "Adapter name: {adapter}\n"
        "Backend name: {backend}\n"
        "Mutable paths inside agent.config: {paths}\n\n"
        "Current mutation context:\n{context}\n\n"
        "Last optimizer summary:\n{summary}\n\n"
        "Return JSON with keys mutation_type, reason, and changes.\n"
        "Each change must contain path and value.\n"
        "Use exactly one mutation proposal and only touch allowed paths."
    ).format(
        adapter=config.agent.adapter,
        backend=config.eval.backend,
        paths=allowed_paths,
        context=adapter.mutation_context(config.agent.config),
        summary=last_summary,
    )
    data, usage = client.generate_json(system_prompt, user_prompt)
    changes = [ConfigChange(path=change["path"], value=change["value"]) for change in data["changes"]]
    return (
        MutationProposal(
            mutation_type=data["mutation_type"],
            reason=data["reason"],
            changes=changes,
        ),
        usage,
    )


def _nested_value(data: Dict[str, object], path: str):
    cursor = data
    for part in path.split("."):
        cursor = cursor[part]
    return cursor


def _bump_numeric(data: Dict[str, object], path: str, amount: int):
    return int(_nested_value(data, path)) + amount


def _append_text(data: Dict[str, object], path: str, line: str) -> str:
    current = str(_nested_value(data, path)).rstrip()
    if line in current:
        return current
    return current + "\n" + line


def _fallback_value(data: Dict[str, object], path: str):
    current = _nested_value(data, path)
    if isinstance(current, bool):
        return not current
    if isinstance(current, int):
        return current + 1
    if isinstance(current, str):
        return current.rstrip() + "\nTry a more explicit debugging plan."
    raise AssertionError("Unsupported fallback mutation value for path: {}".format(path))
