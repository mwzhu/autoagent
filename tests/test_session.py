import tempfile
import unittest
from pathlib import Path

from superagent.report import generate_markdown_report
from superagent.session import (
    agent_accept,
    agent_checkout_parent,
    agent_evaluate,
    agent_failures,
    agent_revert,
    init_agent_session,
)
from superagent.storage import load_session_state, session_paths
from superagent.utils import read_json
from tests.helpers import copy_fixture_repo, write_dataset, write_run_config, write_tiny_benchmark


class SessionTests(unittest.TestCase):
    def test_dataset_session_accept_revert_and_report_holdout(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            repo_root = copy_fixture_repo(root / "repo")
            dataset_path = write_dataset(root / "dataset.jsonl")
            config_path = write_run_config(
                root / "config.yaml",
                repo_root,
                {
                    "backend": "dataset",
                    "dataset_path": str(dataset_path),
                    "scorer_type": "exact_match",
                    "min_train_delta": 1.0,
                    "max_guard_regression": 1.0,
                    "output_mode": "files",
                    "output_file": "response.txt",
                },
            )
            run_dir = init_agent_session(config_path, root / "run")
            (run_dir / "mode.txt").write_text("correct\n", encoding="utf-8")
            evaluation = agent_evaluate(run_dir)
            self.assertEqual(evaluation["verdict"], "eligible_for_accept")
            accepted = agent_accept(run_dir)
            self.assertEqual(accepted["accepted_candidate_id"], "cand_0001")
            (run_dir / "mode.txt").write_text("wrong\n", encoding="utf-8")
            agent_revert(run_dir)
            self.assertEqual((run_dir / "mode.txt").read_text(encoding="utf-8").strip(), "correct")
            report_path = generate_markdown_report(run_dir)
            self.assertTrue(report_path.exists())
            holdout_summary = read_json(run_dir / ".superagent" / "holdout_summary.json")
            self.assertEqual(holdout_summary["current_baseline"]["score"], 1.0)
            self.assertEqual(holdout_summary["best_accepted"]["score"], 1.0)

    def test_accept_fails_if_workspace_changes_after_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            repo_root = copy_fixture_repo(root / "repo")
            dataset_path = write_dataset(root / "dataset.jsonl")
            config_path = write_run_config(
                root / "config.yaml",
                repo_root,
                {
                    "backend": "dataset",
                    "dataset_path": str(dataset_path),
                    "scorer_type": "exact_match",
                    "min_train_delta": 1.0,
                    "max_guard_regression": 1.0,
                    "output_mode": "files",
                    "output_file": "response.txt",
                },
            )
            run_dir = init_agent_session(config_path, root / "run")
            (run_dir / "mode.txt").write_text("correct\n", encoding="utf-8")
            evaluation = agent_evaluate(run_dir)
            self.assertEqual(evaluation["verdict"], "eligible_for_accept")
            (run_dir / "mode.txt").write_text("wrong\n", encoding="utf-8")
            with self.assertRaises(AssertionError):
                agent_accept(run_dir)

    def test_archive_pruning_preserves_only_top_active_parents(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            repo_root = copy_fixture_repo(root / "repo")
            dataset_path = write_dataset(root / "dataset.jsonl")
            config_path = write_run_config(
                root / "config.yaml",
                repo_root,
                {
                    "backend": "dataset",
                    "dataset_path": str(dataset_path),
                    "scorer_type": "exact_match",
                    "min_train_delta": 0.0,
                    "max_guard_regression": 0.0,
                    "output_mode": "files",
                    "output_file": "response.txt",
                },
            )
            run_dir = init_agent_session(config_path, root / "run")
            (run_dir / "mode.txt").write_text("train_only\n", encoding="utf-8")
            self.assertEqual(agent_evaluate(run_dir)["verdict"], "eligible_for_accept")
            agent_accept(run_dir)
            (run_dir / "mode.txt").write_text("correct\n", encoding="utf-8")
            self.assertEqual(agent_evaluate(run_dir)["verdict"], "eligible_for_accept")
            agent_accept(run_dir)
            state = load_session_state(session_paths(run_dir))
            self.assertNotIn("baseline", state.active_archive_ids)
            self.assertIn("cand_0001", state.active_archive_ids)
            self.assertIn("cand_0002", state.active_archive_ids)
            with self.assertRaises(AssertionError):
                agent_checkout_parent(run_dir, "baseline")
            agent_checkout_parent(run_dir, "cand_0001")
            self.assertEqual((run_dir / "mode.txt").read_text(encoding="utf-8").strip(), "train_only")

    def test_denylist_changes_are_blocked_and_failures_are_exposed(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            repo_root = copy_fixture_repo(root / "repo")
            dataset_path = write_dataset(root / "dataset.jsonl")
            config_path = write_run_config(
                root / "config.yaml",
                repo_root,
                {
                    "backend": "dataset",
                    "dataset_path": str(dataset_path),
                    "scorer_type": "exact_match",
                    "min_train_delta": 1.0,
                    "max_guard_regression": 1.0,
                    "output_mode": "files",
                    "output_file": "response.txt",
                },
            )
            run_dir = init_agent_session(config_path, root / "run")
            (run_dir / ".env").write_text("SECRET=1\n", encoding="utf-8")
            blocked = agent_evaluate(run_dir)
            self.assertEqual(blocked["verdict"], "integrity_blocked")
            self.assertIn("blocking:denylist:.env", blocked["failure_summary"]["integrity_flags"])

            (run_dir / ".env").unlink()
            (run_dir / "mode.txt").write_text("different_wrong\n", encoding="utf-8")
            failed = agent_evaluate(run_dir)
            self.assertEqual(failed["verdict"], "rejected_train")
            diagnostics = agent_failures(run_dir, failed["candidate_id"])
            self.assertTrue(diagnostics["attempts"][0]["task_diagnostics"])
            self.assertTrue(diagnostics["failure_summary"]["failing_tasks"])

    def test_code_benchmark_workspace_mode_runs_install_once(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            repo_root = copy_fixture_repo(root / "repo")
            benchmark_dir = write_tiny_benchmark(root / "benchmark")
            config_path = write_run_config(
                root / "config.yaml",
                repo_root,
                {
                    "backend": "code_benchmark",
                    "benchmark_dir": str(benchmark_dir),
                    "min_train_delta_tasks": 1,
                    "max_guard_regression_tasks": 1,
                    "output_mode": "workspace",
                },
            )
            run_dir = init_agent_session(config_path, root / "run")
            (run_dir / "mode.txt").write_text("correct\n", encoding="utf-8")
            result = agent_evaluate(run_dir)
            self.assertEqual(result["verdict"], "eligible_for_accept")
            install_counter = run_dir / ".superagent" / "evaluations" / "cand_0001" / "repo" / "install_counter.txt"
            self.assertEqual(install_counter.read_text(encoding="utf-8").strip(), "1")


if __name__ == "__main__":
    unittest.main()
