import unittest
from pathlib import Path

from superagent.adapters import get_agent_adapter
from superagent.config import load_run_config
from superagent.evals import get_eval_backend
from superagent.models import ConfigChange


class ContractTests(unittest.TestCase):
    def test_adapters_expose_required_interface(self):
        config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml")
        for adapter_name in ("builtin", "simple_coder", "mini_swe_agent"):
            adapter = get_agent_adapter(adapter_name)
            if adapter_name == "builtin":
                adapter_config = config.agent.config
            elif adapter_name == "simple_coder":
                adapter_config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.local.yaml").agent.config
            else:
                adapter_config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.miniswe.yaml").agent.config
            self.assertTrue(adapter.name)
            self.assertIsInstance(adapter.mutable_paths(adapter_config), list)
            self.assertIsInstance(adapter.mutation_context(adapter_config), dict)

    def test_eval_backends_expose_required_interface(self):
        builtin_config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml")
        dataset_config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "dataset.demo.yaml")
        for backend_name, eval_config in (
            ("code_benchmark", builtin_config.eval.config),
            ("dataset", dataset_config.eval.config),
        ):
            backend = get_eval_backend(backend_name)
            self.assertTrue(backend.name)
            self.assertIsInstance(backend.validate(eval_config), dict)

    def test_unknown_mutation_paths_fail_immediately(self):
        config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "agent.builtin.yaml")
        adapter = get_agent_adapter(config.agent.adapter)
        with self.assertRaises(AssertionError):
            config.apply_agent_changes(
                [ConfigChange(path="unknown.path", value=True)],
                adapter.mutable_paths(config.agent.config),
            )

    def test_dataset_backend_optimizer_demo_runs(self):
        config = load_run_config(Path(__file__).resolve().parents[1] / "examples" / "dataset.demo.yaml")
        backend = get_eval_backend(config.eval.backend)
        tasks = backend.load_tasks(config.eval.config)
        self.assertEqual([task.task_id for task in tasks], ["greet_train", "planet_guard", "color_holdout"])
        splits = backend.split_tasks(tasks)
        self.assertEqual(len(splits["train"]), 1)
        self.assertEqual(len(splits["guard"]), 1)
        self.assertEqual(len(splits["holdout"]), 1)


if __name__ == "__main__":
    unittest.main()
