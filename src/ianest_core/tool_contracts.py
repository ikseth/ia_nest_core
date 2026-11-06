from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ianest_core.config.schema import DomainConfig


@dataclass(frozen=True)
class ProviderTool:
    provider: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    annotations: dict[str, Any] | None = None


def offered_tools(
    domain: DomainConfig,
    interlocutor_profile: str,
    provider_tools: list[ProviderTool],
) -> list[ProviderTool]:
    return [
        tool
        for tool in provider_tools
        if tool_is_allowed(domain, interlocutor_profile, tool)
    ]


def tool_is_allowed(
    domain: DomainConfig,
    interlocutor_profile: str,
    tool: ProviderTool,
) -> bool:
    policy = domain.tools
    if policy is None or not interlocutor_profile:
        return False
    if tool.provider != policy.provider:
        return False
    allowed_names = policy.allow.get(interlocutor_profile)
    if allowed_names is None or tool.name not in allowed_names:
        return False
    if tool.name in policy.deny:
        return False
    return _is_non_destructive(tool.annotations)


def invocation_is_allowed(
    domain: DomainConfig,
    interlocutor_profile: str,
    provider_tools: list[ProviderTool],
    provider: str,
    tool_name: str,
) -> bool:
    tool = next(
        (
            item
            for item in provider_tools
            if item.provider == provider and item.name == tool_name
        ),
        None,
    )
    return tool is not None and tool_is_allowed(domain, interlocutor_profile, tool)


def _is_non_destructive(annotations: dict[str, Any] | None) -> bool:
    if not annotations:
        return False
    return annotations.get("readOnlyHint") is True or annotations.get("destructiveHint") is False
