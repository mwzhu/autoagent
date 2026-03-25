"""Dataset-backed evaluation backend."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Dict, List

from superagent.config import DatasetEvalConfig, EntryContractConfig, EvalConfig
from superagent.evals.base import EvalBackend
from superagent.models import CommandRecord, EvalTask, TaskResult


_DATASET_RESERVED_KEYS = {"id", "split", "prompt", "expected_output", "public_fields"}


class DatasetBackend(EvalBackend):
    name = "dataset"

    def __init__(self) -> None:
        self.eval_config: DatasetEvalConfig | None = None

    def load_tasks(self, eval_config: EvalConfig) -> List[EvalTask]:
        assert isinstance(eval_config, DatasetEvalConfig), "DatasetBackend requires DatasetEvalConfig."
        self.eval_config = eval_config
        tasks: List[EvalTask] = []
        with Path(eval_config.dataset_path).open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                public_fields = row.get("public_fields")
                if public_fields is None:
                    public_fields = {key: value for key, value in row.items() if key not in _DATASET_RESERVED_KEYS}
                assert isinstance(public_fields, dict), "dataset public_fields must be a mapping when provided."
                tasks.append(
                    EvalTask(
                        task_id=row["id"],
                        split=row["split"],
                        prompt=row["prompt"],
                        category=str(public_fields.get("category", row.get("category", "default"))),
                        difficulty=int(public_fields.get("difficulty", row.get("difficulty", 0))),
                        expected_output=row["expected_output"],
                        public_fields=public_fields,
                        metadata={"row": row},
                    )
                )
        return tasks

    def split_tasks(self, tasks: List[EvalTask]) -> Dict[str, List[EvalTask]]:
        grouped = {"train": [], "guard": [], "holdout": []}
        for task in tasks:
            grouped[task.split].append(task)
        return grouped

    def public_task_payload(self, task: EvalTask) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "task_id": task.task_id,
            "split": task.split,
            "prompt": task.prompt,
        }
        payload.update(task.public_fields)
        return payload

    def prepare_task_workspace(self, task: EvalTask, workspace_dir: Path) -> None:
        del task
        if workspace_dir.exists():
            for child in workspace_dir.iterdir():
                if child.is_dir():
                    import shutil

                    shutil.rmtree(child)
                else:
                    child.unlink()
        else:
            workspace_dir.mkdir(parents=True, exist_ok=True)

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
        del workspace_dir
        del evaluate_hidden
        assert entry_contract.output_file, "Dataset scoring requires output_file."
        output_path = output_dir / entry_contract.output_file
        actual_output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        assert self.eval_config is not None, "DatasetBackend.load_tasks must be called before score_task."
        passed = _dataset_score_output(self.eval_config, task, actual_output)
        integrity_flags: List[str] = []
        unexpected_changes = [
            path for path in changed_files if path != "output/" + entry_contract.output_file and not path.startswith("repo/")
        ]
        if unexpected_changes:
            integrity_flags.append("blocking:unexpected_dataset_write")
            passed = False
        mismatch_summary = ""
        if not passed:
            mismatch_summary = "expected={} actual={}".format(
                task.expected_output.strip(),
                actual_output.strip(),
            )
        hidden_result = "not_run" if task.split == "train" else ("passed" if passed else "failed")
        return TaskResult(
            task_id=task.task_id,
            split=task.split,
            passed=passed,
            score=1.0 if passed else 0.0,
            visible_passed=passed,
            hidden_result=hidden_result,
            integrity_flags=integrity_flags,
            commands=list(command_records),
            changed_files=changed_files,
            stdout_summary=_last_summary(command_records, "stdout"),
            stderr_summary=_last_summary(command_records, "stderr"),
            mismatch_summary=mismatch_summary,
        )

    def aggregate(self, results: List[TaskResult], split: str, eval_config: EvalConfig) -> float:
        del eval_config
        if split == "train":
            return float(sum(1 for result in results if result.split == "train" and result.passed))
        return float(sum(1 for result in results if result.split == split and result.hidden_result == "passed"))

    def validate(self, eval_config: EvalConfig) -> Dict[str, object]:
        assert isinstance(eval_config, DatasetEvalConfig), "DatasetBackend requires DatasetEvalConfig."
        self.eval_config = eval_config
        tasks = self.load_tasks(eval_config)
        counts = self.split_tasks(tasks)
        detail: Dict[str, object] = {
            "task_count": len(tasks),
            "train_count": len(counts["train"]),
            "guard_count": len(counts["guard"]),
            "holdout_count": len(counts["holdout"]),
            "scorer_type": eval_config.scorer_type,
        }
        if eval_config.scorer_type == "python_function":
            detail["scorer_path"] = eval_config.scorer_path
            detail["scorer_function"] = eval_config.scorer_function
        return detail


def _dataset_score_output(
    eval_config: DatasetEvalConfig,
    task: EvalTask,
    actual_output: str,
) -> bool:
    if eval_config.scorer_type == "exact_match":
        return actual_output.strip() == task.expected_output.strip()
    scorer = _load_python_scorer(eval_config)
    try:
        outcome = scorer(actual_output=actual_output, expected_output=task.expected_output, task=task.to_dict())
    except TypeError:
        outcome = scorer(actual_output, task.expected_output, task.to_dict())
    if isinstance(outcome, bool):
        return outcome
    if isinstance(outcome, (int, float)):
        return bool(outcome)
    raise AssertionError("Dataset scorer must return bool, int, or float.")


def _load_python_scorer(eval_config: DatasetEvalConfig):
    assert eval_config.scorer_path, "Python-function scoring requires scorer_path."
    assert eval_config.scorer_function, "Python-function scoring requires scorer_function."
    scorer_path = Path(eval_config.scorer_path)
    spec = importlib.util.spec_from_file_location("superagent_dataset_scorer", scorer_path)
    assert spec and spec.loader, "Unable to load scorer module from {}".format(scorer_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, eval_config.scorer_function)


def _last_summary(command_records: List[CommandRecord], field_name: str) -> str:
    if not command_records:
        return ""
    value = getattr(command_records[-1], field_name)
    return " ".join(value.strip().split())[:240]
