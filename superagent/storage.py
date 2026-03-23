"""SQLite experiment logging."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List

from superagent.models import CandidateEvaluation, TaskResult
from superagent.utils import ensure_dir, now_iso


def init_db(path: Path) -> sqlite3.Connection:
    ensure_dir(path.parent)
    connection = sqlite3.connect(str(path))
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            benchmark_dir TEXT NOT NULL,
            config_path TEXT NOT NULL,
            screening_sample TEXT NOT NULL
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
            train_score INTEGER NOT NULL,
            guard_score INTEGER NOT NULL,
            integrity_blocked INTEGER NOT NULL,
            audit_blocked INTEGER NOT NULL,
            wall_clock_seconds REAL NOT NULL,
            config_path TEXT NOT NULL,
            audit_flags TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS task_results (
            candidate_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            split TEXT NOT NULL,
            visible_passed INTEGER NOT NULL,
            hidden_result TEXT NOT NULL,
            duration_seconds REAL NOT NULL,
            receipt_path TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def create_run_record(
    connection: sqlite3.Connection,
    run_id: str,
    benchmark_dir: str,
    config_path: str,
    screening_sample: List[str],
) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO runs(run_id, created_at, benchmark_dir, config_path, screening_sample) VALUES (?, ?, ?, ?, ?)",
        (run_id, now_iso(), benchmark_dir, config_path, ",".join(screening_sample)),
    )
    connection.commit()


def log_candidate(connection: sqlite3.Connection, run_id: str, candidate: CandidateEvaluation) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO candidates(
            candidate_id, run_id, parent_id, mutation_type, train_score, guard_score,
            integrity_blocked, audit_blocked, wall_clock_seconds, config_path, audit_flags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate.candidate_id,
            run_id,
            candidate.parent_id,
            candidate.mutation_type,
            candidate.train_score,
            candidate.guard_score,
            1 if candidate.integrity_blocked else 0,
            1 if candidate.audit_blocked else 0,
            candidate.wall_clock_seconds,
            candidate.config_path,
            ",".join(candidate.audit_flags),
        ),
    )
    for result in candidate.task_results:
        connection.execute(
            """
            INSERT INTO task_results(
                candidate_id, task_id, split, visible_passed, hidden_result, duration_seconds, receipt_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate.candidate_id,
                result.task_id,
                result.split,
                1 if result.visible_passed else 0,
                result.hidden_result,
                result.duration_seconds,
                result.receipt_path,
            ),
        )
    connection.commit()


def fetch_candidates(connection: sqlite3.Connection) -> List[Dict[str, object]]:
    cursor = connection.execute(
        """
        SELECT candidate_id, parent_id, mutation_type, train_score, guard_score,
               integrity_blocked, audit_blocked, wall_clock_seconds, config_path, audit_flags
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
                "train_score": row[3],
                "guard_score": row[4],
                "integrity_blocked": bool(row[5]),
                "audit_blocked": bool(row[6]),
                "wall_clock_seconds": row[7],
                "config_path": row[8],
                "audit_flags": [flag for flag in row[9].split(",") if flag],
            }
        )
    return rows
