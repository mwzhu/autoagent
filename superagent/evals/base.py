"""Shared evaluation backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List

from superagent.config import EvalConfig
from superagent.models import AgentResult, AgentRunInput, EvalTask, TaskResult


class EvalBackend(ABC):
    name: str

    @abstractmethod
    def load_tasks(self, eval_config: EvalConfig) -> List[EvalTask]:
        raise NotImplementedError

    @abstractmethod
    def split_tasks(self, tasks: List[EvalTask]) -> Dict[str, List[EvalTask]]:
        raise NotImplementedError

    @abstractmethod
    def prepare_run(self, task: EvalTask, candidate_id: str, output_dir: Path) -> AgentRunInput:
        raise NotImplementedError

    @abstractmethod
    def score_task(
        self,
        task: EvalTask,
        run_input: AgentRunInput,
        agent_result: AgentResult,
        evaluate_hidden: bool,
    ) -> TaskResult:
        raise NotImplementedError

    @abstractmethod
    def aggregate(self, results: List[TaskResult], split: str, eval_config: EvalConfig) -> float:
        raise NotImplementedError

    @abstractmethod
    def validate(self, eval_config: EvalConfig) -> Dict[str, object]:
        raise NotImplementedError
