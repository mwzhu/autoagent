"""SQLite experiment logging."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List

from superagent.models import CandidateAttempt, CandidateEvaluation
from superagent.utils import ensure_dir, now_iso


def init_db(path: Path) -> sqlite3.Connection:
    ensure_dir(path.parent)
    connection = sqlite3.connect(str(path))
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            adapter_name TEXT NOT NULL,
            backend_name TEXT NOT NULL,
            eval_target TEXT NOT NULL,
            config_path TEXT NOT NULL,
            screening_sample TEXT NOT NULL,
            cumulative_meta_cost_usd REAL NOT NULL,
            cumulative_task_cost_usd REAL NOT NULL,
            cumulative_wall_clock_seconds REAL NOT NULL,
            duplicate_skip_count INTEGER NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS candidates (
            candidate_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            parent_id TEXT NOT NULL,
            mutation_type TEXT NOT NULL,
            adapter_name TEXT NOT NULL,
            backend_name TEXT NOT NULL,
            sample_score REAL NOT NULL,
            train_score REAL NOT NULL,
            guard_score REAL NOT NULL,
            accepted INTEGER NOT NULL,
            integrity_blocked INTEGER NOT NULL,
            audit_blocked INTEGER NOT NULL,
            wall_clock_seconds REAL NOT NULL,
            config_path TEXT NOT NULL,
            audit_flags TEXT NOT NULL,
            meta_cost_usd REAL NOT NULL,
            task_cost_usd REAL NOT NULL,
            duplicate_skip_count INTEGER NOT NULL,
            confirmation_rerun_required INTEGER NOT NULL,
            confirmation_rerun_passed INTEGER NOT NULL,
            attempt_ids TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS candidate_attempts (
            attempt_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            sample_score REAL NOT NULL,
            train_score REAL NOT NULL,
            guard_score REAL NOT NULL,
            integrity_blocked INTEGER NOT NULL,
            audit_blocked INTEGER NOT NULL,
            wall_clock_seconds REAL NOT NULL,
            audit_flags TEXT NOT NULL,
            meta_cost_usd REAL NOT NULL,
            task_cost_usd REAL NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS task_results (
            attempt_id TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            split TEXT NOT NULL,
            passed INTEGER NOT NULL,
            score REAL NOT NULL,
            visible_passed INTEGER NOT NULL,
            hidden_result TEXT NOT NULL,
            duration_seconds REAL NOT NULL,
            task_cost_usd REAL NOT NULL,
            receipt_path TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def create_run_record(
    connection: sqlite3.Connection,
    run_id: str,
    adapter_name: str,
    backend_name: str,
    eval_target: str,
    config_path: str,
    screening_sample: List[str],
) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO runs(
            run_id, created_at, adapter_name, backend_name, eval_target, config_path,
            screening_sample, cumulative_meta_cost_usd, cumulative_task_cost_usd,
            cumulative_wall_clock_seconds, duplicate_skip_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now_iso(),
            adapter_name,
            backend_name,
            eval_target,
            config_path,
            ",".join(screening_sample),
            0.0,
            0.0,
            0.0,
            0,
        ),
    )
    connection.commit()


def update_run_record(
    connection: sqlite3.Connection,
    run_id: str,
    cumulative_meta_cost_usd: float,
    cumulative_task_cost_usd: float,
    cumulative_wall_clock_seconds: float,
    duplicate_skip_count: int,
) -> None:
    connection.execute(
        """
        UPDATE runs
        SET cumulative_meta_cost_usd = ?,
            cumulative_task_cost_usd = ?,
            cumulative_wall_clock_seconds = ?,
            duplicate_skip_count = ?
        WHERE run_id = ?
        """,
        (
            cumulative_meta_cost_usd,
            cumulative_task_cost_usd,
            cumulative_wall_clock_seconds,
            duplicate_skip_count,
            run_id,
        ),
    )
    connection.commit()


def log_candidate(connection: sqlite3.Connection, run_id: str, candidate: CandidateEvaluation) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO candidates(
            candidate_id, run_id, parent_id, mutation_type, adapter_name, backend_name,
            sample_score, train_score, guard_score, accepted, integrity_blocked, audit_blocked,
            wall_clock_seconds, config_path, audit_flags, meta_cost_usd, task_cost_usd,
            duplicate_skip_count, confirmation_rerun_required, confirmation_rerun_passed, attempt_ids
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate.candidate_id,
            run_id,
            candidate.parent_id,
            candidate.mutation_type,
            candidate.adapter_name,
            candidate.backend_name,
            candidate.sample_score,
            candidate.train_score,
            candidate.guard_score,
            1 if candidate.accepted else 0,
            1 if candidate.integrity_blocked else 0,
            1 if candidate.audit_blocked else 0,
            candidate.wall_clock_seconds,
            candidate.config_path,
            ",".join(candidate.audit_flags),
            candidate.meta_cost_usd,
            candidate.task_cost_usd,
            candidate.duplicate_skip_count,
            1 if candidate.confirmation_rerun_required else 0,
            1 if candidate.confirmation_rerun_passed else 0,
            ",".join(candidate.attempt_ids),
        ),
    )
    for attempt in candidate.attempts:
        log_candidate_attempt(connection, candidate.candidate_id, attempt)
    connection.commit()


def log_candidate_attempt(connection: sqlite3.Connection, candidate_id: str, attempt: CandidateAttempt) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO candidate_attempts(
            attempt_id, candidate_id, sample_score, train_score, guard_score,
            integrity_blocked, audit_blocked, wall_clock_seconds, audit_flags,
            meta_cost_usd, task_cost_usd
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attempt.attempt_id,
            candidate_id,
            attempt.sample_score,
            attempt.train_score,
            attempt.guard_score,
            1 if attempt.integrity_blocked else 0,
            1 if attempt.audit_blocked else 0,
            attempt.wall_clock_seconds,
            ",".join(attempt.audit_flags),
            attempt.meta_cost_usd,
            attempt.task_cost_usd,
        ),
    )
    connection.execute("DELETE FROM task_results WHERE attempt_id = ?", (attempt.attempt_id,))
    for result in attempt.task_results:
        connection.execute(
            """
            INSERT INTO task_results(
                attempt_id, candidate_id, task_id, split, passed, score, visible_passed,
                hidden_result, duration_seconds, task_cost_usd, receipt_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt.attempt_id,
                candidate_id,
                result.task_id,
                result.split,
                1 if result.passed else 0,
                result.score,
                1 if result.visible_passed else 0,
                result.hidden_result,
                result.duration_seconds,
                result.task_cost_usd,
                result.receipt_path,
            ),
        )


def fetch_run(connection: sqlite3.Connection) -> Dict[str, object]:
    row = connection.execute(
        """
        SELECT run_id, created_at, adapter_name, backend_name, eval_target, config_path,
               screening_sample, cumulative_meta_cost_usd, cumulative_task_cost_usd,
               cumulative_wall_clock_seconds, duplicate_skip_count
        FROM runs
        ORDER BY created_at ASC
        LIMIT 1
        """
    ).fetchone()
    if row is None:
        return {}
    return {
        "run_id": row[0],
        "created_at": row[1],
        "adapter_name": row[2],
        "backend_name": row[3],
        "eval_target": row[4],
        "config_path": row[5],
        "screening_sample": [item for item in row[6].split(",") if item],
        "cumulative_meta_cost_usd": row[7],
        "cumulative_task_cost_usd": row[8],
        "cumulative_wall_clock_seconds": row[9],
        "duplicate_skip_count": row[10],
    }


def fetch_candidates(connection: sqlite3.Connection) -> List[Dict[str, object]]:
    cursor = connection.execute(
        """
        SELECT candidate_id, parent_id, mutation_type, adapter_name, backend_name,
               sample_score, train_score, guard_score, accepted, integrity_blocked,
               audit_blocked, wall_clock_seconds, config_path, audit_flags, meta_cost_usd,
               task_cost_usd, duplicate_skip_count, confirmation_rerun_required,
               confirmation_rerun_passed, attempt_ids
        FROM candidates
        ORDER BY rowid ASC
        """
    )
    rows = []
    for row in cursor.fetchall():
        rows.append(
            {
                "candidate_id": row[0],
                "parent_id": row[1],
                "mutation_type": row[2],
                "adapter_name": row[3],
                "backend_name": row[4],
                "sample_score": row[5],
                "train_score": row[6],
                "guard_score": row[7],
                "accepted": bool(row[8]),
                "integrity_blocked": bool(row[9]),
                "audit_blocked": bool(row[10]),
                "wall_clock_seconds": row[11],
                "config_path": row[12],
                "audit_flags": [flag for flag in row[13].split(",") if flag],
                "meta_cost_usd": row[14],
                "task_cost_usd": row[15],
                "duplicate_skip_count": row[16],
                "confirmation_rerun_required": bool(row[17]),
                "confirmation_rerun_passed": bool(row[18]),
                "attempt_ids": [item for item in row[19].split(",") if item],
            }
        )
    return rows
