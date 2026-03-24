"""Code benchmark compatibility helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from superagent.config import CodeBenchmarkEvalConfig
from superagent.evals.code_benchmark import (
    CodeBenchmarkBackend,
    build_benchmark,
    default_benchmark_dir,
    run_benchmark_command,
    validate_benchmark,
    validate_task,
)
from superagent.models import CommandRecord, EvalTask


def load_tasks(benchmark_dir: Path) -> List[EvalTask]:
    backend = CodeBenchmarkBackend()
    return backend.load_tasks(CodeBenchmarkEvalConfig(benchmark_dir=str(benchmark_dir)))


def split_tasks(tasks: List[EvalTask]) -> Dict[str, List[EvalTask]]:
    return CodeBenchmarkBackend().split_tasks(tasks)


__all__ = [
    "CommandRecord",
    "build_benchmark",
    "default_benchmark_dir",
    "load_tasks",
    "run_benchmark_command",
    "split_tasks",
    "validate_benchmark",
    "validate_task",
]
