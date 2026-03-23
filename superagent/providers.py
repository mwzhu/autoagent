"""Provider backends and JSON helpers."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple

from superagent.config import (
    AnthropicProviderConfig,
    BuiltinProviderConfig,
    OpenAICompatibleProviderConfig,
    OpenAIProviderConfig,
    ProviderConfig,
)


class ProviderError(RuntimeError):
    """Raised when a provider call fails."""


def _extract_json_object(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if not match:
        raise ProviderError("Provider response did not contain a JSON object.")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ProviderError("Unable to parse provider JSON response.") from exc
    if not isinstance(parsed, dict):
        raise ProviderError("Provider response did not contain a JSON object.")
    return parsed


def _http_json_request(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
) -> Tuple[Dict[str, Any], float]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise ProviderError("HTTP error {}: {}".format(exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        raise ProviderError(str(exc)) from exc
    data = json.loads(body)
    assert isinstance(data, dict), "Provider response body must be a JSON object."
    return data, 0.0


class ProviderClient:
    """Thin wrapper around supported provider APIs."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    def generate_json(self, system_prompt: str, user_prompt: str) -> Tuple[Dict[str, Any], float]:
        if isinstance(self.config, AnthropicProviderConfig):
            return self._anthropic_json(system_prompt, user_prompt, self.config)
        if isinstance(self.config, OpenAIProviderConfig):
            return self._openai_json(system_prompt, user_prompt, self.config, response_format=True)
        if isinstance(self.config, OpenAICompatibleProviderConfig):
            return self._openai_json(system_prompt, user_prompt, self.config, response_format=False)
        if isinstance(self.config, BuiltinProviderConfig):
            raise ProviderError("Builtin providers do not serve remote JSON.")
        raise AssertionError("Unsupported provider config: {}".format(type(self.config).__name__))

    def _anthropic_json(
        self,
        system_prompt: str,
        user_prompt: str,
        config: AnthropicProviderConfig,
    ) -> Tuple[Dict[str, Any], float]:
        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            raise ProviderError("Missing Anthropic API key in {}".format(config.api_key_env))
        payload = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        response, _ = _http_json_request("https://api.anthropic.com/v1/messages", payload, headers)
        content = response["content"]
        text = "".join(part.get("text", "") for part in content if part.get("type") == "text")
        return _extract_json_object(text), 0.0

    def _openai_json(
        self,
        system_prompt: str,
        user_prompt: str,
        config: OpenAIProviderConfig | OpenAICompatibleProviderConfig,
        response_format: bool,
    ) -> Tuple[Dict[str, Any], float]:
        base_url = config.base_url
        if not base_url.endswith("/v1"):
            base_url = base_url.rstrip("/")
        api_key = os.environ.get(config.api_key_env, "") if config.api_key_env else ""
        headers = {"content-type": "application/json"}
        if api_key:
            headers["authorization"] = "Bearer " + api_key
        payload = {
            "model": config.model,
            "temperature": config.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_format:
            payload["response_format"] = {"type": "json_object"}
        response, _ = _http_json_request(base_url + "/chat/completions", payload, headers)
        content = response["choices"][0]["message"]["content"]
        if isinstance(content, list):
            text = "".join(block.get("text", "") for block in content)
        else:
            text = str(content)
        return _extract_json_object(text), 0.0
