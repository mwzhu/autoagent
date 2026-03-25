import json
import shutil
from pathlib import Path

import yaml


FIXTURE_REPO = Path(__file__).resolve().parent / "fixtures" / "agent_repo"


def copy_fixture_repo(destination: Path) -> Path:
    shutil.copytree(FIXTURE_REPO, destination, copy_function=shutil.copy2)
    return destination


def write_dataset(dataset_path: Path) -> Path:
    rows = [
        {
            "id": "train_one",
            "split": "train",
            "prompt": "Return alpha",
            "expected_output": "alpha",
            "public_fields": {"public_answer": "alpha", "bad_answer": "wrong", "assert_repo_temp_absent": True},
        },
        {
            "id": "train_two",
            "split": "train",
            "prompt": "Return beta",
            "expected_output": "beta",
            "public_fields": {"public_answer": "beta", "bad_answer": "wrong", "assert_repo_temp_absent": True},
        },
        {
            "id": "guard_one",
            "split": "guard",
            "prompt": "Return gamma",
            "expected_output": "gamma",
            "public_fields": {"public_answer": "gamma", "bad_answer": "wrong"},
        },
        {
            "id": "holdout_one",
            "split": "holdout",
            "prompt": "Return delta",
            "expected_output": "delta",
            "public_fields": {"public_answer": "delta", "bad_answer": "wrong"},
        },
    ]
    dataset_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return dataset_path


def write_tiny_benchmark(benchmark_dir: Path) -> Path:
    definitions = [
        _benchmark_definition("train_fix_one", "train", "repair", 1, "alpha"),
        _benchmark_definition("train_fix_two", "train", "repair", 2, "beta"),
        _benchmark_definition("guard_fix", "guard", "guard", 1, "gamma"),
        _benchmark_definition("holdout_fix", "holdout", "holdout", 1, "delta"),
    ]
    tasks_dir = benchmark_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    catalog = []
    for definition in definitions:
        task_dir = tasks_dir / definition["task_id"]
        buggy_dir = task_dir / "buggy"
        fixed_dir = task_dir / "fixed"
        for root in (buggy_dir, fixed_dir):
            (root / "src").mkdir(parents=True, exist_ok=True)
            (root / "tests" / "visible").mkdir(parents=True, exist_ok=True)
            (root / "tests" / "hidden").mkdir(parents=True, exist_ok=True)
        (buggy_dir / "src" / "app.py").write_text(definition["buggy_source"], encoding="utf-8")
        (fixed_dir / "src" / "app.py").write_text(definition["fixed_source"], encoding="utf-8")
        visible_test = _test_source(definition["expected_value"])
        hidden_test = _test_source(definition["expected_value"])
        (buggy_dir / "tests" / "visible" / "test_visible.py").write_text(visible_test, encoding="utf-8")
        (buggy_dir / "tests" / "hidden" / "test_hidden.py").write_text(hidden_test, encoding="utf-8")
        (fixed_dir / "tests" / "visible" / "test_visible.py").write_text(visible_test, encoding="utf-8")
        (fixed_dir / "tests" / "hidden" / "test_hidden.py").write_text(hidden_test, encoding="utf-8")
        task_yaml = {
            "task_id": definition["task_id"],
            "repo_id": "fixture",
            "category": definition["category"],
            "split": definition["split"],
            "difficulty": definition["difficulty"],
            "prompt": definition["prompt"],
            "visible_test_cmd": "python -m unittest discover -s tests/visible -p 'test_*.py'",
            "hidden_test_cmd": "python -m unittest discover -s tests/hidden -p 'test_*.py'",
            "required_capabilities": [],
            "public_fields": {
                "replacement_source": definition["fixed_source"],
                "bad_source": definition["buggy_source"],
            },
        }
        with (task_dir / "task.yaml").open("w", encoding="utf-8") as handle:
            yaml.safe_dump(task_yaml, handle, sort_keys=False)
        catalog.append(task_yaml)
    with (benchmark_dir / "benchmark.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"tasks": catalog}, handle, sort_keys=False)
    return benchmark_dir


def write_run_config(config_path: Path, repo_root: Path, eval_section: dict) -> Path:
    config = {
        "agent": {
            "repo_root": str(repo_root),
            "run_command": "python agent.py",
            "install_command": "python install_fixture.py",
            "entry_contract": {"input_file": "task.json", "output_mode": eval_section["output_mode"], "output_file": eval_section.get("output_file")},
            "mutation_boundary": {"type": "full_repo"},
        },
        "eval": {key: value for key, value in eval_section.items() if key != "output_mode" and key != "output_file"},
        "policy": {
            "screening_sample_size": 1,
            "archive_size": 2,
            "rerun_borderline_accepts": True,
            "max_evaluations": 20,
            "max_accepts": 20,
            "max_task_cost_usd": 100,
            "max_wall_clock_hours": 1,
        },
        "guards": {
            "forbidden_commands": ["curl"],
            "no_network": True,
            "receipt_requirements": ["commands", "files_written", "final_worktree_diff"],
        },
    }
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
    return config_path


def _benchmark_definition(task_id: str, split: str, category: str, difficulty: int, expected_value: str) -> dict:
    fixed_source = "def solve():\n    return {!r}\n".format(expected_value)
    buggy_source = "def solve():\n    return 'bad'\n"
    return {
        "task_id": task_id,
        "split": split,
        "category": category,
        "difficulty": difficulty,
        "expected_value": expected_value,
        "buggy_source": buggy_source,
        "fixed_source": fixed_source,
        "prompt": "Rewrite src/app.py so solve() returns {!r}.".format(expected_value),
    }


def _test_source(expected_value: str) -> str:
    return (
        "import unittest\n\n"
        "from src.app import solve\n\n\n"
        "class VisibleTest(unittest.TestCase):\n"
        "    def test_value(self):\n"
        "        self.assertEqual(solve(), {!r})\n".format(expected_value)
    )
