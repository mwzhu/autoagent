"""Dataset-backed evaluation backend."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Dict, List

from superagent.config import DatasetEvalConfig, EvalConfig
from superagent.evals.base import EvalBackend
from superagent.models import AgentResult, AgentRunInput, EvalTask, TaskResult
from superagent.utils import ensure_dir


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
                tasks.append(
                    EvalTask(
                        task_id=row["id"],
                        split=row["split"],
                        prompt=row["prompt"],
                        expected_output=row["expected_output"],
                        metadata={"row": row},
                    )
                )
        return tasks

    def split_tasks(self, tasks: List[EvalTask]) -> Dict[str, List[EvalTask]]:
        grouped = {"train": [], "guard": [], "holdout": []}
        for task in tasks:
            grouped[task.split].append(task)
        return grouped

    def prepare_run(self, task: EvalTask, candidate_id: str, output_dir: Path) -> AgentRunInput:
        working_dir = output_dir / "workspaces" / candidate_id / task.task_id
        artifacts_dir = output_dir / "adapter_artifacts" / candidate_id / task.task_id
        ensure_dir(working_dir)
        ensure_dir(artifacts_dir)
        task_path = working_dir / "task.json"
        payload = {
            "id": task.task_id,
            "split": task.split,
            "prompt": task.prompt,
            "expected_output": task.expected_output,
        }
        task_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        prompt = task.prompt.rstrip() + "\nWrite the final answer to response.txt in the working directory."
        return AgentRunInput(
            task_id=task.task_id,
            prompt=prompt,
            working_dir=working_dir,
            artifacts_dir=artifacts_dir,
            budget_steps=0,
            metadata={"response_path": str(working_dir / "response.txt")},
        )

    def score_task(
        self,
        task: EvalTask,
        run_input: AgentRunInput,
        agent_result: AgentResult,
        evaluate_hidden: bool,
    ) -> TaskResult:
        del evaluate_hidden
        response_path = Path(str(run_input.metadata["response_path"]))
        actual_output = ""
        if response_path.exists():
            actual_output = response_path.read_text(encoding="utf-8")
        assert self.eval_config is not None, "DatasetBackend.load_tasks must be called before score_task."
        passed = _dataset_score_output(self.eval_config, task, actual_output, run_input, agent_result)
        integrity_flags = list(agent_result.integrity_flags)
        if any(Path(path).name != "response.txt" for path in agent_result.files_written):
            integrity_flags.append("blocking:unexpected_dataset_write")
            passed = False
        hidden_result = "not_run"
        if task.split != "train":
            hidden_result = "passed" if passed else "failed"
        return TaskResult(
            task_id=task.task_id,
            split=task.split,
            passed=passed,
            score=1.0 if passed else 0.0,
            visible_passed=passed,
            hidden_result=hidden_result,
            integrity_flags=sorted(set(integrity_flags)),
            commands=list(agent_result.commands),
            task_cost_usd=agent_result.cost_usd,
        )

    def aggregate(self, results: List[TaskResult], split: str, eval_config: EvalConfig) -> float:
        del eval_config
        return float(sum(1 for result in results if result.split == split and result.passed))

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
            assert eval_config.scorer_path, "Python-function scoring requires scorer_path."
            assert eval_config.scorer_function, "Python-function scoring requires scorer_function."
            detail["scorer_path"] = eval_config.scorer_path
            detail["scorer_function"] = eval_config.scorer_function
        return detail


def _dataset_score_output(
    eval_config: DatasetEvalConfig,
    task: EvalTask,
    actual_output: str,
    run_input: AgentRunInput,
    agent_result: AgentResult,
) -> bool:
    if eval_config.scorer_type == "exact_match":
        return actual_output.strip() == task.expected_output.strip()
    scorer = _load_python_scorer(eval_config)
    try:
        outcome = scorer(
            actual_output=actual_output,
            expected_output=task.expected_output,
            task=task.to_dict(),
            run_input=run_input.to_dict(),
            agent_result=agent_result.to_dict(),
        )
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
