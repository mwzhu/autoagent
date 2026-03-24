import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from superagent.benchmark import build_benchmark
from superagent.config import load_run_config
from superagent.models import CandidateAttempt, MutationProposal, ProviderUsage, ConfigChange
from superagent.optimizer import run_optimization
from superagent.report import generate_markdown_report
from superagent.storage import fetch_candidates, fetch_run


class OptimizerTests(unittest.TestCase):
    def test_screening_sample_is_fixed_and_run_generates_report(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml")
            config.eval.config.benchmark_dir = str(benchmark_dir)
            config.optimizer.max_iterations = 4
            config.optimizer.max_accepts = 1
            run_dir = root / "run"
            run_optimization(
                config=config,
                config_path=Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml",
                output_dir=run_dir,
            )
            connection = sqlite3.connect(str(run_dir / "run.sqlite3"))
            candidates = fetch_candidates(connection)
            connection.close()
            self.assertGreaterEqual(len(candidates), 2)
            baseline = candidates[0]
            best = max(candidates, key=lambda row: (row["train_score"], row["guard_score"]))
            self.assertGreaterEqual(best["train_score"], baseline["train_score"])
            report_path = generate_markdown_report(run_dir)
            self.assertTrue(report_path.exists())
            report_text = report_path.read_text(encoding="utf-8")
            self.assertIn("Adapter:", report_text)
            self.assertIn("Backend:", report_text)
            self.assertIn("Duplicate skips:", report_text)
            self.assertIn("Meta-agent cost (USD):", report_text)
            self.assertIn("Task-agent cost (USD):", report_text)
            self.assertIn("Confirmation rerun:", report_text)

    def test_duplicate_mutations_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml")
            config.eval.config.benchmark_dir = str(benchmark_dir)
            config.optimizer.max_iterations = 2
            config.optimizer.max_accepts = 1
            config.optimizer.duplicate_retry_limit = 2
            proposal = MutationProposal(
                mutation_type="system_prompt_edit",
                reason="Edit prompt only.",
                changes=[ConfigChange(path="system_prompt", value="Prompt variant")],
            )
            with mock.patch(
                "superagent.optimizer.propose_mutation",
                side_effect=lambda *args, **kwargs: (proposal, ProviderUsage()),
            ):
                run_dir = root / "run"
                run_optimization(
                    config=config,
                    config_path=Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml",
                    output_dir=run_dir,
                )
            connection = sqlite3.connect(str(run_dir / "run.sqlite3"))
            run = fetch_run(connection)
            candidates = fetch_candidates(connection)
            connection.close()
            self.assertEqual(len(candidates), 2)
            self.assertGreaterEqual(run["duplicate_skip_count"], 1)

    def test_borderline_candidates_trigger_confirmation_rerun(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml")
            config.eval.config.benchmark_dir = str(benchmark_dir)
            config.optimizer.max_iterations = 1
            config.optimizer.max_accepts = 1
            proposal = MutationProposal(
                mutation_type="planning_toggle",
                reason="Enable planning.",
                changes=[ConfigChange(path="orchestration.planning", value=True)],
            )

            def fake_attempt(*args, **kwargs):
                candidate_id = kwargs["candidate_id"]
                if candidate_id == "baseline":
                    return CandidateAttempt(
                        attempt_id="baseline",
                        sample_score=2.0,
                        train_score=10.0,
                        guard_score=6.0,
                        integrity_blocked=False,
                        audit_blocked=False,
                        wall_clock_seconds=0.01,
                    )
                return CandidateAttempt(
                    attempt_id=candidate_id,
                    sample_score=2.0,
                    train_score=11.0,
                    guard_score=5.0,
                    integrity_blocked=False,
                    audit_blocked=False,
                    wall_clock_seconds=0.01,
                )

            with mock.patch(
                "superagent.optimizer.propose_mutation",
                side_effect=lambda *args, **kwargs: (proposal, ProviderUsage()),
            ), mock.patch(
                "superagent.optimizer.evaluate_candidate_attempt",
                side_effect=fake_attempt,
            ), mock.patch(
                "superagent.optimizer.evaluate_holdout",
                return_value={"candidate_id": "x", "score": 0, "task_results": []},
            ):
                run_dir = root / "run"
                run_optimization(
                    config=config,
                    config_path=Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml",
                    output_dir=run_dir,
                )
            connection = sqlite3.connect(str(run_dir / "run.sqlite3"))
            candidates = fetch_candidates(connection)
            connection.close()
            candidate = candidates[-1]
            self.assertTrue(candidate["confirmation_rerun_required"])
            self.assertTrue(candidate["confirmation_rerun_passed"])
            self.assertEqual(len(candidate["attempt_ids"]), 2)

    def test_meta_budget_limit_stops_run_early(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml")
            config.eval.config.benchmark_dir = str(benchmark_dir)
            config.optimizer.max_iterations = 3
            config.optimizer.max_meta_api_cost_usd = 0.5
            proposal = MutationProposal(
                mutation_type="planning_toggle",
                reason="Enable planning.",
                changes=[ConfigChange(path="orchestration.planning", value=True)],
            )
            with mock.patch(
                "superagent.optimizer.propose_mutation",
                side_effect=lambda *args, **kwargs: (
                    proposal,
                    ProviderUsage(cost_usd=1.0),
                ),
            ):
                run_dir = root / "run"
                run_optimization(
                    config=config,
                    config_path=Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml",
                    output_dir=run_dir,
                )
            connection = sqlite3.connect(str(run_dir / "run.sqlite3"))
            candidates = fetch_candidates(connection)
            run = fetch_run(connection)
            connection.close()
            self.assertEqual(len(candidates), 1)
            self.assertGreater(run["cumulative_meta_cost_usd"], 0.5)

    def test_optimizer_runs_on_dataset_backend(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "dataset.demo.yaml")
            config.eval.config.dataset_path = str(Path(__file__).resolve().parents[1] / "examples" / "datasets" / "demo.jsonl")
            run_dir = root / "run"
            run_optimization(
                config=config,
                config_path=Path(__file__).resolve().parents[1] / "examples" / "dataset.demo.yaml",
                output_dir=run_dir,
            )
            connection = sqlite3.connect(str(run_dir / "run.sqlite3"))
            candidates = fetch_candidates(connection)
            connection.close()
            self.assertGreaterEqual(len(candidates), 1)


if __name__ == "__main__":
    unittest.main()
