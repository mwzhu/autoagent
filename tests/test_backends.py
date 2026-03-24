import tempfile
import unittest
from pathlib import Path

from superagent.adapters import get_agent_adapter
from superagent.benchmark import build_benchmark
from superagent.config import BuiltinProviderConfig, CodeBenchmarkEvalConfig, DatasetEvalConfig, load_run_config
from superagent.evals import get_eval_backend
from superagent.models import AgentResult, CommandRecord
from superagent.runner import evaluate_task


class BackendTests(unittest.TestCase):
    def test_code_backend_hides_hidden_tests_in_prepared_workspace(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            backend = get_eval_backend("code_benchmark")
            task = backend.load_tasks(CodeBenchmarkEvalConfig(benchmark_dir=str(benchmark_dir)))[0]
            run_input = backend.prepare_run(task, "cand", root / "run")
            self.assertTrue((run_input.working_dir / "tests" / "visible").exists())
            self.assertFalse((run_input.working_dir / "tests" / "hidden").exists())

    def test_code_backend_blocks_test_edits(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            backend = get_eval_backend("code_benchmark")
            task = backend.load_tasks(CodeBenchmarkEvalConfig(benchmark_dir=str(benchmark_dir)))[0]
            run_input = backend.prepare_run(task, "cand", root / "run")
            result = backend.score_task(
                task,
                run_input,
                AgentResult(
                    status="completed",
                    final_message="x",
                    files_written=["tests/visible/test_visible.py"],
                    commands=[],
                    stdout="",
                    stderr="",
                    patch_diff="",
                    cost_usd=0.0,
                    duration_seconds=0.0,
                ),
                evaluate_hidden=True,
            )
            self.assertIn("blocking:test_edit_attempt", result.integrity_flags)
            self.assertFalse(result.passed)

    def test_dataset_backend_exact_match_and_python_function_scoring(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            dataset_path = root / "dataset.jsonl"
            dataset_path.write_text(
                '{"id":"t1","split":"train","prompt":"say hi","expected_output":"hi"}\n',
                encoding="utf-8",
            )
            backend = get_eval_backend("dataset")
            exact_tasks = backend.load_tasks(DatasetEvalConfig(dataset_path=str(dataset_path), scorer_type="exact_match"))
            run_input = backend.prepare_run(exact_tasks[0], "cand", root / "run_exact")
            (run_input.working_dir / "response.txt").write_text("hi\n", encoding="utf-8")
            exact_result = backend.score_task(
                exact_tasks[0],
                run_input,
                AgentResult("completed", "ok", ["response.txt"], [], "", "", "", 0.0, 0.0),
                evaluate_hidden=False,
            )
            self.assertTrue(exact_result.passed)

            scorer_path = root / "scorer.py"
            scorer_path.write_text(
                "def score(actual_output, expected_output, task):\n"
                "    return actual_output.strip() == expected_output.strip()[::-1]\n",
                encoding="utf-8",
            )
            python_tasks = backend.load_tasks(
                DatasetEvalConfig(
                    dataset_path=str(dataset_path),
                    scorer_type="python_function",
                    scorer_path=str(scorer_path),
                    scorer_function="score",
                )
            )
            python_run_input = backend.prepare_run(python_tasks[0], "cand2", root / "run_python")
            (python_run_input.working_dir / "response.txt").write_text("ih", encoding="utf-8")
            python_result = backend.score_task(
                python_tasks[0],
                python_run_input,
                AgentResult("completed", "ok", ["response.txt"], [], "", "", "", 0.0, 0.0),
                evaluate_hidden=False,
            )
            self.assertTrue(python_result.passed)

    def test_simple_coder_and_mini_adapter_both_run_on_code_backend(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            backend = get_eval_backend("code_benchmark")
            task = backend.load_tasks(CodeBenchmarkEvalConfig(benchmark_dir=str(benchmark_dir)))[0]

            simple_config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.local.yaml")
            simple_config.eval.config.benchmark_dir = str(benchmark_dir)
            simple_config.agent.config.task_provider = BuiltinProviderConfig(provider_type="builtin", model="builtin-task")
            simple_result = evaluate_task(
                simple_config,
                get_agent_adapter("simple_coder"),
                backend,
                task,
                "simple",
                root / "simple_run",
                evaluate_hidden=False,
            )
            self.assertTrue(Path(simple_result.receipt_path).exists())

            mini_config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.miniswe.yaml")
            mini_config.eval.config.benchmark_dir = str(benchmark_dir)
            mini_config.agent.config.command = (
                "python3 -c \"from pathlib import Path; p=Path('src/app.py'); p.write_text(p.read_text())\""
            )
            mini_result = evaluate_task(
                mini_config,
                get_agent_adapter("mini_swe_agent"),
                backend,
                task,
                "mini",
                root / "mini_run",
                evaluate_hidden=False,
            )
            self.assertTrue(Path(mini_result.receipt_path).exists())


if __name__ == "__main__":
    unittest.main()
