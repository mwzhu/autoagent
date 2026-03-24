"""Builtin smoke-test adapter."""

from __future__ import annotations

import time
from dataclasses import asdict

from superagent.adapters import AgentAdapter
from superagent.adapters._coding import SIMPLE_CODER_MUTABLE_PATHS, apply_edits, builtin_repair
from superagent.config import AdapterConfig, BuiltinAdapterConfig
from superagent.models import AgentResult, AgentRunInput
from superagent.utils import changed_files, diff_snapshots, snapshot_tree


class BuiltinAdapter(AgentAdapter):
    name = "builtin"

    def run(self, run_input: AgentRunInput, adapter_config: AdapterConfig) -> AgentResult:
        assert isinstance(adapter_config, BuiltinAdapterConfig), "BuiltinAdapter requires BuiltinAdapterConfig."
        started = time.time()
        before_snapshot = snapshot_tree(run_input.working_dir)
        rationale, edits = builtin_repair(adapter_config, run_input.prompt, run_input.working_dir, run_input.metadata)
        _, files_written, integrity_flags = apply_edits(run_input.working_dir, edits)
        after_snapshot = snapshot_tree(run_input.working_dir)
        return AgentResult(
            status="completed" if files_written else "failed",
            final_message=rationale,
            files_written=sorted(changed_files(before_snapshot, after_snapshot)),
            commands=[],
            stdout="",
            stderr="",
            patch_diff=diff_snapshots(before_snapshot, after_snapshot),
            cost_usd=0.0,
            duration_seconds=time.time() - started,
            files_read=[],
            integrity_flags=integrity_flags,
            exit_code=0 if files_written else 1,
        )

    def mutable_paths(self, adapter_config: AdapterConfig) -> list[str]:
        assert isinstance(adapter_config, BuiltinAdapterConfig), "BuiltinAdapter requires BuiltinAdapterConfig."
        return list(SIMPLE_CODER_MUTABLE_PATHS)

    def mutation_context(self, adapter_config: AdapterConfig) -> dict[str, object]:
        assert isinstance(adapter_config, BuiltinAdapterConfig), "BuiltinAdapter requires BuiltinAdapterConfig."
        return asdict(adapter_config)

    def budget_steps(self, adapter_config: AdapterConfig) -> int:
        assert isinstance(adapter_config, BuiltinAdapterConfig), "BuiltinAdapter requires BuiltinAdapterConfig."
        return adapter_config.execution.max_repair_loops
