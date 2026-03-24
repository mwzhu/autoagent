"""Optimization loop."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Dict, List, Set

from superagent.adapters import get_agent_adapter
from superagent.audit import heuristic_audit
from superagent.config import (
    CodeBenchmarkEvalConfig,
    DatasetEvalConfig,
    RunConfig,
    load_run_config,
    maximum_guard_regression,
    minimum_train_delta,
    save_run_config,
)
from superagent.evals import get_eval_backend
from superagent.models import CandidateAttempt, CandidateEvaluation, EvalTask, TaskResult
from superagent.mutator import normalize_mutation_proposal, propose_mutation
from superagent.runner import evaluate_task
from superagent.storage import create_run_record, init_db, log_candidate, update_run_record
from superagent.utils import ensure_dir, write_json


def run_optimization(config: RunConfig, config_path: Path, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    ensure_dir(output_dir / "configs")
    ensure_dir(output_dir / "receipts")
    adapter = get_agent_adapter(config.agent.adapter)
    backend = get_eval_backend(config.eval.backend)
    tasks = backend.load_tasks(config.eval.config)
    splits = backend.split_tasks(tasks)
    screening_sample = choose_screening_sample(splits["train"], config.optimizer.screening_sample_size)
    run_id = output_dir.name
    connection = init_db(output_dir / "run.sqlite3")
    create_run_record(
        connection,
        run_id,
        adapter_name=config.agent.adapter,
        backend_name=config.eval.backend,
        eval_target=_eval_target(config),
        config_path=str(config_path),
        screening_sample=[task.task_id for task in screening_sample],
    )
    run_started = time.time()
    cumulative_meta_cost_usd = 0.0
    cumulative_task_cost_usd = 0.0
    duplicate_skip_count = 0
    seen_fingerprints: Set[str] = set()

    baseline_config_path = output_dir / "configs" / "baseline.yaml"
    save_run_config(config, baseline_config_path)
    baseline_attempt = evaluate_candidate_attempt(
        config=config,
        adapter=adapter,
        backend=backend,
        candidate_id="baseline",
        screening_sample=screening_sample,
        train_tasks=splits["train"],
        guard_tasks=splits["guard"],
        output_dir=output_dir,
        parent_sample_score=-1.0,
        parent_train_score=-1.0,
        min_train_delta=minimum_train_delta(config.eval.config),
        full_train_required=True,
        meta_cost_usd=0.0,
    )
    baseline = summarize_candidate(
        candidate_id="baseline",
        parent_id="baseline",
        mutation_type="baseline",
        adapter_name=config.agent.adapter,
        backend_name=config.eval.backend,
        config_path=baseline_config_path,
        attempts=[baseline_attempt],
        accepted=True,
        duplicate_skip_count=0,
        confirmation_rerun_required=False,
        confirmation_rerun_passed=False,
    )
    log_candidate(connection, run_id, baseline)
    cumulative_task_cost_usd += baseline.task_cost_usd
    update_run_record(
        connection,
        run_id,
        cumulative_meta_cost_usd=cumulative_meta_cost_usd,
        cumulative_task_cost_usd=cumulative_task_cost_usd,
        cumulative_wall_clock_seconds=time.time() - run_started,
        duplicate_skip_count=duplicate_skip_count,
    )

    accepted = [baseline]
    last_summary: Dict[str, object] = {
        "candidate_id": "baseline",
        "sample_score": baseline.sample_score,
        "train_score": baseline.train_score,
        "guard_score": baseline.guard_score,
    }
    accept_count = 0
    holdout_checkpoints: List[Dict[str, object]] = []
    min_train_delta = minimum_train_delta(config.eval.config)
    max_guard_regression = maximum_guard_regression(config.eval.config)
    stop_due_to_budget = False

    for iteration in range(config.optimizer.max_iterations):
        if accept_count >= config.optimizer.max_accepts:
            break
        if _wall_clock_exceeded(config, run_started):
            break
        parent = select_parent(accepted)
        parent_config = load_run_config(Path(parent.config_path))
        proposal = None
        proposal_usage_cost = 0.0
        skipped_this_iteration = 0
        for _ in range(config.optimizer.duplicate_retry_limit):
            proposal_candidate, usage = propose_mutation(parent_config, adapter, last_summary)
            proposal_usage_cost += usage.cost_usd
            cumulative_meta_cost_usd += usage.cost_usd
            if cumulative_meta_cost_usd > config.optimizer.max_meta_api_cost_usd:
                stop_due_to_budget = True
                break
            fingerprint = fingerprint_mutation(parent_config, proposal_candidate)
            if fingerprint in seen_fingerprints:
                duplicate_skip_count += 1
                skipped_this_iteration += 1
                continue
            seen_fingerprints.add(fingerprint)
            proposal = proposal_candidate
            break
        if stop_due_to_budget:
            break
        if proposal is None:
            update_run_record(
                connection,
                run_id,
                cumulative_meta_cost_usd=cumulative_meta_cost_usd,
                cumulative_task_cost_usd=cumulative_task_cost_usd,
                cumulative_wall_clock_seconds=time.time() - run_started,
                duplicate_skip_count=duplicate_skip_count,
            )
            continue
        candidate_config = parent_config.clone()
        candidate_config.apply_agent_changes(proposal.changes, adapter.mutable_paths(candidate_config.agent.config))
        candidate_id = "cand_{:03d}".format(iteration + 1)
        candidate_config_path = output_dir / "configs" / (candidate_id + ".yaml")
        save_run_config(candidate_config, candidate_config_path)
        first_attempt = evaluate_candidate_attempt(
            config=candidate_config,
            adapter=adapter,
            backend=backend,
            candidate_id=candidate_id,
            screening_sample=screening_sample,
            train_tasks=splits["train"],
            guard_tasks=splits["guard"],
            output_dir=output_dir,
            parent_sample_score=sample_score(parent.task_results, screening_sample, backend, config.eval.config),
            parent_train_score=parent.train_score,
            min_train_delta=min_train_delta,
            full_train_required=False,
            meta_cost_usd=proposal_usage_cost,
        )
        attempts = [first_attempt]
        accepted_first = accepted_candidate(first_attempt, parent, min_train_delta, max_guard_regression)
        confirmation_required = (
            accepted_first
            and config.optimizer.rerun_borderline_accepts
            and is_borderline_candidate(first_attempt, parent, min_train_delta, max_guard_regression)
        )
        confirmation_passed = False
        if confirmation_required:
            confirm_attempt = evaluate_candidate_attempt(
                config=candidate_config,
                adapter=adapter,
                backend=backend,
                candidate_id=candidate_id + "_confirm",
                screening_sample=screening_sample,
                train_tasks=splits["train"],
                guard_tasks=splits["guard"],
                output_dir=output_dir,
                parent_sample_score=sample_score(parent.task_results, screening_sample, backend, config.eval.config),
                parent_train_score=parent.train_score,
                min_train_delta=min_train_delta,
                full_train_required=True,
                meta_cost_usd=0.0,
            )
            attempts.append(confirm_attempt)
            confirmation_passed = accepted_candidate(confirm_attempt, parent, min_train_delta, max_guard_regression)
        candidate = summarize_candidate(
            candidate_id=candidate_id,
            parent_id=parent.candidate_id,
            mutation_type=proposal.mutation_type,
            adapter_name=config.agent.adapter,
            backend_name=config.eval.backend,
            config_path=candidate_config_path,
            attempts=attempts,
            accepted=accepted_first and (not confirmation_required or confirmation_passed),
            duplicate_skip_count=skipped_this_iteration,
            confirmation_rerun_required=confirmation_required,
            confirmation_rerun_passed=confirmation_passed,
        )
        cumulative_task_cost_usd += candidate.task_cost_usd
        log_candidate(connection, run_id, candidate)
        update_run_record(
            connection,
            run_id,
            cumulative_meta_cost_usd=cumulative_meta_cost_usd,
            cumulative_task_cost_usd=cumulative_task_cost_usd,
            cumulative_wall_clock_seconds=time.time() - run_started,
            duplicate_skip_count=duplicate_skip_count,
        )
        if candidate.accepted:
            accepted.append(candidate)
            accepted = sort_archive(accepted)[: config.optimizer.archive_size]
            accept_count += 1
            last_summary = {
                "candidate_id": candidate.candidate_id,
                "sample_score": candidate.sample_score,
                "train_score": candidate.train_score,
                "guard_score": candidate.guard_score,
                "audit_flags": candidate.audit_flags,
            }
            if accept_count % 10 == 0:
                holdout_checkpoints.append(
                    evaluate_holdout(
                        config=candidate_config,
                        adapter=adapter,
                        backend=backend,
                        candidate_id=candidate.candidate_id + "_holdout_checkpoint",
                        holdout_tasks=splits["holdout"],
                        output_dir=output_dir,
                    )
                )
        if _wall_clock_exceeded(config, run_started):
            break
    best = sort_archive(accepted)[0]
    best_config = load_run_config(Path(best.config_path))
    holdout_summary = {
        "baseline": evaluate_holdout(
            config=config,
            adapter=adapter,
            backend=backend,
            candidate_id="baseline_holdout",
            holdout_tasks=splits["holdout"],
            output_dir=output_dir,
        ),
        "best": evaluate_holdout(
            config=best_config,
            adapter=adapter,
            backend=backend,
            candidate_id=best.candidate_id + "_holdout",
            holdout_tasks=splits["holdout"],
            output_dir=output_dir,
        ),
        "checkpoints": holdout_checkpoints,
    }
    write_json(output_dir / "holdout_summary.json", holdout_summary)
    update_run_record(
        connection,
        run_id,
        cumulative_meta_cost_usd=cumulative_meta_cost_usd,
        cumulative_task_cost_usd=cumulative_task_cost_usd,
        cumulative_wall_clock_seconds=time.time() - run_started,
        duplicate_skip_count=duplicate_skip_count,
    )
    connection.close()
    return output_dir


def evaluate_candidate_attempt(
    config: RunConfig,
    adapter,
    backend,
    candidate_id: str,
    screening_sample: List[EvalTask],
    train_tasks: List[EvalTask],
    guard_tasks: List[EvalTask],
    output_dir: Path,
    parent_sample_score: float,
    parent_train_score: float,
    min_train_delta: float,
    full_train_required: bool,
    meta_cost_usd: float,
) -> CandidateAttempt:
    started = time.time()
    results: List[TaskResult] = []
    screening_task_ids = {task.task_id for task in screening_sample}
    for task in screening_sample:
        results.append(evaluate_task(config, adapter, backend, task, candidate_id, output_dir, evaluate_hidden=False))
    sample_results = [result for result in results if result.task_id in screening_task_ids]
    screening_score = backend.aggregate(sample_results, "train", config.eval.config)
    if not full_train_required and screening_score < parent_sample_score:
        audit_flags = heuristic_audit([Path(result.receipt_path) for result in results if result.receipt_path])
        return CandidateAttempt(
            attempt_id=candidate_id,
            sample_score=screening_score,
            train_score=screening_score,
            guard_score=0.0,
            integrity_blocked=_results_have_blocking_flags(results),
            audit_blocked=_flags_are_blocking(audit_flags),
            wall_clock_seconds=time.time() - started,
            task_results=results,
            audit_flags=audit_flags,
            meta_cost_usd=meta_cost_usd,
            task_cost_usd=sum(result.task_cost_usd for result in results),
        )
    for task in train_tasks:
        if task.task_id in screening_task_ids:
            continue
        results.append(evaluate_task(config, adapter, backend, task, candidate_id, output_dir, evaluate_hidden=False))
    train_results = [result for result in results if result.split == "train"]
    train_score = backend.aggregate(train_results, "train", config.eval.config)
    guard_score = 0.0
    if full_train_required or train_score >= parent_train_score + min_train_delta:
        for task in guard_tasks:
            results.append(evaluate_task(config, adapter, backend, task, candidate_id, output_dir, evaluate_hidden=True))
        guard_results = [result for result in results if result.split == "guard"]
        guard_score = backend.aggregate(guard_results, "guard", config.eval.config)
    audit_flags = heuristic_audit([Path(result.receipt_path) for result in results if result.receipt_path])
    return CandidateAttempt(
        attempt_id=candidate_id,
        sample_score=screening_score,
        train_score=train_score,
        guard_score=guard_score,
        integrity_blocked=_results_have_blocking_flags(results),
        audit_blocked=_flags_are_blocking(audit_flags),
        wall_clock_seconds=time.time() - started,
        task_results=results,
        audit_flags=audit_flags,
        meta_cost_usd=meta_cost_usd,
        task_cost_usd=sum(result.task_cost_usd for result in results),
    )


def summarize_candidate(
    candidate_id: str,
    parent_id: str,
    mutation_type: str,
    adapter_name: str,
    backend_name: str,
    config_path: Path,
    attempts: List[CandidateAttempt],
    accepted: bool,
    duplicate_skip_count: int,
    confirmation_rerun_required: bool,
    confirmation_rerun_passed: bool,
) -> CandidateEvaluation:
    summary_attempt = attempts[0]
    if accepted and confirmation_rerun_required and len(attempts) > 1:
        summary_attempt = min(
            attempts,
            key=lambda attempt: (attempt.train_score, attempt.guard_score, -attempt.wall_clock_seconds),
        )
    task_results = list(summary_attempt.task_results)
    audit_flags = sorted({flag for attempt in attempts for flag in attempt.audit_flags})
    return CandidateEvaluation(
        candidate_id=candidate_id,
        parent_id=parent_id,
        mutation_type=mutation_type,
        adapter_name=adapter_name,
        backend_name=backend_name,
        sample_score=summary_attempt.sample_score,
        train_score=summary_attempt.train_score,
        guard_score=summary_attempt.guard_score,
        integrity_blocked=any(attempt.integrity_blocked for attempt in attempts),
        audit_blocked=any(attempt.audit_blocked for attempt in attempts),
        wall_clock_seconds=sum(attempt.wall_clock_seconds for attempt in attempts),
        accepted=accepted,
        task_results=task_results,
        audit_flags=audit_flags,
        config_path=str(config_path),
        meta_cost_usd=sum(attempt.meta_cost_usd for attempt in attempts),
        task_cost_usd=sum(attempt.task_cost_usd for attempt in attempts),
        duplicate_skip_count=duplicate_skip_count,
        confirmation_rerun_required=confirmation_rerun_required,
        confirmation_rerun_passed=confirmation_rerun_passed,
        attempt_ids=[attempt.attempt_id for attempt in attempts],
        attempts=attempts,
    )


def accepted_candidate(
    attempt: CandidateAttempt,
    parent: CandidateEvaluation,
    min_train_delta: float,
    max_guard_regression: float,
) -> bool:
    return (
        attempt.train_score >= parent.train_score + min_train_delta
        and attempt.guard_score >= parent.guard_score - max_guard_regression
        and not attempt.integrity_blocked
        and not attempt.audit_blocked
    )


def is_borderline_candidate(
    attempt: CandidateAttempt,
    parent: CandidateEvaluation,
    min_train_delta: float,
    max_guard_regression: float,
) -> bool:
    return (
        attempt.train_score == parent.train_score + min_train_delta
        and attempt.guard_score == parent.guard_score - max_guard_regression
    )


def fingerprint_mutation(config: RunConfig, proposal) -> str:
    payload = {
        "parent_config": config.to_dict(),
        "adapter_name": config.agent.adapter,
        "backend_name": config.eval.backend,
        "proposal": normalize_mutation_proposal(proposal),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def sample_score(results: List[TaskResult], sample_tasks: List[EvalTask], backend, eval_config) -> float:
    sample_ids = {task.task_id for task in sample_tasks}
    sample_results = [result for result in results if result.task_id in sample_ids]
    return backend.aggregate(sample_results, "train", eval_config)


def choose_screening_sample(train_tasks: List[EvalTask], size: int) -> List[EvalTask]:
    categories: Dict[str, List[EvalTask]] = {}
    for task in train_tasks:
        categories.setdefault(task.category or "default", []).append(task)
    sample: List[EvalTask] = []
    for category in sorted(categories):
        sample.append(sorted(categories[category], key=lambda task: (task.difficulty, task.task_id))[0])
    if len(sample) < size:
        remaining = [
            task
            for task in sorted(train_tasks, key=lambda task: (task.difficulty, task.task_id))
            if task not in sample
        ]
        sample.extend(remaining[: max(0, size - len(sample))])
    return sample[:size]


def select_parent(accepted: List[CandidateEvaluation]) -> CandidateEvaluation:
    archive = sort_archive(accepted)
    top_three = archive[:3]
    roll = random.random()
    if roll < 0.7 and top_three:
        weights = [max(candidate.train_score, 1.0) for candidate in top_three]
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
    config: RunConfig,
    adapter,
    backend,
    candidate_id: str,
    holdout_tasks: List[EvalTask],
    output_dir: Path,
) -> Dict[str, object]:
    results = []
    for task in holdout_tasks:
        results.append(evaluate_task(config, adapter, backend, task, candidate_id, output_dir, evaluate_hidden=True))
    return {
        "candidate_id": candidate_id,
        "score": backend.aggregate(results, "holdout", config.eval.config),
        "task_results": [result.to_dict() for result in results],
    }


def _eval_target(config: RunConfig) -> str:
    if isinstance(config.eval.config, CodeBenchmarkEvalConfig):
        return config.eval.config.benchmark_dir
    assert isinstance(config.eval.config, DatasetEvalConfig)
    return config.eval.config.dataset_path


def _flags_are_blocking(flags: List[str]) -> bool:
    return any(flag.startswith("blocking:") for flag in flags)


def _results_have_blocking_flags(results: List[TaskResult]) -> bool:
    return any(any(flag.startswith("blocking:") for flag in result.integrity_flags) for result in results)


def _wall_clock_exceeded(config: RunConfig, started: float) -> bool:
    elapsed_hours = (time.time() - started) / 3600.0
    return elapsed_hours >= config.optimizer.max_wall_clock_hours
