"""External mini-swe-agent adapter."""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import asdict

from superagent.adapters import AgentAdapter
from superagent.config import AdapterConfig, MiniSweAgentAdapterConfig
from superagent.models import AgentResult, AgentRunInput, CommandRecord
from superagent.utils import changed_files, diff_snapshots, ensure_dir, now_iso, snapshot_tree


class MiniSweAgentAdapter(AgentAdapter):
    name = "mini_swe_agent"

    def run(self, run_input: AgentRunInput, adapter_config: AdapterConfig) -> AgentResult:
        assert isinstance(adapter_config, MiniSweAgentAdapterConfig), "MiniSweAgentAdapter requires MiniSweAgentAdapterConfig."
        started = time.time()
        ensure_dir(run_input.artifacts_dir)
        prompt_path = run_input.artifacts_dir / "prompt.txt"
        prompt_path.write_text(run_input.prompt, encoding="utf-8")
        before_snapshot = snapshot_tree(run_input.working_dir)
        env = os.environ.copy()
        env["SUPERAGENT_TASK_ID"] = run_input.task_id
        env["SUPERAGENT_WORKDIR"] = str(run_input.working_dir)
        env["SUPERAGENT_ARTIFACTS_DIR"] = str(run_input.artifacts_dir)
        env["SUPERAGENT_PROMPT_FILE"] = str(prompt_path)
        env["SUPERAGENT_PROMPT"] = run_input.prompt
        env["SUPERAGENT_MODEL"] = adapter_config.model
        env["SUPERAGENT_BASE_URL"] = adapter_config.base_url
        env["SUPERAGENT_MAX_STEPS"] = str(adapter_config.max_steps)
        env["SUPERAGENT_PER_ACTION_TIMEOUT_SEC"] = str(adapter_config.per_action_timeout_sec)
        env["SUPERAGENT_MAX_OBSERVATION_CHARS"] = str(adapter_config.max_observation_chars)
        env["SUPERAGENT_TOOL_MODE"] = adapter_config.tool_mode
        env["SUPERAGENT_INSTRUCTION_PREFIX"] = adapter_config.instruction_prefix
        if adapter_config.api_key_env:
            env["SUPERAGENT_API_KEY"] = os.environ.get(adapter_config.api_key_env, "")
        command_start = now_iso()
        completed = subprocess.run(
            adapter_config.command,
            cwd=str(run_input.working_dir),
            env=env,
            capture_output=True,
            text=True,
            shell=True,
            timeout=max(1, adapter_config.max_steps) * max(1, adapter_config.per_action_timeout_sec),
        )
        command_end = now_iso()
        after_snapshot = snapshot_tree(run_input.working_dir)
        patch_diff = diff_snapshots(before_snapshot, after_snapshot)
        files_written = sorted(changed_files(before_snapshot, after_snapshot))
        return AgentResult(
            status="completed" if completed.returncode == 0 else "failed",
            final_message=self._final_message(completed.stdout),
            files_written=files_written,
            commands=[
                CommandRecord(
                    command=adapter_config.command,
                    exit_code=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    start_time=command_start,
                    end_time=command_end,
                )
            ],
            stdout=completed.stdout,
            stderr=completed.stderr,
            patch_diff=patch_diff,
            cost_usd=self._extract_cost(completed.stdout + "\n" + completed.stderr),
            duration_seconds=time.time() - started,
            files_read=[],
            integrity_flags=[],
            exit_code=completed.returncode,
        )

    def mutable_paths(self, adapter_config: AdapterConfig) -> list[str]:
        assert isinstance(adapter_config, MiniSweAgentAdapterConfig), "MiniSweAgentAdapter requires MiniSweAgentAdapterConfig."
        return [
            "instruction_prefix",
            "max_steps",
            "per_action_timeout_sec",
            "max_observation_chars",
        ]

    def mutation_context(self, adapter_config: AdapterConfig) -> dict[str, object]:
        assert isinstance(adapter_config, MiniSweAgentAdapterConfig), "MiniSweAgentAdapter requires MiniSweAgentAdapterConfig."
        return asdict(adapter_config)

    def budget_steps(self, adapter_config: AdapterConfig) -> int:
        assert isinstance(adapter_config, MiniSweAgentAdapterConfig), "MiniSweAgentAdapter requires MiniSweAgentAdapterConfig."
        return adapter_config.max_steps

    def _extract_cost(self, text: str) -> float:
        matches = re.findall(r"cost_usd\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", text)
        if matches:
            return float(matches[-1])
        return 0.0

    def _final_message(self, stdout: str) -> str:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        if not lines:
            return "mini-swe-agent finished without a final message."
        return lines[-1]
