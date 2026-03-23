"""YAML-backed configuration objects."""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Union

import yaml

from superagent.models import ConfigChange


ProviderType = Literal["anthropic", "openai", "openai_compatible", "builtin"]


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
class BudgetConfig:
    max_iterations: int = 100
    max_accepts: int = 20
    max_meta_api_cost_usd: float = 200.0
    max_wall_clock_hours: float = 24.0


@dataclass
class AgentConfig:
    task_provider: ProviderConfig
    meta_provider: ProviderConfig
    system_prompt: str
    tools: List[ToolConfig] = field(default_factory=list)
    orchestration: OrchestrationConfig = field(default_factory=OrchestrationConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    guards: GuardsConfig = field(default_factory=GuardsConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        for key in ("task_provider", "meta_provider", "system_prompt", "tools", "orchestration", "execution", "guards", "budget"):
            assert key in data, "Missing config section: {}".format(key)
        return cls(
            task_provider=load_provider_config(data["task_provider"]),
            meta_provider=load_provider_config(data["meta_provider"]),
            system_prompt=data["system_prompt"],
            tools=[ToolConfig(**tool) for tool in data["tools"]],
            orchestration=OrchestrationConfig(**data["orchestration"]),
            execution=ExecutionConfig(**data["execution"]),
            guards=GuardsConfig(**data["guards"]),
            budget=BudgetConfig(**data["budget"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def clone(self) -> "AgentConfig":
        return AgentConfig.from_dict(copy.deepcopy(self.to_dict()))

    def apply_changes(self, changes: List[ConfigChange]) -> None:
        data = self.to_dict()
        for change in changes:
            assert change.path in MUTABLE_PATHS, "Unsupported mutation path: {}".format(change.path)
            path = change.path.split(".")
            cursor = data
            for part in path[:-1]:
                cursor = cursor[part]
            cursor[path[-1]] = change.value
        mutated = AgentConfig.from_dict(data)
        self.task_provider = mutated.task_provider
        self.meta_provider = mutated.meta_provider
        self.system_prompt = mutated.system_prompt
        self.tools = mutated.tools
        self.orchestration = mutated.orchestration
        self.execution = mutated.execution
        self.guards = mutated.guards
        self.budget = mutated.budget


MUTABLE_PATHS = {
    "system_prompt",
    "orchestration.planning",
    "orchestration.decomposition",
    "orchestration.self_check",
    "execution.max_repair_loops",
    "execution.test_budget",
    "execution.file_read_budget",
    "execution.context_budget",
}


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


def load_agent_config(path: Path) -> AgentConfig:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict), "Agent config must be a mapping."
    return AgentConfig.from_dict(data)


def save_agent_config(config: AgentConfig, path: Path) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config.to_dict(), handle, sort_keys=False)
