"""Core data models for SuperAgent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal


Split = Literal["train", "guard", "holdout"]
HiddenResult = Literal["not_run", "passed", "failed"]
AgentStatus = Literal["completed", "failed"]


@dataclass
class ProviderUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CommandRecord:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    start_time: str
    end_time: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FileEdit:
    path: str
    content: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConfigChange:
    path: str
    value: Any

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MutationProposal:
    mutation_type: str
    reason: str
    changes: List[ConfigChange]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_type": self.mutation_type,
            "reason": self.reason,
            "changes": [change.to_dict() for change in self.changes],
        }


@dataclass
class AgentRunInput:
    task_id: str
    prompt: str
    working_dir: Path
    artifacts_dir: Path
    budget_steps: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["working_dir"] = str(self.working_dir)
        data["artifacts_dir"] = str(self.artifacts_dir)
        return data


@dataclass
class AgentResult:
    status: AgentStatus
    final_message: str
    files_written: List[str]
    commands: List[CommandRecord]
    stdout: str
    stderr: str
    patch_diff: str
    cost_usd: float
    duration_seconds: float
    files_read: List[str] = field(default_factory=list)
    integrity_flags: List[str] = field(default_factory=list)
    exit_code: int = 0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["commands"] = [command.to_dict() for command in self.commands]
        return data


@dataclass
class RunReceipt:
    task_id: str
    candidate_id: str
    split: Split
    commands: List[CommandRecord] = field(default_factory=list)
    files_read: List[str] = field(default_factory=list)
    files_written: List[str] = field(default_factory=list)
    final_worktree_diff: str = ""
    final_submission: Dict[str, Any] = field(default_factory=dict)
    visible_passed: bool = False
    hidden_result: HiddenResult = "not_run"
    integrity_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["commands"] = [command.to_dict() for command in self.commands]
        return data


@dataclass
class EvalTask:
    task_id: str
    split: Split
    prompt: str
    repo_id: str = ""
    category: str = ""
    difficulty: int = 0
    expected_output: str = ""
    mutation_lineage: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    min_test_budget: int = 1
    min_file_read_budget: int = 1
    task_dir: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskResult:
    task_id: str
    split: Split
    passed: bool
    score: float
    visible_passed: bool = False
    hidden_result: HiddenResult = "not_run"
    integrity_flags: List[str] = field(default_factory=list)
    receipt_path: str = ""
    duration_seconds: float = 0.0
    commands: List[CommandRecord] = field(default_factory=list)
    task_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["commands"] = [command.to_dict() for command in self.commands]
        return data


@dataclass
class CandidateAttempt:
    attempt_id: str
    sample_score: float
    train_score: float
    guard_score: float
    integrity_blocked: bool
    audit_blocked: bool
    wall_clock_seconds: float
    task_results: List[TaskResult] = field(default_factory=list)
    audit_flags: List[str] = field(default_factory=list)
    meta_cost_usd: float = 0.0
    task_cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "sample_score": self.sample_score,
            "train_score": self.train_score,
            "guard_score": self.guard_score,
            "integrity_blocked": self.integrity_blocked,
            "audit_blocked": self.audit_blocked,
            "wall_clock_seconds": self.wall_clock_seconds,
            "task_results": [result.to_dict() for result in self.task_results],
            "audit_flags": list(self.audit_flags),
            "meta_cost_usd": self.meta_cost_usd,
            "task_cost_usd": self.task_cost_usd,
        }


@dataclass
class CandidateEvaluation:
    candidate_id: str
    parent_id: str
    mutation_type: str
    adapter_name: str
    backend_name: str
    sample_score: float
    train_score: float
    guard_score: float
    integrity_blocked: bool
    audit_blocked: bool
    wall_clock_seconds: float
    accepted: bool = False
    task_results: List[TaskResult] = field(default_factory=list)
    audit_flags: List[str] = field(default_factory=list)
    config_path: str = ""
    meta_cost_usd: float = 0.0
    task_cost_usd: float = 0.0
    duplicate_skip_count: int = 0
    confirmation_rerun_required: bool = False
    confirmation_rerun_passed: bool = False
    attempt_ids: List[str] = field(default_factory=list)
    attempts: List[CandidateAttempt] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "parent_id": self.parent_id,
            "mutation_type": self.mutation_type,
            "adapter_name": self.adapter_name,
            "backend_name": self.backend_name,
            "sample_score": self.sample_score,
            "train_score": self.train_score,
            "guard_score": self.guard_score,
            "integrity_blocked": self.integrity_blocked,
            "audit_blocked": self.audit_blocked,
            "wall_clock_seconds": self.wall_clock_seconds,
            "accepted": self.accepted,
            "task_results": [result.to_dict() for result in self.task_results],
            "audit_flags": list(self.audit_flags),
            "config_path": self.config_path,
            "meta_cost_usd": self.meta_cost_usd,
            "task_cost_usd": self.task_cost_usd,
            "duplicate_skip_count": self.duplicate_skip_count,
            "confirmation_rerun_required": self.confirmation_rerun_required,
            "confirmation_rerun_passed": self.confirmation_rerun_passed,
            "attempt_ids": list(self.attempt_ids),
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }
