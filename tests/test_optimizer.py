import sqlite3
import tempfile
import unittest
from pathlib import Path

from superagent.benchmark import build_benchmark
from superagent.config import load_agent_config
from superagent.optimizer import choose_screening_sample, run_optimization
from superagent.report import generate_markdown_report
from superagent.storage import fetch_candidates


class OptimizerTests(unittest.TestCase):
    def test_screening_sample_is_fixed_and_run_generates_report(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            config = load_agent_config(Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml")
            config.budget.max_iterations = 4
            config.budget.max_accepts = 1
            run_dir = root / "run"
            run_optimization(
                config=config,
                config_path=Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml",
                benchmark_dir=benchmark_dir,
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


if __name__ == "__main__":
    unittest.main()
