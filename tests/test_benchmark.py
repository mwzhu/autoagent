import tempfile
import unittest
from collections import Counter
from pathlib import Path

from superagent.benchmark import build_benchmark, load_tasks, split_tasks, validate_benchmark


class BenchmarkTests(unittest.TestCase):
    def test_build_and_validate(self):
        with tempfile.TemporaryDirectory() as tmp_root:
            benchmark_dir = build_benchmark(Path(tmp_root) / "benchmark")
            validation = validate_benchmark(benchmark_dir)
            self.assertEqual(validation["task_count"], 32)
            self.assertEqual(validation["valid_count"], 32)
            tasks = load_tasks(benchmark_dir)
            splits = split_tasks(tasks)
            self.assertEqual(len(splits["train"]), 20)
            self.assertEqual(len(splits["guard"]), 6)
            self.assertEqual(len(splits["holdout"]), 6)
            category_counts = Counter(task.category for task in tasks)
            self.assertTrue(category_counts)


if __name__ == "__main__":
    unittest.main()
