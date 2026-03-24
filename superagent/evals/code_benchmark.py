"""Code benchmark backend and helpers."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from superagent.benchmark_definitions import DEFAULT_TASK_DEFINITIONS
from superagent.config import CodeBenchmarkEvalConfig, EvalConfig
from superagent.evals.base import EvalBackend
from superagent.models import AgentResult, AgentRunInput, CommandRecord, EvalTask, TaskResult
from superagent.utils import copytree, ensure_dir, now_iso


VISIBLE_CMD = "python -m unittest discover -s tests/visible -p 'test_*.py'"
HIDDEN_CMD = "python -m unittest discover -s tests/hidden -p 'test_*.py'"


class CodeBenchmarkBackend(EvalBackend):
    name = "code_benchmark"

    def load_tasks(self, eval_config: EvalConfig) -> List[EvalTask]:
        assert isinstance(eval_config, CodeBenchmarkEvalConfig), "CodeBenchmarkBackend requires CodeBenchmarkEvalConfig."
        tasks: List[EvalTask] = []
        benchmark_dir = Path(eval_config.benchmark_dir)
        for task_file in sorted((benchmark_dir / "tasks").glob("*/task.yaml")):
            with task_file.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
            task_dir = task_file.parent
            tasks.append(
                EvalTask(
                    task_id=data["task_id"],
                    repo_id=data["repo_id"],
                    category=data["category"],
                    difficulty=data["difficulty"],
                    prompt=data["prompt"],
                    split=data["split"],
                    mutation_lineage=data.get("mutation_lineage", []),
                    required_capabilities=data.get("required_capabilities", []),
                    min_test_budget=data.get("min_test_budget", 1),
                    min_file_read_budget=data.get("min_file_read_budget", 1),
                    task_dir=str(task_dir),
                    metadata={
                        "visible_test_cmd": data["visible_test_cmd"],
                        "hidden_test_cmd": data["hidden_test_cmd"],
                        "fixed_dir": str(task_dir / "fixed"),
                    },
                )
            )
        return tasks

    def split_tasks(self, tasks: List[EvalTask]) -> Dict[str, List[EvalTask]]:
        grouped = {"train": [], "guard": [], "holdout": []}
        for task in tasks:
            grouped[task.split].append(task)
        return grouped

    def prepare_run(self, task: EvalTask, candidate_id: str, output_dir: Path) -> AgentRunInput:
        task_dir = Path(task.task_dir)
        working_dir = output_dir / "workspaces" / candidate_id / task.task_id
        artifacts_dir = output_dir / "adapter_artifacts" / candidate_id / task.task_id
        _copy_task_workspace(task_dir, working_dir)
        ensure_dir(artifacts_dir)
        prompt = (
            task.prompt.rstrip()
            + "\nEdit source files under src/ only."
            + "\nVisible tests are available under tests/visible."
            + "\nRun visible tests with: {}.".format(task.metadata["visible_test_cmd"])
        )
        metadata = dict(task.metadata)
        metadata.update(
            {
                "required_capabilities": list(task.required_capabilities),
                "min_test_budget": task.min_test_budget,
                "min_file_read_budget": task.min_file_read_budget,
            }
        )
        return AgentRunInput(
            task_id=task.task_id,
            prompt=prompt,
            working_dir=working_dir,
            artifacts_dir=artifacts_dir,
            budget_steps=0,
            metadata=metadata,
        )

    def score_task(
        self,
        task: EvalTask,
        run_input: AgentRunInput,
        agent_result: AgentResult,
        evaluate_hidden: bool,
    ) -> TaskResult:
        integrity_flags = list(agent_result.integrity_flags)
        commands: List[CommandRecord] = []
        if any("/tests/" in path or path.startswith("tests/") for path in agent_result.files_written):
            integrity_flags.append("blocking:test_edit_attempt")
        for path in agent_result.files_written:
            if not path.replace("\\", "/").startswith("src/"):
                integrity_flags.append("blocking:write_outside_src:" + path.replace("\\", "/"))
        if any("tests/hidden" in path for path in agent_result.files_read):
            integrity_flags.append("blocking:hidden_path_read")
        visible_passed = False
        hidden_result = "not_run"
        if not any(flag.startswith("blocking:") for flag in integrity_flags):
            visible = run_benchmark_command(str(task.metadata["visible_test_cmd"]), run_input.working_dir)
            commands.append(visible)
            visible_passed = visible.exit_code == 0
            if evaluate_hidden:
                hidden = self._run_hidden(task, run_input.working_dir)
                commands.append(hidden)
                hidden_result = "passed" if hidden.exit_code == 0 else "failed"
        passed = visible_passed if task.split == "train" else hidden_result == "passed"
        return TaskResult(
            task_id=task.task_id,
            split=task.split,
            passed=passed,
            score=1.0 if passed else 0.0,
            visible_passed=visible_passed,
            hidden_result=hidden_result,
            integrity_flags=sorted(set(integrity_flags)),
            commands=commands,
            task_cost_usd=agent_result.cost_usd,
        )

    def aggregate(self, results: List[TaskResult], split: str, eval_config: EvalConfig) -> float:
        del eval_config
        if split == "train":
            return float(sum(1 for result in results if result.split == "train" and result.visible_passed))
        return float(sum(1 for result in results if result.split == split and result.hidden_result == "passed"))

    def validate(self, eval_config: EvalConfig) -> Dict[str, object]:
        assert isinstance(eval_config, CodeBenchmarkEvalConfig), "CodeBenchmarkBackend requires CodeBenchmarkEvalConfig."
        return validate_benchmark(Path(eval_config.benchmark_dir))

    def _run_hidden(self, task: EvalTask, working_dir: Path) -> CommandRecord:
        task_dir = Path(task.task_dir)
        with tempfile.TemporaryDirectory() as tmp_root:
            eval_dir = Path(tmp_root) / "hidden_eval"
            copytree(working_dir, eval_dir)
            hidden_src = task_dir / "buggy" / "tests" / "hidden"
            hidden_dst = eval_dir / "tests" / "hidden"
            ensure_dir(hidden_dst.parent)
            shutil.copytree(hidden_src, hidden_dst)
            return run_benchmark_command(str(task.metadata["hidden_test_cmd"]), eval_dir)

def default_benchmark_dir(root: Path) -> Path:
    return root / "artifacts" / "benchmark" / "v1"


def build_benchmark(output_dir: Path, force: bool = False) -> Path:
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise ValueError("Benchmark directory already exists. Use --force to rebuild.")
    if output_dir.exists() and force:
        shutil.rmtree(output_dir)
    ensure_dir(output_dir / "tasks")
    catalog = []
    for definition in _selected_definitions():
        task_dir = output_dir / "tasks" / definition["task_id"]
        buggy_dir = task_dir / "buggy"
        fixed_dir = task_dir / "fixed"
        for root in (buggy_dir, fixed_dir):
            ensure_dir(root / "src")
            ensure_dir(root / "tests" / "visible")
            ensure_dir(root / "tests" / "hidden")
            (root / "src" / "app.py").write_text(definition["buggy_source"], encoding="utf-8")
            if root is fixed_dir:
                (root / "src" / "app.py").write_text(definition["fixed_source"], encoding="utf-8")
            (root / "tests" / "visible" / "test_visible.py").write_text(definition["visible_tests"], encoding="utf-8")
            (root / "tests" / "hidden" / "test_hidden.py").write_text(definition["hidden_tests"], encoding="utf-8")
        task_metadata = {
            "task_id": definition["task_id"],
            "repo_id": definition["repo_id"],
            "category": definition["category"],
            "split": definition["split"],
            "difficulty": definition["difficulty"],
            "prompt": definition["prompt"],
            "visible_test_cmd": VISIBLE_CMD,
            "hidden_test_cmd": HIDDEN_CMD,
            "expected_artifact": "src/app.py",
            "mutation_lineage": [],
            "required_capabilities": definition["required_capabilities"],
            "min_test_budget": definition["min_test_budget"],
            "min_file_read_budget": definition["min_file_read_budget"],
        }
        with (task_dir / "task.yaml").open("w", encoding="utf-8") as handle:
            yaml.safe_dump(task_metadata, handle, sort_keys=False)
        catalog.append(task_metadata)
    with (output_dir / "benchmark.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"tasks": catalog}, handle, sort_keys=False)
    return output_dir


def run_benchmark_command(command: str, cwd: Path) -> CommandRecord:
    start_time = now_iso()
    argv = shlex.split(command)
    if argv and argv[0] == "python":
        argv[0] = sys.executable
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    end_time = now_iso()
    return CommandRecord(
        command=command,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        start_time=start_time,
        end_time=end_time,
    )


def validate_task(task: EvalTask) -> Tuple[bool, Dict[str, str]]:
    task_dir = Path(task.task_dir)
    buggy_dir = task_dir / "buggy"
    fixed_dir = task_dir / "fixed"
    with tempfile.TemporaryDirectory() as tmp_root:
        tmp_root_path = Path(tmp_root)
        buggy_copy = tmp_root_path / "buggy"
        fixed_copy = tmp_root_path / "fixed"
        copytree(buggy_dir, buggy_copy)
        copytree(fixed_dir, fixed_copy)
        buggy_visible = run_benchmark_command(str(task.metadata["visible_test_cmd"]), buggy_copy)
        buggy_hidden = run_benchmark_command(str(task.metadata["hidden_test_cmd"]), buggy_copy)
        fixed_visible = run_benchmark_command(str(task.metadata["visible_test_cmd"]), fixed_copy)
        fixed_hidden = run_benchmark_command(str(task.metadata["hidden_test_cmd"]), fixed_copy)
    results = {
        "buggy_visible": "pass" if buggy_visible.exit_code == 0 else "fail",
        "buggy_hidden": "pass" if buggy_hidden.exit_code == 0 else "fail",
        "fixed_visible": "pass" if fixed_visible.exit_code == 0 else "fail",
        "fixed_hidden": "pass" if fixed_hidden.exit_code == 0 else "fail",
    }
    is_valid = (
        buggy_visible.exit_code != 0
        and buggy_hidden.exit_code != 0
        and fixed_visible.exit_code == 0
        and fixed_hidden.exit_code == 0
    )
    return is_valid, results


def validate_benchmark(benchmark_dir: Path) -> Dict[str, object]:
    backend = CodeBenchmarkBackend()
    tasks = backend.load_tasks(CodeBenchmarkEvalConfig(benchmark_dir=str(benchmark_dir)))
    results = []
    valid_count = 0
    for task in tasks:
        ok, detail = validate_task(task)
        if ok:
            valid_count += 1
        results.append({"task_id": task.task_id, "valid": ok, "details": detail})
    return {
        "task_count": len(tasks),
        "valid_count": valid_count,
        "invalid_count": len(tasks) - valid_count,
        "results": results,
    }


def _selected_definitions() -> List[Dict[str, object]]:
    train = [definition for definition in DEFAULT_TASK_DEFINITIONS if definition["split"] == "train"][:20]
    guard = [definition for definition in DEFAULT_TASK_DEFINITIONS if definition["split"] == "guard"][:6]
    holdout = [definition for definition in DEFAULT_TASK_DEFINITIONS if definition["split"] == "holdout"][:6]
    return train + guard + holdout


def _copy_task_workspace(task_dir: Path, working_dir: Path) -> None:
    if working_dir.exists():
        shutil.rmtree(working_dir)
    ensure_dir(working_dir)
    shutil.copytree(task_dir / "buggy" / "src", working_dir / "src")
    shutil.copytree(task_dir / "buggy" / "tests" / "visible", working_dir / "tests" / "visible")
