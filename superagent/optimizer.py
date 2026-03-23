"""Optimization loop."""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Dict, List

from superagent.audit import candidate_is_blocked, heuristic_audit
from superagent.benchmark import load_tasks, split_tasks
from superagent.config import AgentConfig, load_agent_config, save_agent_config
from superagent.models import CandidateEvaluation, EvalTask, TaskResult
from superagent.mutator import propose_mutation
from superagent.runner import evaluate_task
from superagent.storage import create_run_record, init_db, log_candidate
from superagent.utils import ensure_dir, write_json


def run_optimization(config: AgentConfig, config_path: Path, benchmark_dir: Path, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    ensure_dir(output_dir / "configs")
    ensure_dir(output_dir / "receipts")
    tasks = load_tasks(benchmark_dir)
    splits = split_tasks(tasks)
    screening_sample = choose_screening_sample(splits["train"], 8)
    run_id = output_dir.name
    connection = init_db(output_dir / "run.sqlite3")
    create_run_record(connection, run_id, str(benchmark_dir), str(config_path), [task.task_id for task in screening_sample])

    baseline_config_path = output_dir / "configs" / "baseline.yaml"
    save_agent_config(config, baseline_config_path)
    baseline = evaluate_candidate(
        candidate_id="baseline",
        parent_id="baseline",
        mutation_type="baseline",
        config=config,
        config_path=baseline_config_path,
        screening_sample=screening_sample,
        train_tasks=splits["train"],
        guard_tasks=splits["guard"],
        output_dir=output_dir,
        parent_sample_score=-1,
        parent_train_score=-1,
        parent_guard_score=0,
        full_train_required=True,
    )
    log_candidate(connection, run_id, baseline)

    accepted = [baseline]
    last_summary = {"candidate_id": "baseline", "train_score": baseline.train_score, "guard_score": baseline.guard_score}
    accept_count = 0
    holdout_checkpoints = []

    for iteration in range(config.budget.max_iterations):
        if accept_count >= config.budget.max_accepts:
            break
        parent = select_parent(accepted)
        parent_config = load_agent_config(Path(parent.config_path))
        proposal, _ = propose_mutation(parent_config, last_summary)
        candidate_config = parent_config.clone()
        candidate_config.apply_changes(proposal.changes)
        candidate_id = "cand_{:03d}".format(iteration + 1)
        candidate_config_path = output_dir / "configs" / (candidate_id + ".yaml")
        save_agent_config(candidate_config, candidate_config_path)
        candidate = evaluate_candidate(
            candidate_id=candidate_id,
            parent_id=parent.candidate_id,
            mutation_type=proposal.mutation_type,
            config=candidate_config,
            config_path=candidate_config_path,
            screening_sample=screening_sample,
            train_tasks=splits["train"],
            guard_tasks=splits["guard"],
            output_dir=output_dir,
            parent_sample_score=sample_score(parent.task_results, screening_sample),
            parent_train_score=parent.train_score,
            parent_guard_score=parent.guard_score,
        )
        log_candidate(connection, run_id, candidate)
        if accepted_candidate(candidate, parent):
            accepted.append(candidate)
            accepted = sort_archive(accepted)[:10]
            accept_count += 1
            last_summary = {
                "candidate_id": candidate.candidate_id,
                "train_score": candidate.train_score,
                "guard_score": candidate.guard_score,
                "audit_flags": candidate.audit_flags,
            }
            if accept_count % 10 == 0:
                holdout_checkpoints.append(
                    evaluate_holdout(
                        candidate_id=candidate.candidate_id + "_holdout_checkpoint",
                        config=candidate_config,
                        holdout_tasks=splits["holdout"],
                        output_dir=output_dir,
                    )
                )
    best = sort_archive(accepted)[0]
    best_config = load_agent_config(Path(best.config_path))
    holdout_summary = {
        "baseline": evaluate_holdout(
            candidate_id="baseline_holdout",
            config=config,
            holdout_tasks=splits["holdout"],
            output_dir=output_dir,
        ),
        "best": evaluate_holdout(
            candidate_id=best.candidate_id + "_holdout",
            config=best_config,
            holdout_tasks=splits["holdout"],
            output_dir=output_dir,
        ),
        "checkpoints": holdout_checkpoints,
    }
    write_json(output_dir / "holdout_summary.json", holdout_summary)
    connection.close()
    return output_dir


def evaluate_candidate(
    candidate_id: str,
    parent_id: str,
    mutation_type: str,
    config: AgentConfig,
    config_path: Path,
    screening_sample: List[EvalTask],
    train_tasks: List[EvalTask],
    guard_tasks: List[EvalTask],
    output_dir: Path,
    parent_sample_score: int,
    parent_train_score: int,
    parent_guard_score: int,
    full_train_required: bool = False,
) -> CandidateEvaluation:
    started = time.time()
    results: List[TaskResult] = []
    screening_task_ids = {task.task_id for task in screening_sample}
    for task in screening_sample:
        results.append(evaluate_task(config, task, candidate_id, output_dir, evaluate_hidden=False))
    screening_score = sample_score(results, screening_sample)
    if not full_train_required and screening_score < parent_sample_score:
        audit_flags = heuristic_audit([Path(result.receipt_path) for result in results if result.receipt_path])
        candidate = CandidateEvaluation(
            candidate_id=candidate_id,
            parent_id=parent_id,
            mutation_type=mutation_type,
            train_score=screening_score,
            guard_score=0,
            integrity_blocked=any(flag.startswith("blocking:") for flag in audit_flags),
            audit_blocked=False,
            wall_clock_seconds=time.time() - started,
            task_results=results,
            audit_flags=audit_flags,
            config_path=str(config_path),
        )
        candidate.audit_blocked = candidate_is_blocked(candidate)
        return candidate
    for task in train_tasks:
        if task.task_id in screening_task_ids:
            continue
        results.append(evaluate_task(config, task, candidate_id, output_dir, evaluate_hidden=False))
    train_score = sum(1 for result in results if result.split == "train" and result.visible_passed)
    guard_score = 0
    if full_train_required or train_score >= parent_train_score + 1:
        for task in guard_tasks:
            result = evaluate_task(config, task, candidate_id, output_dir, evaluate_hidden=True)
            results.append(result)
        guard_score = sum(1 for result in results if result.split == "guard" and result.hidden_result == "passed")
    audit_flags = heuristic_audit([Path(result.receipt_path) for result in results if result.receipt_path])
    candidate = CandidateEvaluation(
        candidate_id=candidate_id,
        parent_id=parent_id,
        mutation_type=mutation_type,
        train_score=train_score,
        guard_score=guard_score,
        integrity_blocked=any(flag.startswith("blocking:") for flag in audit_flags),
        audit_blocked=False,
        wall_clock_seconds=time.time() - started,
        task_results=results,
        audit_flags=audit_flags,
        config_path=str(config_path),
    )
    candidate.audit_blocked = candidate_is_blocked(candidate)
    return candidate


def accepted_candidate(candidate: CandidateEvaluation, parent: CandidateEvaluation) -> bool:
    return (
        candidate.train_score >= parent.train_score + 1
        and candidate.guard_score >= parent.guard_score - 1
        and not candidate.integrity_blocked
        and not candidate.audit_blocked
    )


def sample_score(results: List[TaskResult], sample_tasks: List[EvalTask]) -> int:
    sample_ids = {task.task_id for task in sample_tasks}
    return sum(1 for result in results if result.task_id in sample_ids and result.visible_passed)


def choose_screening_sample(train_tasks: List[EvalTask], size: int) -> List[EvalTask]:
    categories = {}
    for task in train_tasks:
        categories.setdefault(task.category, []).append(task)
    sample = []
    for category in sorted(categories):
        sample.append(sorted(categories[category], key=lambda task: (task.difficulty, task.task_id))[0])
    if len(sample) < size:
        remaining = [task for task in sorted(train_tasks, key=lambda task: (task.difficulty, task.task_id)) if task not in sample]
        sample.extend(remaining[: size - len(sample)])
    return sample[:size]


def select_parent(accepted: List[CandidateEvaluation]) -> CandidateEvaluation:
    archive = sort_archive(accepted)
    top_three = archive[:3]
    roll = random.random()
    if roll < 0.7 and top_three:
        weights = [max(candidate.train_score, 1) for candidate in top_three]
        return random.choices(top_three, weights=weights, k=1)[0]
    if roll < 0.9:
        return choose_diverse_parent(archive)
    return random.choice(archive)


def choose_diverse_parent(accepted: List[CandidateEvaluation]) -> CandidateEvaluation:
    recent = accepted[-10:]
    counts: Dict[str, int] = {}
    for candidate in recent:
        counts[candidate.mutation_type] = counts.get(candidate.mutation_type, 0) + 1
    ranked = sorted(accepted, key=lambda candidate: counts.get(candidate.mutation_type, 0))
    return ranked[0]


def sort_archive(accepted: List[CandidateEvaluation]) -> List[CandidateEvaluation]:
    return sorted(
        accepted,
        key=lambda candidate: (
            candidate.train_score,
            candidate.guard_score,
            -candidate.wall_clock_seconds,
            -len(candidate.audit_flags),
        ),
        reverse=True,
    )


def evaluate_holdout(
    candidate_id: str,
    config: AgentConfig,
    holdout_tasks: List[EvalTask],
    output_dir: Path,
) -> Dict[str, object]:
    results = []
    for task in holdout_tasks:
        results.append(evaluate_task(config, task, candidate_id, output_dir, evaluate_hidden=True))
    return {
        "candidate_id": candidate_id,
        "visible_score": sum(1 for result in results if result.visible_passed),
        "hidden_score": sum(1 for result in results if result.hidden_result == "passed"),
        "task_results": [result.to_dict() for result in results],
    }
