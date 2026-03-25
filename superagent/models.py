"""Core data models for SuperAgent agent sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal


Split = Literal["train", "guard", "holdout"]
HiddenOutcome = Literal["not_run", "passed", "failed"]
Verdict = Literal[
    "baseline",
    "duplicate",
    "integrity_blocked",
    "rejected_screening",
    "rejected_train",
    "rejected_guard",
    "eligible_for_accept",
]


def _command_records_from_list(items: List[Dict[str, Any]]) -> List["CommandRecord"]:
    return [CommandRecord(**item) for item in items]


@dataclass
class CommandRecord:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    start_time: str
    end_time: str
    cwd: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvalTask:
    task_id: str
    split: Split
    prompt: str
    category: str = ""
    difficulty: int = 0
    repo_id: str = ""
    expected_output: str = ""
    public_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunReceipt:
    task_id: str
    candidate_id: str
    attempt_id: str
    split: Split
    commands: List[CommandRecord] = field(default_factory=list)
    files_read: List[str] = field(default_factory=list)
    files_written: List[str] = field(default_factory=list)
    final_worktree_diff: str = ""
    final_submission: Dict[str, Any] = field(default_factory=dict)
    visible_passed: bool = False
    hidden_result: HiddenOutcome = "not_run"
    integrity_flags: List[str] = field(default_factory=list)
    stdout_summary: str = ""
    stderr_summary: str = ""
    mismatch_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["commands"] = [command.to_dict() for command in self.commands]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunReceipt":
        return cls(
            task_id=data["task_id"],
            candidate_id=data["candidate_id"],
            attempt_id=data["attempt_id"],
            split=data["split"],
            commands=_command_records_from_list(data.get("commands", [])),
            files_read=list(data.get("files_read", [])),
            files_written=list(data.get("files_written", [])),
            final_worktree_diff=data.get("final_worktree_diff", ""),
            final_submission=dict(data.get("final_submission", {})),
            visible_passed=bool(data.get("visible_passed", False)),
            hidden_result=data.get("hidden_result", "not_run"),
            integrity_flags=list(data.get("integrity_flags", [])),
            stdout_summary=data.get("stdout_summary", ""),
            stderr_summary=data.get("stderr_summary", ""),
            mismatch_summary=data.get("mismatch_summary", ""),
        )


@dataclass
class TaskResult:
    task_id: str
    split: Split
    passed: bool
    score: float
    visible_passed: bool = False
    hidden_result: HiddenOutcome = "not_run"
    integrity_flags: List[str] = field(default_factory=list)
    commands: List[CommandRecord] = field(default_factory=list)
    changed_files: List[str] = field(default_factory=list)
    stdout_summary: str = ""
    stderr_summary: str = ""
    mismatch_summary: str = ""
    receipt_path: str = ""
    duration_seconds: float = 0.0
    task_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["commands"] = [command.to_dict() for command in self.commands]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskResult":
        return cls(
            task_id=data["task_id"],
            split=data["split"],
            passed=bool(data["passed"]),
            score=float(data["score"]),
            visible_passed=bool(data.get("visible_passed", False)),
            hidden_result=data.get("hidden_result", "not_run"),
            integrity_flags=list(data.get("integrity_flags", [])),
            commands=_command_records_from_list(data.get("commands", [])),
            changed_files=list(data.get("changed_files", [])),
            stdout_summary=data.get("stdout_summary", ""),
            stderr_summary=data.get("stderr_summary", ""),
            mismatch_summary=data.get("mismatch_summary", ""),
            receipt_path=data.get("receipt_path", ""),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            task_cost_usd=float(data.get("task_cost_usd", 0.0)),
        )


@dataclass
class CandidateAttempt:
    attempt_id: str
    sample_score: float
    train_score: float
    guard_score: float
    wall_clock_seconds: float
    task_results: List[TaskResult] = field(default_factory=list)
    setup_commands: List[CommandRecord] = field(default_factory=list)
    task_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "sample_score": self.sample_score,
            "train_score": self.train_score,
            "guard_score": self.guard_score,
            "wall_clock_seconds": self.wall_clock_seconds,
            "task_results": [result.to_dict() for result in self.task_results],
            "setup_commands": [command.to_dict() for command in self.setup_commands],
            "task_cost_usd": self.task_cost_usd,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateAttempt":
        return cls(
            attempt_id=data["attempt_id"],
            sample_score=float(data["sample_score"]),
            train_score=float(data["train_score"]),
            guard_score=float(data["guard_score"]),
            wall_clock_seconds=float(data.get("wall_clock_seconds", 0.0)),
            task_results=[TaskResult.from_dict(item) for item in data.get("task_results", [])],
            setup_commands=_command_records_from_list(data.get("setup_commands", [])),
            task_cost_usd=float(data.get("task_cost_usd", 0.0)),
        )


@dataclass
class CandidateRecord:
    candidate_id: str
    parent_id: str
    created_at: str
    verdict: Verdict
    accepted: bool = False
    in_active_archive: bool = False
    accepted_commit_id: str = ""
    workspace_hash: str = ""
    candidate_fingerprint: str = ""
    diff_path: str = ""
    sample_score: float | None = None
    train_score: float | None = None
    guard_score: float | None = None
    wall_clock_seconds: float = 0.0
    task_cost_usd: float = 0.0
    confirmation_rerun_required: bool = False
    confirmation_rerun_passed: bool = False
    integrity_flags: List[str] = field(default_factory=list)
    failure_summary: Dict[str, Any] = field(default_factory=dict)
    attempt_ids: List[str] = field(default_factory=list)
    attempts: List[CandidateAttempt] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "verdict": self.verdict,
            "accepted": self.accepted,
            "in_active_archive": self.in_active_archive,
            "accepted_commit_id": self.accepted_commit_id,
            "workspace_hash": self.workspace_hash,
            "candidate_fingerprint": self.candidate_fingerprint,
            "diff_path": self.diff_path,
            "sample_score": self.sample_score,
            "train_score": self.train_score,
            "guard_score": self.guard_score,
            "wall_clock_seconds": self.wall_clock_seconds,
            "task_cost_usd": self.task_cost_usd,
            "confirmation_rerun_required": self.confirmation_rerun_required,
            "confirmation_rerun_passed": self.confirmation_rerun_passed,
            "integrity_flags": list(self.integrity_flags),
            "failure_summary": dict(self.failure_summary),
            "attempt_ids": list(self.attempt_ids),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidateRecord":
        return cls(
            candidate_id=data["candidate_id"],
            parent_id=data["parent_id"],
            created_at=data["created_at"],
            verdict=data["verdict"],
            accepted=bool(data.get("accepted", False)),
            in_active_archive=bool(data.get("in_active_archive", False)),
            accepted_commit_id=data.get("accepted_commit_id", ""),
            workspace_hash=data.get("workspace_hash", ""),
            candidate_fingerprint=data.get("candidate_fingerprint", ""),
            diff_path=data.get("diff_path", ""),
            sample_score=_optional_float(data.get("sample_score")),
            train_score=_optional_float(data.get("train_score")),
            guard_score=_optional_float(data.get("guard_score")),
            wall_clock_seconds=float(data.get("wall_clock_seconds", 0.0)),
            task_cost_usd=float(data.get("task_cost_usd", 0.0)),
            confirmation_rerun_required=bool(data.get("confirmation_rerun_required", False)),
            confirmation_rerun_passed=bool(data.get("confirmation_rerun_passed", False)),
            integrity_flags=list(data.get("integrity_flags", [])),
            failure_summary=dict(data.get("failure_summary", {})),
            attempt_ids=list(data.get("attempt_ids", [])),
            attempts=[CandidateAttempt.from_dict(item) for item in data.get("attempts", [])],
        )


@dataclass
class SessionState:
    run_id: str
    created_at: str
    config_path: str
    imported_repo_root: str
    backend_name: str
    current_baseline_id: str
    active_parent_id: str
    last_evaluated_candidate_id: str = ""
    last_evaluated_candidate_fingerprint: str = ""
    last_evaluated_workspace_hash: str = ""
    screening_sample_ids: List[str] = field(default_factory=list)
    evaluation_count: int = 0
    accept_count: int = 0
    cumulative_task_cost_usd: float = 0.0
    cumulative_wall_clock_seconds: float = 0.0
    next_candidate_number: int = 1
    active_archive_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        return cls(
            run_id=data["run_id"],
            created_at=data["created_at"],
            config_path=data["config_path"],
            imported_repo_root=data["imported_repo_root"],
            backend_name=data["backend_name"],
            current_baseline_id=data["current_baseline_id"],
            active_parent_id=data["active_parent_id"],
            last_evaluated_candidate_id=data.get("last_evaluated_candidate_id", ""),
            last_evaluated_candidate_fingerprint=data.get("last_evaluated_candidate_fingerprint", ""),
            last_evaluated_workspace_hash=data.get("last_evaluated_workspace_hash", ""),
            screening_sample_ids=list(data.get("screening_sample_ids", [])),
            evaluation_count=int(data.get("evaluation_count", 0)),
            accept_count=int(data.get("accept_count", 0)),
            cumulative_task_cost_usd=float(data.get("cumulative_task_cost_usd", 0.0)),
            cumulative_wall_clock_seconds=float(data.get("cumulative_wall_clock_seconds", 0.0)),
            next_candidate_number=int(data.get("next_candidate_number", 1)),
            active_archive_ids=list(data.get("active_archive_ids", [])),
        )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def candidate_scores(candidate: CandidateRecord) -> tuple[float, float, float]:
    return (
        float(candidate.sample_score or 0.0),
        float(candidate.train_score or 0.0),
        float(candidate.guard_score or 0.0),
    )


def candidate_receipt_paths(candidate: CandidateRecord) -> List[Path]:
    paths: List[Path] = []
    for attempt in candidate.attempts:
        for result in attempt.task_results:
            if result.receipt_path:
                paths.append(Path(result.receipt_path))
    return paths
