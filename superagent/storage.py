"""Filesystem-backed session storage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from superagent.config import RunConfig, load_run_config, save_run_config
from superagent.models import CandidateRecord, SessionState
from superagent.utils import ensure_dir, read_json, write_json


MARKER_DIR_NAME = ".superagent"


@dataclass(frozen=True)
class SessionPaths:
    run_dir: Path

    @property
    def control_dir(self) -> Path:
        return self.run_dir / MARKER_DIR_NAME

    @property
    def config_path(self) -> Path:
        return self.control_dir / "config.yaml"

    @property
    def state_path(self) -> Path:
        return self.control_dir / "state.json"

    @property
    def candidates_dir(self) -> Path:
        return self.control_dir / "history"

    @property
    def receipts_dir(self) -> Path:
        return self.control_dir / "receipts"

    @property
    def diffs_dir(self) -> Path:
        return self.control_dir / "diffs"

    @property
    def evaluations_dir(self) -> Path:
        return self.control_dir / "evaluations"

    @property
    def canonical_repo_dir(self) -> Path:
        return self.control_dir / "canonical_repo"

    @property
    def holdout_summary_path(self) -> Path:
        return self.control_dir / "holdout_summary.json"

    @property
    def report_path(self) -> Path:
        return self.control_dir / "report.md"


def session_paths(run_dir: Path) -> SessionPaths:
    return SessionPaths(run_dir=run_dir.resolve())


def ensure_session_dirs(paths: SessionPaths) -> None:
    ensure_dir(paths.control_dir)
    ensure_dir(paths.candidates_dir)
    ensure_dir(paths.receipts_dir)
    ensure_dir(paths.diffs_dir)
    ensure_dir(paths.evaluations_dir)


def is_managed_workspace(path: Path) -> bool:
    return (path / MARKER_DIR_NAME).is_dir()


def save_managed_config(config: RunConfig, paths: SessionPaths) -> None:
    ensure_dir(paths.control_dir)
    save_run_config(config, paths.config_path)


def load_managed_config(paths: SessionPaths) -> RunConfig:
    return load_run_config(paths.config_path)


def save_session_state(state: SessionState, paths: SessionPaths) -> None:
    write_json(paths.state_path, state.to_dict())


def load_session_state(paths: SessionPaths) -> SessionState:
    return SessionState.from_dict(_load_mapping(paths.state_path))


def candidate_path(paths: SessionPaths, candidate_id: str) -> Path:
    return paths.candidates_dir / (candidate_id + ".json")


def save_candidate(candidate: CandidateRecord, paths: SessionPaths) -> None:
    write_json(candidate_path(paths, candidate.candidate_id), candidate.to_dict())


def load_candidate(paths: SessionPaths, candidate_id: str) -> CandidateRecord:
    return CandidateRecord.from_dict(_load_mapping(candidate_path(paths, candidate_id)))


def list_candidates(paths: SessionPaths) -> List[CandidateRecord]:
    candidates = [CandidateRecord.from_dict(_load_mapping(path)) for path in sorted(paths.candidates_dir.glob("*.json"))]
    return sorted(candidates, key=lambda candidate: (candidate.created_at, candidate.candidate_id))


def _load_mapping(path: Path) -> dict:
    data = read_json(path)
    assert isinstance(data, dict), "{} must contain a JSON object.".format(path)
    return data
