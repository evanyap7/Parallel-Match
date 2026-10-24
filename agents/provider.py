"""Chat providers.

Two interchangeable implementations:

- TemplateProvider: deterministic phrasing assembled in plain code. No
  network, no model. This is the default in development, CI and tests, and
  the guaranteed fallback in production.
- AgentFrameworkProvider: Microsoft Agent Framework Agent backed by Azure AI
  Foundry (agent-framework's FoundryChatClient). Used in deployment when
  PM_AGENT_BACKEND=foundry and credentials are configured.

Selection happens in get_provider(); the agents never know which one they
got. Every provider output passes guardrails.check_output against the fact
bundle and falls back to the template phrasing if it does not.
"""

from __future__ import annotations

import json
import os
from typing import Protocol

from .guardrails import check_output


class ChatProvider(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


class TemplateProvider:
    """Offline, deterministic. complete() is a pass-through: the caller has
    already built the template text and sends it as `user`, so the whole
    pipeline runs identically with or without a model."""

    name = "template"

    def complete(self, system: str, user: str) -> str:
        return user


class AgentFrameworkProvider:
    """Microsoft Agent Framework Agent on Azure AI Foundry."""

    name = "agent-framework/foundry"

    def __init__(self, project_endpoint: str, model: str, credential=None):
        from agent_framework import Agent
        from agent_framework.foundry import FoundryChatClient

        if credential is None:
            from azure.identity import DefaultAzureCredential
            credential = DefaultAzureCredential()
        self._client = FoundryChatClient(
            project_endpoint=project_endpoint,
            model=model,
            credential=credential,
        )
        self._instructions = (
            "You are a careful football broadcast writer for a synthetic "
            "league. Use only the facts given. Never add numbers that are "
            "not in the facts. Never judge officials, players or decisions: "
            "state what was decided and what the relevant Law says. Keep to "
            "at most three short sentences."
        )
        self._agent = Agent(
            client=self._client,
            name="parallel-match-writer",
            instructions=self._instructions,
        )

    def complete(self, system: str, user: str) -> str:
        result = self._agent.run(f"{system}\n\n{user}")
        # Agent Framework results expose the final text; be defensive about
        # the exact attribute across preview versions.
        for attr in ("text", "output", "content"):
            value = getattr(result, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        messages = getattr(result, "messages", None) or []
        if messages:
            last = messages[-1]
            content = getattr(last, "content", None)
            if content is None and isinstance(last, dict):
                content = last.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        raise RuntimeError("agent-framework returned no text")


def get_provider(backend: str | None = None) -> ChatProvider:
    """Provider per PM_AGENT_BACKEND: 'template' (default) or 'foundry'."""
    backend = (backend or os.environ.get("PM_AGENT_BACKEND", "template")).lower()
    if backend in ("foundry", "azure", "agent-framework"):
        return AgentFrameworkProvider(
            project_endpoint=os.environ["AZURE_AI_FOUNDRY_PROJECT_ENDPOINT"],
            model=os.environ.get("AZURE_AI_FOUNDRY_MODEL", "gpt-4o-mini"),
        )
    return TemplateProvider()


def phrase(provider: ChatProvider | None, system: str, facts: dict,
           template_text: str, polish: bool = True) -> tuple[str, bool]:
    """Run one agent utterance through the guardrail pipeline.

    Returns (text, fell_back). The template text is the deterministic
    phrasing of the facts; a model provider, when configured, rewrites it
    for style. If the rewrite fails guardrails (or errors), the template
    text is returned instead.
    """
    if provider is None or isinstance(provider, TemplateProvider) or not polish:
        return template_text, False
    user = (
        "Facts (JSON, the only source of truth):\n"
        + json.dumps(facts, sort_keys=True, default=str)
        + "\n\nReference phrasing (deterministic; rephrase for broadcast "
          "style without changing any fact or number):\n"
        + template_text
    )
    try:
        text = provider.complete(system, user)
    except Exception:
        return template_text, True
    if check_output(text, facts):
        return template_text, True
    return text, False
