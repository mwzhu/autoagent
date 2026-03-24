"""In-repo simple coding adapter."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Dict, Tuple

from superagent.adapters import AgentAdapter
from superagent.adapters._coding import SIMPLE_CODER_MUTABLE_PATHS, apply_edits, builtin_repair, collect_source_files
from superagent.benchmark import run_benchmark_command
from superagent.config import AdapterConfig, BuiltinProviderConfig, SimpleCoderAdapterConfig
from superagent.models import AgentResult, AgentRunInput, CommandRecord, FileEdit
from superagent.providers import ProviderClient
from superagent.utils import changed_files, diff_snapshots, snapshot_tree


class SimpleCoderAdapter(AgentAdapter):
    name = "simple_coder"

    def run(self, run_input: AgentRunInput, adapter_config: AdapterConfig) -> AgentResult:
        assert isinstance(adapter_config, SimpleCoderAdapterConfig), "SimpleCoderAdapter requires SimpleCoderAdapterConfig."
        started = time.time()
        commands: list[CommandRecord] = []
        files_read: list[str] = []
        files_written: list[str] = []
        integrity_flags: list[str] = []
        total_cost = 0.0
        before_snapshot = snapshot_tree(run_input.working_dir)
        visible_test_cmd = str(run_input.metadata.get("visible_test_cmd", "")).strip()
        read_files = collect_source_files(run_input.working_dir, adapter_config.execution.file_read_budget)
        files_read.extend(read_files.keys())
        visible = None
        tests_used = 0
        failure_output = ""
        if visible_test_cmd and adapter_config.execution.test_budget > 0:
            visible = run_benchmark_command(visible_test_cmd, run_input.working_dir)
            commands.append(visible)
            tests_used += 1
            failure_output = visible.stdout + visible.stderr
        rationale = ""
        for _ in range(adapter_config.execution.max_repair_loops):
            rationale, edits, step_cost = self._propose_repair(adapter_config, run_input, read_files, failure_output)
            total_cost += step_cost
            if not edits:
                integrity_flags.append("warning:zero_edit_fix")
                break
            applied, new_files_written, apply_flags = apply_edits(run_input.working_dir, edits)
            integrity_flags.extend(apply_flags)
            if not applied:
                break
            files_written.extend(new_files_written)
            if not visible_test_cmd:
                continue
            if tests_used >= adapter_config.execution.test_budget:
                break
            visible = run_benchmark_command(visible_test_cmd, run_input.working_dir)
            commands.append(visible)
            tests_used += 1
            if visible.exit_code == 0:
                break
            failure_output = visible.stdout + visible.stderr
        after_snapshot = snapshot_tree(run_input.working_dir)
        command_stdout = "".join(command.stdout for command in commands)
        command_stderr = "".join(command.stderr for command in commands)
        last_exit_code = commands[-1].exit_code if commands else 0
        status = "completed" if visible is not None and visible.exit_code == 0 else "failed"
        if not commands:
            status = "completed" if files_written else "failed"
        return AgentResult(
            status=status,
            final_message=rationale or "No repair rationale produced.",
            files_written=sorted(changed_files(before_snapshot, after_snapshot)),
            commands=commands,
            stdout=command_stdout,
            stderr=command_stderr,
            patch_diff=diff_snapshots(before_snapshot, after_snapshot),
            cost_usd=total_cost,
            duration_seconds=time.time() - started,
            files_read=files_read,
            integrity_flags=sorted(set(integrity_flags)),
            exit_code=last_exit_code,
        )

    def mutable_paths(self, adapter_config: AdapterConfig) -> list[str]:
        assert isinstance(adapter_config, SimpleCoderAdapterConfig), "SimpleCoderAdapter requires SimpleCoderAdapterConfig."
        return list(SIMPLE_CODER_MUTABLE_PATHS)

    def mutation_context(self, adapter_config: AdapterConfig) -> dict[str, object]:
        assert isinstance(adapter_config, SimpleCoderAdapterConfig), "SimpleCoderAdapter requires SimpleCoderAdapterConfig."
        return asdict(adapter_config)

    def budget_steps(self, adapter_config: AdapterConfig) -> int:
        assert isinstance(adapter_config, SimpleCoderAdapterConfig), "SimpleCoderAdapter requires SimpleCoderAdapterConfig."
        return adapter_config.execution.max_repair_loops

    def _propose_repair(
        self,
        adapter_config: SimpleCoderAdapterConfig,
        run_input: AgentRunInput,
        read_files: Dict[str, str],
        visible_failure_output: str,
    ) -> Tuple[str, list[FileEdit], float]:
        if isinstance(adapter_config.task_provider, BuiltinProviderConfig):
            rationale, edits = builtin_repair(adapter_config, run_input.prompt, run_input.working_dir, run_input.metadata)
            return rationale, edits, 0.0
        client = ProviderClient(adapter_config.task_provider)
        system_prompt = (
            adapter_config.system_prompt.rstrip()
            + "\nReturn JSON with rationale and edits. "
            + "Each edit must have path and content. Only write files under src/."
        )
        user_prompt = (
            "Task prompt:\n{}\n\nCurrent files:\n{}\n\nVisible test failure output:\n{}\n\n"
            "Return JSON with rationale and edits."
        ).format(run_input.prompt, read_files, visible_failure_output[-4000:])
        data, usage = client.generate_json(system_prompt, user_prompt)
        edits = [FileEdit(path=edit["path"], content=edit["content"]) for edit in data.get("edits", [])]
        return data.get("rationale", ""), edits, usage.cost_usd
