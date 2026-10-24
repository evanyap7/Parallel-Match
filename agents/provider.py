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


class _LoopThread:
    """One long-lived asyncio loop on a daemon thread.

    Agent Framework's Agent.run() is async, and the Foundry client holds an
    aiohttp session bound to the loop that created it. FastAPI runs our sync
    endpoints in a thread pool, so every call is handed to this one loop and
    waited on with a timeout.
    """

    def __init__(self):
        import asyncio
        import threading

        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever,
                                        name="foundry-loop", daemon=True)
        self._thread.start()

    def run(self, coro, timeout: float):
        import asyncio

        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)


class AgentFrameworkProvider:
    """Microsoft Agent Framework Agent on Azure AI Foundry.

    Auth is keyless: azure.identity's async DefaultAzureCredential, which is
    the Container App's managed identity in Azure and `az login` locally.
    """

    name = "agent-framework/foundry"

    def __init__(self, project_endpoint: str, model: str, credential=None,
                 timeout_s: float | None = None):
        from agent_framework import Agent
        from agent_framework.foundry import FoundryChatClient

        self.model = model
        self.timeout_s = timeout_s or float(os.environ.get("PM_AGENT_TIMEOUT_S", "8"))
        # After a failure, skip the model for a while so a down model costs
        # one timeout, not one per utterance (callers fall back to templates).
        self.cooldown_s = float(os.environ.get("PM_AGENT_COOLDOWN_S", "60"))
        self._down_until = 0.0
        self.last_error: str | None = None
        self._loop = _LoopThread()
        if credential is None:
            # The Foundry client is async (azure.ai.projects.aio), so it needs
            # an async credential. ManagedIdentityCredential is tried first
            # inside DefaultAzureCredential when running in Container Apps.
            client_id = os.environ.get("AZURE_CLIENT_ID") or None
            if os.environ.get("IDENTITY_ENDPOINT"):   # set by Container Apps
                from azure.identity.aio import ManagedIdentityCredential
                credential = ManagedIdentityCredential(client_id=client_id)
            else:                                     # local: az login etc.
                from azure.identity.aio import DefaultAzureCredential
                credential = DefaultAzureCredential(managed_identity_client_id=client_id)
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

    @staticmethod
    def _text(result) -> str:
        # AgentResponse exposes .text; stay defensive across versions.
        for attr in ("text", "output", "content"):
            value = getattr(result, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
        messages = getattr(result, "messages", None) or []
        if messages:
            last = messages[-1]
            content = getattr(last, "text", None) or getattr(last, "content", None)
            if content is None and isinstance(last, dict):
                content = last.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
        raise RuntimeError("agent-framework returned no text")

    def complete(self, system: str, user: str) -> str:
        import time

        if time.monotonic() < self._down_until:
            raise RuntimeError(f"model cooling down after: {self.last_error}")
        try:
            result = self._loop.run(self._agent.run(f"{system}\n\n{user}"), self.timeout_s)
            text = self._text(result)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}"
            self._down_until = time.monotonic() + self.cooldown_s
            raise
        self.last_error = None
        return text


_PROVIDER: ChatProvider | None = None
_PROVIDER_ERROR: str | None = None


def _build(backend: str) -> ChatProvider:
    if backend in ("foundry", "azure", "agent-framework"):
        endpoint = os.environ.get("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", "").strip()
        if not endpoint:
            raise RuntimeError("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT is not set")
        return AgentFrameworkProvider(
            project_endpoint=endpoint,
            model=os.environ.get("AZURE_AI_FOUNDRY_MODEL", "").strip() or "gpt-4.1-mini",
        )
    return TemplateProvider()


def get_provider(backend: str | None = None) -> ChatProvider:
    """Provider per PM_AGENT_BACKEND: 'template' (default) or 'foundry'.

    The env-selected provider is built once per process. If Foundry is
    selected but cannot be built (missing package, endpoint or identity),
    the service stays up on the template provider and `provider_error()`
    says why - the demo never depends on the model.
    """
    global _PROVIDER, _PROVIDER_ERROR
    if backend is not None:
        return _build(backend.lower())
    if _PROVIDER is None:
        try:
            _PROVIDER = _build(os.environ.get("PM_AGENT_BACKEND", "template").lower())
            _PROVIDER_ERROR = None
        except Exception as exc:
            _PROVIDER, _PROVIDER_ERROR = TemplateProvider(), f"{type(exc).__name__}: {exc}"
    return _PROVIDER


def provider_error() -> str | None:
    """Why the configured backend is not active, if it is not."""
    return _PROVIDER_ERROR


def reset_provider() -> None:
    """Forget the cached provider (tests, or after changing env)."""
    global _PROVIDER, _PROVIDER_ERROR
    _PROVIDER, _PROVIDER_ERROR = None, None


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
