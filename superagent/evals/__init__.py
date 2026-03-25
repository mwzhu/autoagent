"""Eval backends."""

from superagent.evals.base import EvalBackend
from superagent.evals.code_benchmark import (
    CodeBenchmarkBackend,
    build_benchmark,
    default_benchmark_dir,
    validate_benchmark,
    validate_task,
)
from superagent.evals.dataset import DatasetBackend
from superagent.utils import run_shell_command

run_benchmark_command = run_shell_command


def get_eval_backend(name: str) -> EvalBackend:
    if name == "code_benchmark":
        return CodeBenchmarkBackend()
    if name == "dataset":
        return DatasetBackend()
    raise AssertionError("Unsupported eval backend: {}".format(name))

__all__ = [
    "CodeBenchmarkBackend",
    "DatasetBackend",
    "EvalBackend",
    "build_benchmark",
    "default_benchmark_dir",
    "get_eval_backend",
    "run_benchmark_command",
    "validate_benchmark",
    "validate_task",
]
