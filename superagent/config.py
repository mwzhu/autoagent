"""YAML-backed configuration objects for agent sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Literal, Union

import yaml


def _resolve_path(base_dir: Path, raw_path: str) -> str:
    path = Path(raw_path)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return str(path)


def _normalize_repo_root(root: str) -> str:
    raw = root.replace("\\", "/").strip()
    assert raw, "Mutation roots must not be empty."
    pure = PurePosixPath(raw)
    assert not pure.is_absolute(), "Mutation roots must be relative to the managed repo."
    assert ".." not in pure.parts, "Mutation roots must not escape the managed repo."
    normalized = pure.as_posix()
    return "." if normalized in ("", ".") else normalized


def _roots_overlap(left: str, right: str) -> bool:
    left_parts = PurePosixPath(left).parts
    right_parts = PurePosixPath(right).parts
    if left == "." or right == ".":
        return True
    return left_parts[: len(right_parts)] == right_parts or right_parts[: len(left_parts)] == left_parts


@dataclass
class EntryContractConfig:
    input_file: str
    output_mode: Literal["files", "workspace"]
    output_file: str | None = None

    def validate(self) -> None:
        assert self.input_file, "agent.entry_contract.input_file is required."
        assert Path(self.input_file).name == self.input_file, "input_file must be a file name, not a path."
        if self.output_mode == "files":
            assert self.output_file, "output_file is required when output_mode=files."
            assert Path(str(self.output_file)).name == self.output_file, "output_file must be a file name, not a path."
        else:
            assert not self.output_file, "output_file is only valid when output_mode=files."


@dataclass
class MutationBoundaryConfig:
    type: Literal["full_repo", "scoped_roots"]
    mutable_roots: List[str] = field(default_factory=list)
    protected_roots: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MutationBoundaryConfig":
        boundary_type = data["type"]
        if boundary_type == "full_repo":
            mutable_roots = ["."]
            protected_roots: List[str] = []
        elif boundary_type == "scoped_roots":
            mutable_roots = list(data.get("mutable_roots", []))
            protected_roots = list(data.get("protected_roots", []))
            assert mutable_roots, "scoped_roots requires mutable_roots."
        else:
            raise AssertionError("Unsupported mutation boundary type: {}".format(boundary_type))
        boundary = cls(
            type=boundary_type,
            mutable_roots=[_normalize_repo_root(root) for root in mutable_roots],
            protected_roots=[_normalize_repo_root(root) for root in protected_roots],
        )
        boundary.validate()
        return boundary

    def validate(self) -> None:
        assert self.mutable_roots, "At least one mutable root is required."
        for mutable_root in self.mutable_roots:
            for protected_root in self.protected_roots:
                assert not _roots_overlap(
                    mutable_root, protected_root
                ), "Mutable and protected roots must not overlap: {} vs {}".format(mutable_root, protected_root)


@dataclass
class AgentConfig:
    repo_root: str
    run_command: str
    install_command: str = ""
    entry_contract: EntryContractConfig = field(
        default_factory=lambda: EntryContractConfig(input_file="task.json", output_mode="files")
    )
    mutation_boundary: MutationBoundaryConfig = field(
        default_factory=lambda: MutationBoundaryConfig(type="full_repo", mutable_roots=["."], protected_roots=[])
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Path) -> "AgentConfig":
        config = cls(
            repo_root=_resolve_path(base_dir, data["repo_root"]),
            run_command=data["run_command"],
            install_command=data.get("install_command", ""),
            entry_contract=EntryContractConfig(**data["entry_contract"]),
            mutation_boundary=MutationBoundaryConfig.from_dict(data["mutation_boundary"]),
        )
        config.validate()
        return config

    def validate(self) -> None:
        assert self.run_command.strip(), "agent.run_command is required."
        repo_root = Path(self.repo_root)
        assert repo_root.exists() and repo_root.is_dir(), "agent.repo_root must exist and be a directory."
        self.entry_contract.validate()
        self.mutation_boundary.validate()


@dataclass
class PolicyConfig:
    screening_sample_size: int = 8
    archive_size: int = 10
    rerun_borderline_accepts: bool = True
    max_evaluations: int = 100
    max_accepts: int = 20
    max_task_cost_usd: float = 500.0
    max_wall_clock_hours: float = 24.0

    def validate(self) -> None:
        assert self.screening_sample_size > 0, "policy.screening_sample_size must be positive."
        assert self.archive_size > 0, "policy.archive_size must be positive."
        assert self.max_evaluations > 0, "policy.max_evaluations must be positive."
        assert self.max_accepts >= 0, "policy.max_accepts must be non-negative."
        assert self.max_task_cost_usd >= 0.0, "policy.max_task_cost_usd must be non-negative."
        assert self.max_wall_clock_hours > 0.0, "policy.max_wall_clock_hours must be positive."


@dataclass
class GuardsConfig:
    forbidden_commands: List[str] = field(default_factory=list)
    no_network: bool = True
    receipt_requirements: List[str] = field(
        default_factory=lambda: ["commands", "files_written", "final_worktree_diff"]
    )


@dataclass
class CodeBenchmarkEvalConfig:
    backend: Literal["code_benchmark"]
    benchmark_dir: str
    min_train_delta_tasks: int = 1
    max_guard_regression_tasks: int = 1


@dataclass
class DatasetEvalConfig:
    backend: Literal["dataset"]
    dataset_path: str
    scorer_type: Literal["exact_match", "python_function"] = "exact_match"
    scorer_path: str = ""
    scorer_function: str = ""
    min_train_delta: float = 1.0
    max_guard_regression: float = 1.0


EvalConfig = Union[CodeBenchmarkEvalConfig, DatasetEvalConfig]


def load_eval_config(data: Dict[str, Any], base_dir: Path) -> EvalConfig:
    backend = data["backend"]
    if backend == "code_benchmark":
        config = CodeBenchmarkEvalConfig(
            backend="code_benchmark",
            benchmark_dir=_resolve_path(base_dir, data["benchmark_dir"]),
            min_train_delta_tasks=int(data.get("min_train_delta_tasks", 1)),
            max_guard_regression_tasks=int(data.get("max_guard_regression_tasks", 1)),
        )
        return config
    if backend == "dataset":
        config = DatasetEvalConfig(
            backend="dataset",
            dataset_path=_resolve_path(base_dir, data["dataset_path"]),
            scorer_type=data.get("scorer_type", "exact_match"),
            scorer_path=_resolve_path(base_dir, data["scorer_path"]) if data.get("scorer_path") else "",
            scorer_function=data.get("scorer_function", ""),
            min_train_delta=float(data.get("min_train_delta", 1.0)),
            max_guard_regression=float(data.get("max_guard_regression", 1.0)),
        )
        if config.scorer_type == "python_function":
            assert config.scorer_path, "dataset scorer_type=python_function requires scorer_path."
            assert config.scorer_function, "dataset scorer_type=python_function requires scorer_function."
        return config
    raise AssertionError("Unsupported eval backend: {}".format(backend))


@dataclass
class RunConfig:
    agent: AgentConfig
    eval: EvalConfig
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    guards: GuardsConfig = field(default_factory=GuardsConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Path) -> "RunConfig":
        for key in ("agent", "eval", "policy", "guards"):
            assert key in data, "Missing config section: {}".format(key)
        config = cls(
            agent=AgentConfig.from_dict(data["agent"], base_dir),
            eval=load_eval_config(data["eval"], base_dir),
            policy=PolicyConfig(**data["policy"]),
            guards=GuardsConfig(**data["guards"]),
        )
        config.validate()
        return config

    def validate(self) -> None:
        self.agent.validate()
        self.policy.validate()
        if isinstance(self.eval, CodeBenchmarkEvalConfig):
            assert Path(self.eval.benchmark_dir).exists(), "eval.benchmark_dir must exist."
            assert (
                self.agent.entry_contract.output_mode == "workspace"
            ), "code_benchmark requires output_mode=workspace."
        elif isinstance(self.eval, DatasetEvalConfig):
            assert Path(self.eval.dataset_path).exists(), "eval.dataset_path must exist."
            assert self.agent.entry_contract.output_mode == "files", "dataset requires output_mode=files."
        else:
            raise AssertionError("Unsupported eval config: {}".format(type(self.eval).__name__))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def minimum_train_delta(eval_config: EvalConfig) -> float:
    if isinstance(eval_config, CodeBenchmarkEvalConfig):
        return float(eval_config.min_train_delta_tasks)
    if isinstance(eval_config, DatasetEvalConfig):
        return float(eval_config.min_train_delta)
    raise AssertionError("Unsupported eval config: {}".format(type(eval_config).__name__))


def maximum_guard_regression(eval_config: EvalConfig) -> float:
    if isinstance(eval_config, CodeBenchmarkEvalConfig):
        return float(eval_config.max_guard_regression_tasks)
    if isinstance(eval_config, DatasetEvalConfig):
        return float(eval_config.max_guard_regression)
    raise AssertionError("Unsupported eval config: {}".format(type(eval_config).__name__))


def load_run_config(path: Path) -> RunConfig:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict), "Run config must be a mapping."
    return RunConfig.from_dict(data, path.parent.resolve())


def save_run_config(config: RunConfig, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config.to_dict(), handle, sort_keys=False)
