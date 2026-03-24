"""Agent adapter interface and factories."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List

from superagent.config import AdapterConfig
from superagent.models import AgentResult, AgentRunInput


class AgentAdapter(ABC):
    name: str

    @abstractmethod
    def run(self, run_input: AgentRunInput, adapter_config: AdapterConfig) -> AgentResult:
        raise NotImplementedError

    @abstractmethod
    def mutable_paths(self, adapter_config: AdapterConfig) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def mutation_context(self, adapter_config: AdapterConfig) -> Dict[str, object]:
        raise NotImplementedError

    @abstractmethod
    def budget_steps(self, adapter_config: AdapterConfig) -> int:
        raise NotImplementedError


def get_agent_adapter(name: str) -> AgentAdapter:
    if name == "builtin":
        from superagent.adapters.builtin import BuiltinAdapter

        return BuiltinAdapter()
    if name == "simple_coder":
        from superagent.adapters.simple_coder import SimpleCoderAdapter

        return SimpleCoderAdapter()
    if name == "mini_swe_agent":
        from superagent.adapters.mini_swe_agent import MiniSweAgentAdapter

        return MiniSweAgentAdapter()
    raise AssertionError("Unsupported adapter: {}".format(name))
