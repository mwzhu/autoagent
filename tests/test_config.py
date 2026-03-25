import tempfile
import unittest
from pathlib import Path

import yaml

from superagent.config import load_run_config
from tests.helpers import copy_fixture_repo, write_dataset, write_tiny_benchmark


class ConfigTests(unittest.TestCase):
    def test_full_repo_config_loads_and_expands(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            repo_root = copy_fixture_repo(root / "repo")
            dataset_path = write_dataset(root / "dataset.jsonl")
            config_path = root / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "agent": {
                            "repo_root": str(repo_root),
                            "run_command": "python agent.py",
                            "entry_contract": {"input_file": "task.json", "output_mode": "files", "output_file": "response.txt"},
                            "mutation_boundary": {"type": "full_repo"},
                        },
                        "eval": {"backend": "dataset", "dataset_path": str(dataset_path)},
                        "policy": {
                            "screening_sample_size": 1,
                            "archive_size": 2,
                            "rerun_borderline_accepts": True,
                            "max_evaluations": 5,
                            "max_accepts": 5,
                            "max_task_cost_usd": 10,
                            "max_wall_clock_hours": 1,
                        },
                        "guards": {"forbidden_commands": [], "no_network": True, "receipt_requirements": []},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            config = load_run_config(config_path)
            self.assertEqual(config.agent.mutation_boundary.mutable_roots, ["."])
            self.assertEqual(config.agent.mutation_boundary.protected_roots, [])

    def test_overlapping_mutable_and_protected_roots_fail(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            repo_root = copy_fixture_repo(root / "repo")
            dataset_path = write_dataset(root / "dataset.jsonl")
            config_path = root / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "agent": {
                            "repo_root": str(repo_root),
                            "run_command": "python agent.py",
                            "entry_contract": {"input_file": "task.json", "output_mode": "files", "output_file": "response.txt"},
                            "mutation_boundary": {
                                "type": "scoped_roots",
                                "mutable_roots": ["src"],
                                "protected_roots": ["src/private"],
                            },
                        },
                        "eval": {"backend": "dataset", "dataset_path": str(dataset_path)},
                        "policy": {
                            "screening_sample_size": 1,
                            "archive_size": 2,
                            "rerun_borderline_accepts": True,
                            "max_evaluations": 5,
                            "max_accepts": 5,
                            "max_task_cost_usd": 10,
                            "max_wall_clock_hours": 1,
                        },
                        "guards": {"forbidden_commands": [], "no_network": True, "receipt_requirements": []},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(AssertionError):
                load_run_config(config_path)

    def test_output_mode_mismatch_fails_immediately(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            repo_root = copy_fixture_repo(root / "repo")
            benchmark_dir = write_tiny_benchmark(root / "benchmark")
            config_path = root / "config.yaml"
            config_path.write_text(
                yaml.safe_dump(
                    {
                        "agent": {
                            "repo_root": str(repo_root),
                            "run_command": "python agent.py",
                            "entry_contract": {"input_file": "task.json", "output_mode": "files", "output_file": "response.txt"},
                            "mutation_boundary": {"type": "full_repo"},
                        },
                        "eval": {"backend": "code_benchmark", "benchmark_dir": str(benchmark_dir)},
                        "policy": {
                            "screening_sample_size": 1,
                            "archive_size": 2,
                            "rerun_borderline_accepts": True,
                            "max_evaluations": 5,
                            "max_accepts": 5,
                            "max_task_cost_usd": 10,
                            "max_wall_clock_hours": 1,
                        },
                        "guards": {"forbidden_commands": [], "no_network": True, "receipt_requirements": []},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(AssertionError):
                load_run_config(config_path)


if __name__ == "__main__":
    unittest.main()
