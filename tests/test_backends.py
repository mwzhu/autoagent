import tempfile
import unittest
from pathlib import Path

from superagent.benchmark import build_benchmark
from superagent.config import CodeBenchmarkEvalConfig, DatasetEvalConfig, EntryContractConfig
from superagent.evals import get_eval_backend
from superagent.models import CommandRecord


class BackendTests(unittest.TestCase):
    def test_code_backend_prepares_workspace_without_hidden_tests(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            backend = get_eval_backend("code_benchmark")
            task = backend.load_tasks(CodeBenchmarkEvalConfig(backend="code_benchmark", benchmark_dir=str(benchmark_dir)))[0]
            workspace_dir = root / "workspace"
            backend.prepare_task_workspace(task, workspace_dir)
            self.assertTrue((workspace_dir / "tests" / "visible").exists())
            self.assertFalse((workspace_dir / "tests" / "hidden").exists())

    def test_code_backend_blocks_test_edits(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            benchmark_dir = build_benchmark(root / "benchmark")
            backend = get_eval_backend("code_benchmark")
            task = backend.load_tasks(CodeBenchmarkEvalConfig(backend="code_benchmark", benchmark_dir=str(benchmark_dir)))[0]
            workspace_dir = root / "workspace"
            backend.prepare_task_workspace(task, workspace_dir)
            result = backend.score_task(
                task=task,
                workspace_dir=workspace_dir,
                output_dir=root / "output",
                entry_contract=EntryContractConfig(input_file="task.json", output_mode="workspace"),
                command_records=[
                    CommandRecord(
                        command="python agent.py",
                        exit_code=0,
                        stdout="",
                        stderr="",
                        start_time="x",
                        end_time="y",
                    )
                ],
                changed_files=["workspace/tests/visible/test_visible.py"],
                evaluate_hidden=True,
            )
            self.assertIn("blocking:test_edit_attempt", result.integrity_flags)
            self.assertFalse(result.passed)

    def test_dataset_backend_exact_match_and_python_function_scoring(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            root = Path(tmp_root)
            dataset_path = root / "dataset.jsonl"
            dataset_path.write_text(
                '{"id":"t1","split":"train","prompt":"say hi","expected_output":"hi","public_fields":{"public_answer":"hi"}}\n',
                encoding="utf-8",
            )
            backend = get_eval_backend("dataset")
            exact_tasks = backend.load_tasks(
                DatasetEvalConfig(backend="dataset", dataset_path=str(dataset_path), scorer_type="exact_match")
            )
            output_dir = root / "output"
            output_dir.mkdir()
            (output_dir / "response.txt").write_text("hi\n", encoding="utf-8")
            exact_result = backend.score_task(
                task=exact_tasks[0],
                workspace_dir=root / "workspace",
                output_dir=output_dir,
                entry_contract=EntryContractConfig(input_file="task.json", output_mode="files", output_file="response.txt"),
                command_records=[],
                changed_files=["output/response.txt"],
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
                    backend="dataset",
                    dataset_path=str(dataset_path),
                    scorer_type="python_function",
                    scorer_path=str(scorer_path),
                    scorer_function="score",
                )
            )
            (output_dir / "response.txt").write_text("ih", encoding="utf-8")
            python_result = backend.score_task(
                task=python_tasks[0],
                workspace_dir=root / "workspace",
                output_dir=output_dir,
                entry_contract=EntryContractConfig(input_file="task.json", output_mode="files", output_file="response.txt"),
                command_records=[],
                changed_files=["output/response.txt"],
                evaluate_hidden=False,
            )
            self.assertTrue(python_result.passed)


if __name__ == "__main__":
    unittest.main()
