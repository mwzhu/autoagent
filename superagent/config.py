"""YAML-backed configuration objects."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Union

import yaml

from superagent.models import ConfigChange


@dataclass
class AnthropicProviderConfig:
    provider_type: Literal["anthropic"]
    model: str
    api_key_env: str
    temperature: float = 0.2
    max_tokens: int = 4096


@dataclass
class OpenAIProviderConfig:
    provider_type: Literal["openai"]
    model: str
    api_key_env: str
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.2
    max_tokens: int = 4096


@dataclass
class OpenAICompatibleProviderConfig:
    provider_type: Literal["openai_compatible"]
    model: str
    base_url: str
    api_key_env: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096


@dataclass
class BuiltinProviderConfig:
    provider_type: Literal["builtin"]
    model: str
    temperature: float = 0.2
    max_tokens: int = 4096


ProviderConfig = Union[
    AnthropicProviderConfig,
    OpenAIProviderConfig,
    OpenAICompatibleProviderConfig,
    BuiltinProviderConfig,
]


@dataclass
class ToolConfig:
    name: str
    enabled: bool = True
    permissions: List[str] = field(default_factory=list)


@dataclass
class OrchestrationConfig:
    planning: bool = False
    decomposition: bool = False
    self_check: bool = True


@dataclass
class ExecutionConfig:
    max_repair_loops: int = 3
    test_budget: int = 3
    file_read_budget: int = 12
    context_budget: int = 12000


@dataclass
class GuardsConfig:
    forbidden_paths: List[str] = field(default_factory=list)
    forbidden_commands: List[str] = field(default_factory=list)
    no_network: bool = True
    receipt_requirements: List[str] = field(
        default_factory=lambda: ["commands", "files_read", "files_written", "final_worktree_diff"]
    )


@dataclass
class OptimizerConfig:
    max_iterations: int = 100
    max_accepts: int = 20
    max_meta_api_cost_usd: float = 200.0
    max_wall_clock_hours: float = 24.0
    screening_sample_size: int = 8
    archive_size: int = 10
    rerun_borderline_accepts: bool = True
    duplicate_retry_limit: int = 5


@dataclass
class BuiltinAdapterConfig:
    system_prompt: str
    tools: List[ToolConfig] = field(default_factory=list)
    orchestration: OrchestrationConfig = field(default_factory=OrchestrationConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)


@dataclass
class SimpleCoderAdapterConfig:
    task_provider: ProviderConfig
    system_prompt: str
    tools: List[ToolConfig] = field(default_factory=list)
    orchestration: OrchestrationConfig = field(default_factory=OrchestrationConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)


@dataclass
class MiniSweAgentAdapterConfig:
    command: str
    model: str
    base_url: str
    api_key_env: str = ""
    instruction_prefix: str = ""
    max_steps: int = 20
    per_action_timeout_sec: int = 90
    max_observation_chars: int = 12000
    tool_mode: Literal["native", "text"] = "native"


AdapterConfig = Union[BuiltinAdapterConfig, SimpleCoderAdapterConfig, MiniSweAgentAdapterConfig]


@dataclass
class AgentSection:
    adapter: Literal["builtin", "simple_coder", "mini_swe_agent"]
    config: AdapterConfig


@dataclass
class CodeBenchmarkEvalConfig:
    benchmark_dir: str
    min_train_delta_tasks: int = 1
    max_guard_regression_tasks: int = 1


@dataclass
class DatasetEvalConfig:
    dataset_path: str
    scorer_type: Literal["exact_match", "python_function"] = "exact_match"
    scorer_path: str = ""
    scorer_function: str = ""
    min_train_delta: float = 1.0
    max_guard_regression: float = 1.0


EvalConfig = Union[CodeBenchmarkEvalConfig, DatasetEvalConfig]


@dataclass
class EvalSection:
    backend: Literal["code_benchmark", "dataset"]
    config: EvalConfig


@dataclass
class RunConfig:
    meta_provider: ProviderConfig
    optimizer: OptimizerConfig
    agent: AgentSection
    eval: EvalSection
    guards: GuardsConfig = field(default_factory=GuardsConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunConfig":
        for key in ("meta_provider", "optimizer", "agent", "eval", "guards"):
            assert key in data, "Missing config section: {}".format(key)
        agent_section = data["agent"]
        eval_section = data["eval"]
        return cls(
            meta_provider=load_provider_config(data["meta_provider"]),
            optimizer=OptimizerConfig(**data["optimizer"]),
            agent=AgentSection(
                adapter=agent_section["adapter"],
                config=load_adapter_config(agent_section["adapter"], agent_section["config"]),
            ),
            eval=EvalSection(
                backend=eval_section["backend"],
                config=load_eval_config(eval_section["backend"], eval_section["config"]),
            ),
            guards=GuardsConfig(**data["guards"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def clone(self) -> "RunConfig":
        return RunConfig.from_dict(copy.deepcopy(self.to_dict()))

    def apply_agent_changes(self, changes: List[ConfigChange], allowed_paths: List[str]) -> None:
        data = self.to_dict()
        agent_config = data["agent"]["config"]
        for change in changes:
            assert change.path in allowed_paths, "Unsupported mutation path: {}".format(change.path)
            cursor = agent_config
            parts = change.path.split(".")
            for part in parts[:-1]:
                cursor = cursor[part]
            cursor[parts[-1]] = change.value
        mutated = RunConfig.from_dict(data)
        self.meta_provider = mutated.meta_provider
        self.optimizer = mutated.optimizer
        self.agent = mutated.agent
        self.eval = mutated.eval
        self.guards = mutated.guards


def load_provider_config(data: Dict[str, Any]) -> ProviderConfig:
    provider_type = data["provider_type"]
    if provider_type == "anthropic":
        return AnthropicProviderConfig(**data)
    if provider_type == "openai":
        return OpenAIProviderConfig(**data)
    if provider_type == "openai_compatible":
        return OpenAICompatibleProviderConfig(**data)
    if provider_type == "builtin":
        return BuiltinProviderConfig(**data)
    raise AssertionError("Unsupported provider type: {}".format(provider_type))


def load_adapter_config(adapter: str, data: Dict[str, Any]) -> AdapterConfig:
    if adapter == "builtin":
        return BuiltinAdapterConfig(
            system_prompt=data["system_prompt"],
            tools=_load_tools(data.get("tools", [])),
            orchestration=OrchestrationConfig(**data.get("orchestration", {})),
            execution=ExecutionConfig(**data.get("execution", {})),
        )
    if adapter == "simple_coder":
        return SimpleCoderAdapterConfig(
            task_provider=load_provider_config(data["task_provider"]),
            system_prompt=data["system_prompt"],
            tools=_load_tools(data.get("tools", [])),
            orchestration=OrchestrationConfig(**data.get("orchestration", {})),
            execution=ExecutionConfig(**data.get("execution", {})),
        )
    if adapter == "mini_swe_agent":
        return MiniSweAgentAdapterConfig(**data)
    raise AssertionError("Unsupported adapter: {}".format(adapter))


def load_eval_config(backend: str, data: Dict[str, Any]) -> EvalConfig:
    if backend == "code_benchmark":
        return CodeBenchmarkEvalConfig(**data)
    if backend == "dataset":
        return DatasetEvalConfig(**data)
    raise AssertionError("Unsupported eval backend: {}".format(backend))


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
    return RunConfig.from_dict(data)


def save_run_config(config: RunConfig, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config.to_dict(), handle, sort_keys=False)


def _load_tools(items: List[Dict[str, Any]]) -> List[ToolConfig]:
    return [ToolConfig(**item) for item in items]
