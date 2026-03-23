"""Core data models for SuperAgent."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal


Split = Literal["train", "guard", "holdout"]
HiddenResult = Literal["not_run", "passed", "failed"]


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
class RepairProposal:
    rationale: str
    edits: List[FileEdit]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rationale": self.rationale,
            "edits": [edit.to_dict() for edit in self.edits],
        }


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
    repo_id: str
    category: str
    difficulty: int
    prompt: str
    visible_test_cmd: str
    hidden_test_cmd: str
    expected_artifact: str
    mutation_lineage: List[str]
    split: Split
    required_capabilities: List[str] = field(default_factory=list)
    min_test_budget: int = 1
    min_file_read_budget: int = 1
    task_dir: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskResult:
    task_id: str
    split: Split
    visible_passed: bool
    hidden_result: HiddenResult
    integrity_flags: List[str] = field(default_factory=list)
    receipt_path: str = ""
    duration_seconds: float = 0.0

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
class CandidateEvaluation:
    candidate_id: str
    parent_id: str
    mutation_type: str
    train_score: int
    guard_score: int
    integrity_blocked: bool
    audit_blocked: bool
    wall_clock_seconds: float
    task_results: List[TaskResult] = field(default_factory=list)
    audit_flags: List[str] = field(default_factory=list)
    config_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "parent_id": self.parent_id,
            "mutation_type": self.mutation_type,
            "train_score": self.train_score,
            "guard_score": self.guard_score,
            "integrity_blocked": self.integrity_blocked,
            "audit_blocked": self.audit_blocked,
            "wall_clock_seconds": self.wall_clock_seconds,
            "task_results": [result.to_dict() for result in self.task_results],
            "audit_flags": list(self.audit_flags),
            "config_path": self.config_path,
        }
