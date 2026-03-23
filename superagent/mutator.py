"""Mutation proposal logic."""

from __future__ import annotations

from typing import Dict, Tuple

from superagent.config import AgentConfig
from superagent.models import ConfigChange, MutationProposal
from superagent.providers import ProviderClient


def propose_mutation(
    config: AgentConfig,
    last_summary: Dict[str, object],
) -> Tuple[MutationProposal, float]:
    if config.meta_provider.provider_type == "builtin":
        return _builtin_mutation(config), 0.0
    return _llm_mutation(config, last_summary)


def _builtin_mutation(config: AgentConfig) -> MutationProposal:
    if not config.orchestration.planning:
        return MutationProposal(
            mutation_type="planning_toggle",
            reason="Enable planning to improve tasks that need explicit decomposition.",
            changes=[ConfigChange(path="orchestration.planning", value=True)],
        )
    if not config.orchestration.decomposition:
        return MutationProposal(
            mutation_type="decomposition_toggle",
            reason="Enable decomposition for multi-step repair tasks.",
            changes=[ConfigChange(path="orchestration.decomposition", value=True)],
        )
    if config.execution.test_budget < 4:
        return MutationProposal(
            mutation_type="test_budget_change",
            reason="Increase the test budget to support more validation steps.",
            changes=[ConfigChange(path="execution.test_budget", value=config.execution.test_budget + 1)],
        )
    if config.execution.file_read_budget < 16:
        return MutationProposal(
            mutation_type="file_read_budget_change",
            reason="Increase the file read budget for broader inspection.",
            changes=[ConfigChange(path="execution.file_read_budget", value=config.execution.file_read_budget + 2)],
        )
    if config.execution.max_repair_loops < 4:
        return MutationProposal(
            mutation_type="repair_loops_change",
            reason="Allow one more repair loop for iterative fixes.",
            changes=[ConfigChange(path="execution.max_repair_loops", value=config.execution.max_repair_loops + 1)],
        )
    if "Always summarize the failing behavior before editing." not in config.system_prompt:
        return MutationProposal(
            mutation_type="system_prompt_edit",
            reason="Add a debugging reminder to the system prompt.",
            changes=[ConfigChange(path="system_prompt", value=config.system_prompt.rstrip() + "\nAlways summarize the failing behavior before editing.")],
        )
    return MutationProposal(
        mutation_type="context_budget_change",
        reason="Increase context budget as a safe fallback mutation.",
        changes=[ConfigChange(path="execution.context_budget", value=config.execution.context_budget + 2000)],
    )


def _llm_mutation(config: AgentConfig, last_summary: Dict[str, object]) -> Tuple[MutationProposal, float]:
    client = ProviderClient(config.meta_provider)
    allowed_types = [
        "system_prompt_edit",
        "planning_toggle",
        "decomposition_toggle",
        "self_check_toggle",
        "repair_loops_change",
        "test_budget_change",
        "file_read_budget_change",
        "context_budget_change",
    ]
    system_prompt = (
        "You mutate agent configurations for a self-improving coding agent. "
        "Return JSON with keys mutation_type, reason, and changes. "
        "Each change must contain path and value."
    )
    user_prompt = (
        "Current config:\n{}\n\n"
        "Last summary:\n{}\n\n"
        "Allowed mutation types: {}\n"
        "Return only one mutation proposal."
    ).format(config.to_dict(), last_summary, allowed_types)
    data, cost = client.generate_json(system_prompt, user_prompt)
    changes = [ConfigChange(path=change["path"], value=change["value"]) for change in data["changes"]]
    proposal = MutationProposal(
        mutation_type=data["mutation_type"],
        reason=data["reason"],
        changes=changes,
    )
    return proposal, cost
