"""Benchmark generation and validation."""

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
from superagent.models import CommandRecord, EvalTask
from superagent.utils import copytree, ensure_dir, now_iso


VISIBLE_CMD = "python -m unittest discover -s tests/visible -p 'test_*.py'"
HIDDEN_CMD = "python -m unittest discover -s tests/hidden -p 'test_*.py'"


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


def load_tasks(benchmark_dir: Path) -> List[EvalTask]:
    tasks = []
    for task_file in sorted((benchmark_dir / "tasks").glob("*/task.yaml")):
        with task_file.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        task = EvalTask(
            task_id=data["task_id"],
            repo_id=data["repo_id"],
            category=data["category"],
            difficulty=data["difficulty"],
            prompt=data["prompt"],
            visible_test_cmd=data["visible_test_cmd"],
            hidden_test_cmd=data["hidden_test_cmd"],
            expected_artifact=data["expected_artifact"],
            mutation_lineage=data.get("mutation_lineage", []),
            split=data["split"],
            required_capabilities=data.get("required_capabilities", []),
            min_test_budget=data.get("min_test_budget", 1),
            min_file_read_budget=data.get("min_file_read_budget", 1),
            task_dir=str(task_file.parent),
        )
        tasks.append(task)
    return tasks


def split_tasks(tasks: List[EvalTask]) -> Dict[str, List[EvalTask]]:
    grouped = {"train": [], "guard": [], "holdout": []}
    for task in tasks:
        grouped[task.split].append(task)
    return grouped


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
        buggy_visible = run_benchmark_command(task.visible_test_cmd, buggy_copy)
        buggy_hidden = run_benchmark_command(task.hidden_test_cmd, buggy_copy)
        fixed_visible = run_benchmark_command(task.visible_test_cmd, fixed_copy)
        fixed_hidden = run_benchmark_command(task.hidden_test_cmd, fixed_copy)
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
    tasks = load_tasks(benchmark_dir)
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
