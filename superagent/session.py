"""Managed agent-session runtime."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from superagent.boundary import BUILTIN_DENYLIST_PATTERNS, enforce_boundary
from superagent.config import RunConfig, load_run_config, maximum_guard_regression, minimum_train_delta
from superagent.evals import get_eval_backend
from superagent.models import CandidateAttempt, CandidateRecord, CommandRecord, EvalTask, RunReceipt, SessionState, TaskResult, candidate_scores
from superagent.storage import (
    SessionPaths,
    ensure_session_dirs,
    is_managed_workspace,
    list_candidates,
    load_candidate,
    load_managed_config,
    load_session_state,
    save_candidate,
    save_managed_config,
    save_session_state,
    session_paths,
)
from superagent.utils import (
    clear_directory,
    copytree,
    diff_snapshots,
    ensure_dir,
    hash_snapshot,
    hash_text,
    now_iso,
    read_json,
    replace_tree_contents,
    run_shell_command,
    snapshot_tree,
    summarize_text,
    sync_snapshot,
    write_json,
)


NETWORK_ENV_OVERRIDES = {
    "ALL_PROXY": "",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "NO_PROXY": "*",
    "all_proxy": "",
    "http_proxy": "",
    "https_proxy": "",
    "no_proxy": "*",
}


def init_agent_session(config_path: Path, run_dir: Path | None = None) -> Path:
    config = load_run_config(config_path.resolve())
    target_run_dir = (run_dir.resolve() if run_dir else _default_run_dir(config)).resolve()
    source_repo = Path(config.agent.repo_root).resolve()
    assert target_run_dir != source_repo, "run_dir must be different from agent.repo_root."
    if target_run_dir.exists():
        if is_managed_workspace(target_run_dir):
            raise AssertionError("Run directory is already initialized: {}".format(target_run_dir))
        assert not any(target_run_dir.iterdir()), "run_dir must not already contain files."
    ensure_dir(target_run_dir)
    _copy_imported_repo(source_repo, target_run_dir)
    paths = session_paths(target_run_dir)
    ensure_session_dirs(paths)
    save_managed_config(config, paths)
    baseline_commit_id = _initialize_canonical_repo(paths, target_run_dir)
    backend = get_eval_backend(config.eval.backend)
    tasks = backend.load_tasks(config.eval)
    splits = backend.split_tasks(tasks)
    screening_sample = choose_screening_sample(splits["train"], config.policy.screening_sample_size)
    baseline_snapshot = _live_repo_snapshot(paths)
    baseline_diff_path = paths.diffs_dir / "baseline.patch"
    baseline_diff_path.write_text("", encoding="utf-8")
    baseline = CandidateRecord(
        candidate_id="baseline",
        parent_id="baseline",
        created_at=now_iso(),
        verdict="baseline",
        accepted=True,
        in_active_archive=True,
        accepted_commit_id=baseline_commit_id,
        workspace_hash=hash_snapshot(baseline_snapshot),
        candidate_fingerprint=hash_text(""),
        diff_path=str(baseline_diff_path),
        failure_summary={"built_in_denylist": BUILTIN_DENYLIST_PATTERNS},
    )
    save_candidate(baseline, paths)
    state = SessionState(
        run_id=target_run_dir.name,
        created_at=now_iso(),
        config_path=str(config_path.resolve()),
        imported_repo_root=str(source_repo),
        backend_name=config.eval.backend,
        current_baseline_id="baseline",
        active_parent_id="baseline",
        screening_sample_ids=[task.task_id for task in screening_sample],
        active_archive_ids=["baseline"],
    )
    save_session_state(state, paths)
    return target_run_dir


def resolve_run_dir(run_dir: Path | None = None) -> Path:
    if run_dir is not None:
        resolved = run_dir.resolve()
    else:
        resolved = Path.cwd().resolve()
    if not is_managed_workspace(resolved):
        raise AssertionError("No managed SuperAgent workspace found at {}".format(resolved))
    return resolved


def agent_status(run_dir: Path) -> Dict[str, object]:
    paths, config, state = _load_session_bundle(run_dir)
    candidates = list_candidates(paths)
    parent_snapshot = _snapshot_for_parent(paths, state.active_parent_id)
    live_snapshot = _live_repo_snapshot(paths)
    changed = sorted(_changed_paths(parent_snapshot, live_snapshot))
    return {
        "run_dir": str(paths.run_dir),
        "config_path": state.config_path,
        "current_baseline_id": state.current_baseline_id,
        "active_parent_id": state.active_parent_id,
        "last_evaluated_candidate_id": state.last_evaluated_candidate_id or None,
        "screening_sample_ids": list(state.screening_sample_ids),
        "evaluation_count": state.evaluation_count,
        "accept_count": state.accept_count,
        "cumulative_task_cost_usd": state.cumulative_task_cost_usd,
        "cumulative_wall_clock_seconds": state.cumulative_wall_clock_seconds,
        "active_archive_ids": list(state.active_archive_ids),
        "candidate_count": len(candidates),
        "live_changed_files": changed,
        "built_in_denylist": BUILTIN_DENYLIST_PATTERNS,
        "entry_contract": config.agent.entry_contract.__dict__,
    }


def agent_history(run_dir: Path) -> Dict[str, object]:
    paths = session_paths(resolve_run_dir(run_dir))
    return {"candidates": [candidate.to_dict() for candidate in list_candidates(paths)]}


def agent_diff(run_dir: Path) -> str:
    paths, _, state = _load_session_bundle(run_dir)
    parent_snapshot = _snapshot_for_parent(paths, state.active_parent_id)
    live_snapshot = _live_repo_snapshot(paths)
    return diff_snapshots(parent_snapshot, live_snapshot)


def agent_checkout_parent(run_dir: Path, candidate_id: str) -> Dict[str, object]:
    paths, _, state = _load_session_bundle(run_dir)
    candidate = load_candidate(paths, candidate_id)
    assert candidate.accepted and candidate.in_active_archive, "candidate_id must be an accepted candidate in the active archive."
    _restore_candidate_to_live_workspace(paths, candidate)
    state.active_parent_id = candidate_id
    save_session_state(state, paths)
    return {"active_parent_id": state.active_parent_id, "current_baseline_id": state.current_baseline_id}


def agent_revert(run_dir: Path) -> Dict[str, object]:
    paths, _, state = _load_session_bundle(run_dir)
    baseline = load_candidate(paths, state.current_baseline_id)
    _restore_candidate_to_live_workspace(paths, baseline)
    state.active_parent_id = state.current_baseline_id
    save_session_state(state, paths)
    return {"active_parent_id": state.active_parent_id, "current_baseline_id": state.current_baseline_id}


def agent_accept(run_dir: Path) -> Dict[str, object]:
    paths, config, state = _load_session_bundle(run_dir)
    assert state.last_evaluated_candidate_id, "No evaluated candidate is available to accept."
    candidate = load_candidate(paths, state.last_evaluated_candidate_id)
    assert candidate.verdict == "eligible_for_accept", "Only eligible_for_accept candidates can be accepted."
    current_snapshot = _live_repo_snapshot(paths)
    parent_snapshot = _snapshot_for_parent(paths, state.active_parent_id)
    current_diff = diff_snapshots(parent_snapshot, current_snapshot)
    current_fingerprint = hash_text(current_diff)
    current_workspace_hash = hash_snapshot(current_snapshot)
    boundary_flags = enforce_boundary(_changed_paths(parent_snapshot, current_snapshot), config.agent.mutation_boundary)
    assert not boundary_flags, "Current workspace violates the mutation boundary: {}".format(", ".join(boundary_flags))
    assert (
        current_workspace_hash == state.last_evaluated_workspace_hash
    ), "Live workspace changed after evaluation. Re-run `superagent agent evaluate` before accepting."
    assert (
        current_fingerprint == state.last_evaluated_candidate_fingerprint
    ), "Candidate diff changed after evaluation. Re-run `superagent agent evaluate` before accepting."
    commit_id = _commit_live_workspace(paths, candidate.candidate_id)
    candidate.accepted = True
    candidate.in_active_archive = True
    candidate.accepted_commit_id = commit_id
    save_candidate(candidate, paths)
    state.current_baseline_id = candidate.candidate_id
    state.active_parent_id = candidate.candidate_id
    if candidate.candidate_id not in state.active_archive_ids:
        state.active_archive_ids.append(candidate.candidate_id)
    state.accept_count += 1
    _prune_archive(paths, config, state)
    save_session_state(state, paths)
    return {
        "accepted_candidate_id": candidate.candidate_id,
        "current_baseline_id": state.current_baseline_id,
        "active_parent_id": state.active_parent_id,
        "active_archive_ids": list(state.active_archive_ids),
    }


def agent_failures(run_dir: Path, candidate_id: str) -> Dict[str, object]:
    paths = session_paths(resolve_run_dir(run_dir))
    candidate = load_candidate(paths, candidate_id)
    attempts = []
    for attempt in candidate.attempts:
        attempts.append(
            {
                "attempt_id": attempt.attempt_id,
                "sample_score": attempt.sample_score,
                "train_score": attempt.train_score,
                "guard_score": attempt.guard_score,
                "task_diagnostics": [
                    {
                        "task_id": result.task_id,
                        "split": result.split,
                        "passed": result.passed,
                        "visible_outcome": "passed" if result.visible_passed else "failed",
                        "hidden_outcome": result.hidden_result,
                        "integrity_flags": list(result.integrity_flags),
                        "stdout_summary": result.stdout_summary,
                        "stderr_summary": result.stderr_summary,
                        "mismatch_summary": result.mismatch_summary,
                        "receipt_path": result.receipt_path,
                    }
                    for result in attempt.task_results
                ],
            }
        )
    return {
        "candidate_id": candidate.candidate_id,
        "verdict": candidate.verdict,
        "failure_summary": dict(candidate.failure_summary),
        "attempts": attempts,
    }


def agent_evaluate(run_dir: Path) -> Dict[str, object]:
    paths, config, state = _load_session_bundle(run_dir)
    backend = get_eval_backend(config.eval.backend)
    tasks = backend.load_tasks(config.eval)
    splits = backend.split_tasks(tasks)
    task_index = {task.task_id: task for task in tasks}
    screening_sample = [task_index[task_id] for task_id in state.screening_sample_ids if task_id in task_index]
    if not screening_sample:
        screening_sample = choose_screening_sample(splits["train"], config.policy.screening_sample_size)
        state.screening_sample_ids = [task.task_id for task in screening_sample]
        save_session_state(state, paths)
    parent = _ensure_parent_scores(paths, config, state, backend, splits, screening_sample)
    live_snapshot = _live_repo_snapshot(paths)
    parent_snapshot = _snapshot_for_parent(paths, state.active_parent_id)
    diff_text = diff_snapshots(parent_snapshot, live_snapshot)
    changed_paths = _changed_paths(parent_snapshot, live_snapshot)
    candidate_id = _next_candidate_id(state)
    diff_path = paths.diffs_dir / (candidate_id + ".patch")
    diff_path.write_text(diff_text, encoding="utf-8")
    workspace_hash = hash_snapshot(live_snapshot)
    candidate_fingerprint = hash_text(diff_text)
    boundary_flags = enforce_boundary(changed_paths, config.agent.mutation_boundary)
    duplicate_of = _duplicate_candidate_id(paths, workspace_hash)
    policy_reason = _policy_block_reason(config, state)

    candidate = CandidateRecord(
        candidate_id=candidate_id,
        parent_id=state.active_parent_id,
        created_at=now_iso(),
        verdict="integrity_blocked",
        workspace_hash=workspace_hash,
        candidate_fingerprint=candidate_fingerprint,
        diff_path=str(diff_path),
        integrity_flags=list(boundary_flags),
        failure_summary={"built_in_denylist": BUILTIN_DENYLIST_PATTERNS},
    )
    state.last_evaluated_candidate_id = candidate_id
    state.last_evaluated_candidate_fingerprint = candidate_fingerprint
    state.last_evaluated_workspace_hash = workspace_hash

    if duplicate_of:
        candidate.verdict = "duplicate"
        candidate.failure_summary.update({"duplicate_of": duplicate_of, "changed_files": sorted(changed_paths)})
        save_candidate(candidate, paths)
        save_session_state(state, paths)
        return _candidate_response(candidate)

    if boundary_flags:
        candidate.failure_summary.update(
            {
                "reason": "mutation boundary violation",
                "changed_files": sorted(changed_paths),
                "integrity_flags": list(boundary_flags),
            }
        )
        save_candidate(candidate, paths)
        save_session_state(state, paths)
        return _candidate_response(candidate)

    if policy_reason:
        candidate.failure_summary.update({"reason": policy_reason, "changed_files": sorted(changed_paths)})
        save_candidate(candidate, paths)
        save_session_state(state, paths)
        return _candidate_response(candidate)

    min_train_delta = minimum_train_delta(config.eval)
    max_guard_regression = maximum_guard_regression(config.eval)
    start_time = time.time()
    first_attempt, first_blocking_flags = _evaluate_attempt(
        paths=paths,
        config=config,
        backend=backend,
        candidate_id=candidate_id,
        attempt_id=candidate_id,
        candidate_snapshot=live_snapshot,
        screening_sample=screening_sample,
        train_tasks=splits["train"],
        guard_tasks=splits["guard"],
        parent_sample_score=float(parent.sample_score or 0.0),
        parent_train_score=float(parent.train_score or 0.0),
        min_train_delta=min_train_delta,
        full_train_required=False,
    )
    attempts = [first_attempt]
    candidate.attempt_ids = [first_attempt.attempt_id]
    candidate.attempts = attempts
    candidate.task_cost_usd = first_attempt.task_cost_usd
    candidate.wall_clock_seconds = first_attempt.wall_clock_seconds
    blocking_flags = list(first_blocking_flags)
    verdict = _determine_attempt_verdict(first_attempt, parent, min_train_delta, max_guard_regression, blocking_flags)
    confirmation_required = (
        verdict == "eligible_for_accept"
        and config.policy.rerun_borderline_accepts
        and _is_borderline_candidate(first_attempt, parent, min_train_delta, max_guard_regression)
    )
    confirmation_passed = False
    if confirmation_required:
        rerun_attempt, rerun_blocking_flags = _evaluate_attempt(
            paths=paths,
            config=config,
            backend=backend,
            candidate_id=candidate_id,
            attempt_id=candidate_id + "_rerun",
            candidate_snapshot=live_snapshot,
            screening_sample=screening_sample,
            train_tasks=splits["train"],
            guard_tasks=splits["guard"],
            parent_sample_score=float(parent.sample_score or 0.0),
            parent_train_score=float(parent.train_score or 0.0),
            min_train_delta=min_train_delta,
            full_train_required=True,
        )
        attempts.append(rerun_attempt)
        blocking_flags.extend(rerun_blocking_flags)
        candidate.attempt_ids.append(rerun_attempt.attempt_id)
        candidate.task_cost_usd += rerun_attempt.task_cost_usd
        candidate.wall_clock_seconds += rerun_attempt.wall_clock_seconds
        candidate.attempts = attempts
        rerun_verdict = _determine_attempt_verdict(rerun_attempt, parent, min_train_delta, max_guard_regression, rerun_blocking_flags)
        confirmation_passed = rerun_verdict == "eligible_for_accept"
        verdict = rerun_verdict

    summary_attempt = _summary_attempt(attempts, confirmation_required, confirmation_passed)
    candidate.verdict = verdict
    candidate.sample_score = summary_attempt.sample_score
    candidate.train_score = summary_attempt.train_score
    candidate.guard_score = summary_attempt.guard_score
    candidate.confirmation_rerun_required = confirmation_required
    candidate.confirmation_rerun_passed = confirmation_passed
    candidate.integrity_flags = sorted(set(blocking_flags + _collect_result_flags(summary_attempt.task_results)))
    candidate.failure_summary = _build_failure_summary(candidate, summary_attempt, parent)
    state.evaluation_count += 1
    state.cumulative_task_cost_usd += candidate.task_cost_usd
    state.cumulative_wall_clock_seconds += time.time() - start_time
    save_candidate(candidate, paths)
    save_session_state(state, paths)
    return _candidate_response(candidate)


def evaluate_holdout_candidate(run_dir: Path, candidate_id: str) -> Dict[str, object]:
    paths, config, _ = _load_session_bundle(run_dir)
    backend = get_eval_backend(config.eval.backend)
    tasks = backend.load_tasks(config.eval)
    splits = backend.split_tasks(tasks)
    candidate = load_candidate(paths, candidate_id)
    assert candidate.accepted and candidate.accepted_commit_id, "Holdout can only run for accepted candidates."
    snapshot = _snapshot_from_commit(paths, candidate.accepted_commit_id)
    holdout_attempt, blocking_flags = _run_attempt(
        paths=paths,
        config=config,
        backend=backend,
        candidate_id=candidate_id + "_holdout",
        attempt_id=candidate_id + "_holdout",
        candidate_snapshot=snapshot,
        screening_sample=[],
        train_tasks=[],
        guard_tasks=splits["holdout"],
        parent_sample_score=0.0,
        parent_train_score=0.0,
        min_train_delta=0.0,
        full_train_required=True,
        holdout_mode=True,
    )
    return {
        "candidate_id": candidate_id,
        "score": backend.aggregate(holdout_attempt.task_results, "holdout", config.eval),
        "blocking_flags": blocking_flags,
        "task_results": [result.to_dict() for result in holdout_attempt.task_results],
    }


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


def best_accepted_candidate(paths: SessionPaths) -> CandidateRecord:
    accepted = [candidate for candidate in list_candidates(paths) if candidate.accepted]
    assert accepted, "No accepted candidates are available."
    return sorted(
        accepted,
        key=lambda candidate: (
            float(candidate.train_score or 0.0),
            float(candidate.guard_score or 0.0),
            float(candidate.sample_score or 0.0),
            candidate.created_at,
        ),
        reverse=True,
    )[0]


def _load_session_bundle(run_dir: Path) -> Tuple[SessionPaths, RunConfig, SessionState]:
    paths = session_paths(resolve_run_dir(run_dir))
    config = load_managed_config(paths)
    state = load_session_state(paths)
    return paths, config, state


def _default_run_dir(config: RunConfig) -> Path:
    return (Path.cwd() / (Path(config.agent.repo_root).name + "-superagent-run")).resolve()


def _copy_imported_repo(source_repo: Path, target_run_dir: Path) -> None:
    for child in source_repo.iterdir():
        if child.name in {".git", ".superagent"}:
            continue
        destination = target_run_dir / child.name
        if child.is_dir():
            shutil.copytree(child, destination, copy_function=shutil.copy2)
        else:
            shutil.copy2(child, destination)


def _initialize_canonical_repo(paths: SessionPaths, run_dir: Path) -> str:
    canonical_repo = paths.canonical_repo_dir
    ensure_dir(canonical_repo.parent)
    if canonical_repo.exists():
        shutil.rmtree(canonical_repo)
    shutil.copytree(run_dir, canonical_repo, ignore=shutil.ignore_patterns(".superagent"), copy_function=shutil.copy2)
    _git(canonical_repo, "init")
    _git(canonical_repo, "config", "user.name", "SuperAgent")
    _git(canonical_repo, "config", "user.email", "superagent@example.invalid")
    _git(canonical_repo, "add", "-A")
    _git(canonical_repo, "commit", "--allow-empty", "-m", "baseline import")
    return _git(canonical_repo, "rev-parse", "HEAD").strip()


def _git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError("git {} failed: {}".format(" ".join(args), completed.stderr.strip()))
    return completed.stdout


def _snapshot_from_commit(paths: SessionPaths, commit_id: str) -> Dict[str, str]:
    with tempfile.TemporaryDirectory() as tmp_root:
        clone_dir = Path(tmp_root) / "export"
        completed = subprocess.run(
            ["git", "clone", "--quiet", str(paths.canonical_repo_dir), str(clone_dir)],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError("git clone failed: {}".format(completed.stderr.strip()))
        _git(clone_dir, "checkout", "--quiet", commit_id)
        return snapshot_tree(clone_dir, ignore_roots={".git"})


def _restore_candidate_to_live_workspace(paths: SessionPaths, candidate: CandidateRecord) -> None:
    assert candidate.accepted_commit_id, "Accepted candidates must have an associated commit."
    with tempfile.TemporaryDirectory() as tmp_root:
        clone_dir = Path(tmp_root) / "restore"
        completed = subprocess.run(
            ["git", "clone", "--quiet", str(paths.canonical_repo_dir), str(clone_dir)],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError("git clone failed: {}".format(completed.stderr.strip()))
        _git(clone_dir, "checkout", "--quiet", candidate.accepted_commit_id)
        replace_tree_contents(clone_dir, paths.run_dir, preserve_names={paths.control_dir.name})
        live_git_dir = paths.run_dir / ".git"
        if live_git_dir.exists():
            shutil.rmtree(live_git_dir)


def _commit_live_workspace(paths: SessionPaths, candidate_id: str) -> str:
    with tempfile.TemporaryDirectory() as tmp_root:
        export_dir = Path(tmp_root) / "export"
        ensure_dir(export_dir)
        for child in paths.run_dir.iterdir():
            if child.name == paths.control_dir.name:
                continue
            destination = export_dir / child.name
            if child.is_dir():
                shutil.copytree(child, destination, copy_function=shutil.copy2)
            else:
                shutil.copy2(child, destination)
        replace_tree_contents(export_dir, paths.canonical_repo_dir, preserve_names={".git"})
    _git(paths.canonical_repo_dir, "add", "-A")
    _git(paths.canonical_repo_dir, "commit", "--allow-empty", "-m", "accept {}".format(candidate_id))
    return _git(paths.canonical_repo_dir, "rev-parse", "HEAD").strip()


def _live_repo_snapshot(paths: SessionPaths) -> Dict[str, str]:
    return snapshot_tree(paths.run_dir, ignore_roots={paths.control_dir.name})


def _snapshot_for_parent(paths: SessionPaths, candidate_id: str) -> Dict[str, str]:
    candidate = load_candidate(paths, candidate_id)
    if candidate_id == "baseline" or candidate.accepted:
        assert candidate.accepted_commit_id, "Parent candidate must have an accepted commit."
        return _snapshot_from_commit(paths, candidate.accepted_commit_id)
    raise AssertionError("Only accepted candidates can be used as active parents.")


def _changed_paths(before: Dict[str, str], after: Dict[str, str]) -> List[str]:
    return sorted({path for path in set(before) | set(after) if before.get(path) != after.get(path)})


def _duplicate_candidate_id(paths: SessionPaths, workspace_hash: str) -> str:
    for candidate in list_candidates(paths):
        if candidate.workspace_hash == workspace_hash:
            return candidate.candidate_id
    return ""


def _policy_block_reason(config: RunConfig, state: SessionState) -> str:
    if state.evaluation_count >= config.policy.max_evaluations:
        return "policy max_evaluations reached"
    if state.accept_count >= config.policy.max_accepts:
        return "policy max_accepts reached"
    if state.cumulative_task_cost_usd >= config.policy.max_task_cost_usd:
        return "policy max_task_cost_usd reached"
    created_at = datetime.fromisoformat(state.created_at)
    elapsed_hours = (datetime.now(created_at.tzinfo) - created_at).total_seconds() / 3600.0
    if elapsed_hours >= config.policy.max_wall_clock_hours:
        return "policy max_wall_clock_hours reached"
    return ""


def _next_candidate_id(state: SessionState) -> str:
    candidate_id = "cand_{:04d}".format(state.next_candidate_number)
    state.next_candidate_number += 1
    return candidate_id


def _ensure_parent_scores(
    paths: SessionPaths,
    config: RunConfig,
    state: SessionState,
    backend,
    splits: Dict[str, List[EvalTask]],
    screening_sample: List[EvalTask],
) -> CandidateRecord:
    parent = load_candidate(paths, state.active_parent_id)
    if parent.sample_score is not None and parent.train_score is not None and parent.guard_score is not None:
        return parent
    assert parent.accepted and parent.accepted_commit_id, "Active parent must be accepted."
    snapshot = _snapshot_from_commit(paths, parent.accepted_commit_id)
    attempt, blocking_flags = _run_attempt(
        paths=paths,
        config=config,
        backend=backend,
        candidate_id=parent.candidate_id,
        attempt_id=parent.candidate_id,
        candidate_snapshot=snapshot,
        screening_sample=screening_sample,
        train_tasks=splits["train"],
        guard_tasks=splits["guard"],
        parent_sample_score=0.0,
        parent_train_score=0.0,
        min_train_delta=0.0,
        full_train_required=True,
    )
    parent.sample_score = attempt.sample_score
    parent.train_score = attempt.train_score
    parent.guard_score = attempt.guard_score
    parent.attempt_ids = [attempt.attempt_id]
    parent.attempts = [attempt]
    parent.task_cost_usd = 0.0
    parent.wall_clock_seconds = attempt.wall_clock_seconds
    parent.integrity_flags = list(blocking_flags)
    parent.failure_summary = _build_failure_summary(parent, attempt, parent)
    save_candidate(parent, paths)
    return parent


def _evaluate_attempt(
    paths: SessionPaths,
    config: RunConfig,
    backend,
    candidate_id: str,
    attempt_id: str,
    candidate_snapshot: Dict[str, str],
    screening_sample: List[EvalTask],
    train_tasks: List[EvalTask],
    guard_tasks: List[EvalTask],
    parent_sample_score: float,
    parent_train_score: float,
    min_train_delta: float,
    full_train_required: bool,
) -> Tuple[CandidateAttempt, List[str]]:
    return _run_attempt(
        paths=paths,
        config=config,
        backend=backend,
        candidate_id=candidate_id,
        attempt_id=attempt_id,
        candidate_snapshot=candidate_snapshot,
        screening_sample=screening_sample,
        train_tasks=train_tasks,
        guard_tasks=guard_tasks,
        parent_sample_score=parent_sample_score,
        parent_train_score=parent_train_score,
        min_train_delta=min_train_delta,
        full_train_required=full_train_required,
    )


def _run_attempt(
    paths: SessionPaths,
    config: RunConfig,
    backend,
    candidate_id: str,
    attempt_id: str,
    candidate_snapshot: Dict[str, str],
    screening_sample: List[EvalTask],
    train_tasks: List[EvalTask],
    guard_tasks: List[EvalTask],
    parent_sample_score: float,
    parent_train_score: float,
    min_train_delta: float,
    full_train_required: bool,
    holdout_mode: bool = False,
) -> Tuple[CandidateAttempt, List[str]]:
    attempt_root = paths.evaluations_dir / attempt_id
    if attempt_root.exists():
        shutil.rmtree(attempt_root)
    repo_dir = attempt_root / "repo"
    task_dir = attempt_root / ".superagent_task"
    output_dir = attempt_root / ".superagent_output"
    workspace_dir = attempt_root / ".superagent_workspace"
    ensure_dir(repo_dir)
    ensure_dir(task_dir)
    ensure_dir(output_dir)
    ensure_dir(workspace_dir)
    sync_snapshot(candidate_snapshot, repo_dir)
    env = _command_environment(config, task_dir, workspace_dir, output_dir)
    setup_commands: List[CommandRecord] = []
    blocking_flags: List[str] = []
    if config.agent.install_command:
        install_block_reason = _validate_command_text(config.agent.install_command, config)
        if install_block_reason:
            blocking_flags.append(install_block_reason)
        else:
            install_record = run_shell_command(config.agent.install_command, repo_dir, env=env)
            setup_commands.append(install_record)
            if install_record.exit_code != 0:
                blocking_flags.append("blocking:install_command_failed")
    if blocking_flags:
        attempt = CandidateAttempt(
            attempt_id=attempt_id,
            sample_score=0.0,
            train_score=0.0,
            guard_score=0.0,
            wall_clock_seconds=0.0,
            task_results=[],
            setup_commands=setup_commands,
            task_cost_usd=0.0,
        )
        return attempt, blocking_flags
    after_install_snapshot = snapshot_tree(repo_dir)
    install_extra_snapshot = {
        path: content for path, content in after_install_snapshot.items() if path not in candidate_snapshot
    }
    reset_snapshot = dict(candidate_snapshot)
    reset_snapshot.update(install_extra_snapshot)

    started = time.time()
    results: List[TaskResult] = []
    sample_ids = {task.task_id for task in screening_sample}
    if screening_sample:
        for task in screening_sample:
            results.append(
                _run_single_task(
                    paths=paths,
                    config=config,
                    backend=backend,
                    candidate_id=candidate_id,
                    attempt_id=attempt_id,
                    task=task,
                    repo_dir=repo_dir,
                    task_dir=task_dir,
                    output_dir=output_dir,
                    workspace_dir=workspace_dir,
                    reset_snapshot=reset_snapshot,
                    evaluate_hidden=False,
                )
            )
        screening_score = backend.aggregate([result for result in results if result.task_id in sample_ids], "train", config.eval)
        if not holdout_mode and not full_train_required and screening_score < parent_sample_score:
            return (
                CandidateAttempt(
                    attempt_id=attempt_id,
                    sample_score=screening_score,
                    train_score=screening_score,
                    guard_score=0.0,
                    wall_clock_seconds=time.time() - started,
                    task_results=results,
                    setup_commands=setup_commands,
                    task_cost_usd=sum(result.task_cost_usd for result in results),
                ),
                blocking_flags,
            )
    else:
        screening_score = 0.0

    for task in train_tasks:
        if task.task_id in sample_ids:
            continue
        results.append(
            _run_single_task(
                paths=paths,
                config=config,
                backend=backend,
                candidate_id=candidate_id,
                attempt_id=attempt_id,
                task=task,
                repo_dir=repo_dir,
                task_dir=task_dir,
                output_dir=output_dir,
                workspace_dir=workspace_dir,
                reset_snapshot=reset_snapshot,
                evaluate_hidden=False,
            )
        )
    train_score = backend.aggregate([result for result in results if result.split == "train"], "train", config.eval)
    guard_score = 0.0
    should_run_guard = holdout_mode or full_train_required or train_score >= parent_train_score + min_train_delta
    if should_run_guard:
        for task in guard_tasks:
            results.append(
                _run_single_task(
                    paths=paths,
                    config=config,
                    backend=backend,
                    candidate_id=candidate_id,
                    attempt_id=attempt_id,
                    task=task,
                    repo_dir=repo_dir,
                    task_dir=task_dir,
                    output_dir=output_dir,
                    workspace_dir=workspace_dir,
                    reset_snapshot=reset_snapshot,
                    evaluate_hidden=True,
                )
            )
        split_name = "holdout" if holdout_mode else "guard"
        guard_score = backend.aggregate([result for result in results if result.split == split_name], split_name, config.eval)
    return (
        CandidateAttempt(
            attempt_id=attempt_id,
            sample_score=screening_score,
            train_score=train_score,
            guard_score=guard_score,
            wall_clock_seconds=time.time() - started,
            task_results=results,
            setup_commands=setup_commands,
            task_cost_usd=sum(result.task_cost_usd for result in results),
        ),
        blocking_flags,
    )


def _run_single_task(
    paths: SessionPaths,
    config: RunConfig,
    backend,
    candidate_id: str,
    attempt_id: str,
    task: EvalTask,
    repo_dir: Path,
    task_dir: Path,
    output_dir: Path,
    workspace_dir: Path,
    reset_snapshot: Dict[str, str],
    evaluate_hidden: bool,
) -> TaskResult:
    started = time.time()
    sync_snapshot(reset_snapshot, repo_dir)
    clear_directory(task_dir)
    clear_directory(output_dir)
    clear_directory(workspace_dir)
    backend.prepare_task_workspace(task, workspace_dir)
    input_path = task_dir / config.agent.entry_contract.input_file
    input_payload = backend.public_task_payload(task)
    write_json(input_path, input_payload)
    env = _command_environment(config, task_dir, workspace_dir, output_dir)
    before_repo = snapshot_tree(repo_dir)
    before_workspace = snapshot_tree(workspace_dir)
    before_output = snapshot_tree(output_dir)
    command_flags: List[str] = []
    command_block_reason = _validate_command_text(config.agent.run_command, config)
    if command_block_reason:
        command_flags.append(command_block_reason)
        command_record = CommandRecord(
            command=config.agent.run_command,
            exit_code=126,
            stdout="",
            stderr=command_block_reason,
            start_time=now_iso(),
            end_time=now_iso(),
            cwd=str(repo_dir),
        )
    else:
        command_record = run_shell_command(config.agent.run_command, repo_dir, env=env)
        if command_record.exit_code != 0:
            command_flags.append("blocking:run_command_failed")
    after_repo = snapshot_tree(repo_dir)
    after_workspace = snapshot_tree(workspace_dir)
    after_output = snapshot_tree(output_dir)
    changed_files = _prefixed_changed_files(before_repo, after_repo, before_workspace, after_workspace, before_output, after_output)
    task_result = backend.score_task(
        task=task,
        workspace_dir=workspace_dir,
        output_dir=output_dir,
        entry_contract=config.agent.entry_contract,
        command_records=[command_record],
        changed_files=changed_files,
        evaluate_hidden=evaluate_hidden,
    )
    task_result.integrity_flags = sorted(
        set(task_result.integrity_flags + command_flags + _receipt_requirement_flags(config, task_result, changed_files))
    )
    if command_flags:
        task_result.passed = False
        task_result.visible_passed = False
        if task.split != "train":
            task_result.hidden_result = "failed"
    task_result.receipt_path = str(_write_receipt(paths, candidate_id, attempt_id, task, task_result, [command_record], changed_files))
    task_result.duration_seconds = time.time() - started
    task_result.task_cost_usd = 0.0
    return task_result


def _write_receipt(
    paths: SessionPaths,
    candidate_id: str,
    attempt_id: str,
    task: EvalTask,
    task_result: TaskResult,
    command_records: List[CommandRecord],
    changed_files: List[str],
) -> Path:
    before: Dict[str, str] = {}
    after: Dict[str, str] = {}
    # A compact synthetic diff is enough for receipts and audits.
    for relative_path in changed_files:
        after[relative_path] = relative_path
    receipt = RunReceipt(
        task_id=task.task_id,
        candidate_id=candidate_id,
        attempt_id=attempt_id,
        split=task.split,
        commands=list(task_result.commands or command_records),
        files_written=list(changed_files),
        final_worktree_diff=diff_snapshots(before, after),
        final_submission={"task_id": task.task_id, "passed": task_result.passed},
        visible_passed=task_result.visible_passed,
        hidden_result=task_result.hidden_result,
        integrity_flags=list(task_result.integrity_flags),
        stdout_summary=task_result.stdout_summary,
        stderr_summary=task_result.stderr_summary,
        mismatch_summary=task_result.mismatch_summary,
    )
    receipt_path = paths.receipts_dir / candidate_id / attempt_id / (task.task_id + ".json")
    write_json(receipt_path, receipt.to_dict())
    return receipt_path


def _prefixed_changed_files(
    before_repo: Dict[str, str],
    after_repo: Dict[str, str],
    before_workspace: Dict[str, str],
    after_workspace: Dict[str, str],
    before_output: Dict[str, str],
    after_output: Dict[str, str],
) -> List[str]:
    changed = []
    changed.extend("repo/" + path for path in _changed_paths(before_repo, after_repo))
    changed.extend("workspace/" + path for path in _changed_paths(before_workspace, after_workspace))
    changed.extend("output/" + path for path in _changed_paths(before_output, after_output))
    return sorted(changed)


def _command_environment(config: RunConfig, task_dir: Path, workspace_dir: Path, output_dir: Path) -> Dict[str, str]:
    env = dict(os.environ)
    env["SUPERAGENT_TASK_DIR"] = str(task_dir)
    env["SUPERAGENT_WORKSPACE_DIR"] = str(workspace_dir)
    env["SUPERAGENT_OUTPUT_DIR"] = str(output_dir)
    if config.guards.no_network:
        env.update(NETWORK_ENV_OVERRIDES)
        env["SUPERAGENT_NO_NETWORK"] = "1"
    return env


def _validate_command_text(command: str, config: RunConfig) -> str:
    tokens = set(re.findall(r"[A-Za-z0-9_.:/-]+", command))
    for forbidden in config.guards.forbidden_commands:
        if forbidden in tokens:
            return "blocking:forbidden_command:" + forbidden
    return ""


def _receipt_requirement_flags(config: RunConfig, task_result: TaskResult, changed_files: List[str]) -> List[str]:
    required = set(config.guards.receipt_requirements)
    flags: List[str] = []
    if "commands" in required and not task_result.commands:
        flags.append("warning:missing_commands")
    if "files_read" in required:
        flags.append("warning:missing_files_read")
    if "files_written" in required and not changed_files:
        flags.append("warning:missing_files_written")
    if "final_worktree_diff" in required and changed_files and not task_result.changed_files:
        flags.append("warning:missing_diff")
    return flags


def _determine_attempt_verdict(
    attempt: CandidateAttempt,
    parent: CandidateRecord,
    min_train_delta: float,
    max_guard_regression: float,
    blocking_flags: Iterable[str],
) -> str:
    if any(flag.startswith("blocking:") for flag in blocking_flags) or any(
        flag.startswith("blocking:") for flag in _collect_result_flags(attempt.task_results)
    ):
        return "integrity_blocked"
    if attempt.sample_score < float(parent.sample_score or 0.0):
        return "rejected_screening"
    if attempt.train_score < float(parent.train_score or 0.0) + min_train_delta:
        return "rejected_train"
    if attempt.guard_score < float(parent.guard_score or 0.0) - max_guard_regression:
        return "rejected_guard"
    return "eligible_for_accept"


def _is_borderline_candidate(
    attempt: CandidateAttempt,
    parent: CandidateRecord,
    min_train_delta: float,
    max_guard_regression: float,
) -> bool:
    return (
        attempt.train_score == float(parent.train_score or 0.0) + min_train_delta
        and attempt.guard_score == float(parent.guard_score or 0.0) - max_guard_regression
    )


def _summary_attempt(
    attempts: List[CandidateAttempt],
    confirmation_required: bool,
    confirmation_passed: bool,
) -> CandidateAttempt:
    if confirmation_required and confirmation_passed and len(attempts) > 1:
        return min(attempts, key=lambda attempt: (attempt.train_score, attempt.guard_score, -attempt.wall_clock_seconds))
    return attempts[-1]


def _collect_result_flags(task_results: List[TaskResult]) -> List[str]:
    flags: List[str] = []
    for result in task_results:
        flags.extend(result.integrity_flags)
    return sorted(set(flags))


def _build_failure_summary(
    candidate: CandidateRecord,
    summary_attempt: CandidateAttempt,
    parent: CandidateRecord,
) -> Dict[str, object]:
    failing_results = [result for result in summary_attempt.task_results if not result.passed or result.integrity_flags]
    snippets = []
    for result in failing_results[:5]:
        snippet = result.stderr_summary or result.stdout_summary or result.mismatch_summary
        if snippet:
            snippets.append({"task_id": result.task_id, "snippet": snippet})
    return {
        "candidate_id": candidate.candidate_id,
        "parent_id": candidate.parent_id,
        "failing_tasks": [
            {"task_id": result.task_id, "split": result.split, "receipt_path": result.receipt_path}
            for result in failing_results
        ],
        "regression_summary": {
            "parent_sample_score": parent.sample_score,
            "candidate_sample_score": summary_attempt.sample_score,
            "parent_train_score": parent.train_score,
            "candidate_train_score": summary_attempt.train_score,
            "parent_guard_score": parent.guard_score,
            "candidate_guard_score": summary_attempt.guard_score,
        },
        "actionable_snippets": snippets,
        "receipt_references": [result.receipt_path for result in failing_results if result.receipt_path][:10],
        "integrity_flags": list(candidate.integrity_flags),
        "built_in_denylist": BUILTIN_DENYLIST_PATTERNS,
    }


def _candidate_response(candidate: CandidateRecord) -> Dict[str, object]:
    return {
        "candidate_id": candidate.candidate_id,
        "parent_id": candidate.parent_id,
        "verdict": candidate.verdict,
        "sample_score": candidate.sample_score,
        "train_score": candidate.train_score,
        "guard_score": candidate.guard_score,
        "confirmation_rerun_required": candidate.confirmation_rerun_required,
        "confirmation_rerun_passed": candidate.confirmation_rerun_passed,
        "failure_summary": dict(candidate.failure_summary),
        "diff_path": candidate.diff_path,
    }


def _prune_archive(paths: SessionPaths, config: RunConfig, state: SessionState) -> None:
    accepted = [candidate for candidate in list_candidates(paths) if candidate.accepted]
    if len(accepted) <= config.policy.archive_size:
        state.active_archive_ids = [candidate.candidate_id for candidate in accepted if candidate.in_active_archive]
        return
    ranked = sorted(
        accepted,
        key=lambda candidate: (
            float(candidate.train_score or 0.0),
            float(candidate.guard_score or 0.0),
            float(candidate.sample_score or 0.0),
            candidate.created_at,
        ),
        reverse=True,
    )
    keep_ids = {state.current_baseline_id}
    for candidate in ranked:
        if len(keep_ids) >= config.policy.archive_size:
            break
        keep_ids.add(candidate.candidate_id)
    state.active_archive_ids = []
    for candidate in accepted:
        candidate.in_active_archive = candidate.candidate_id in keep_ids
        if candidate.in_active_archive:
            state.active_archive_ids.append(candidate.candidate_id)
        save_candidate(candidate, paths)

