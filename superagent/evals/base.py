"""Shared evaluation backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List

from superagent.config import EntryContractConfig, EvalConfig
from superagent.models import CommandRecord, EvalTask, TaskResult


class EvalBackend(ABC):
    name: str

    @abstractmethod
    def load_tasks(self, eval_config: EvalConfig) -> List[EvalTask]:
        raise NotImplementedError

    @abstractmethod
    def split_tasks(self, tasks: List[EvalTask]) -> Dict[str, List[EvalTask]]:
        raise NotImplementedError

    @abstractmethod
    def public_task_payload(self, task: EvalTask) -> Dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def prepare_task_workspace(self, task: EvalTask, workspace_dir: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def score_task(
        self,
        task: EvalTask,
        workspace_dir: Path,
        output_dir: Path,
        entry_contract: EntryContractConfig,
        command_records: List[CommandRecord],
        changed_files: List[str],
        evaluate_hidden: bool,
    ) -> TaskResult:
        raise NotImplementedError

    @abstractmethod
    def aggregate(self, results: List[TaskResult], split: str, eval_config: EvalConfig) -> float:
        raise NotImplementedError

    @abstractmethod
    def validate(self, eval_config: EvalConfig) -> Dict[str, object]:
        raise NotImplementedError
