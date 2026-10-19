"""Thin wrappers around Azure OpenAI and Azure AI Content Safety (Prompt Shields).

Both are optional. When credentials are missing, every function returns None and
callers fall back to deterministic logic, so the demo always runs.
"""

from __future__ import annotations

import datetime
import json
import logging
import sys
from typing import Any

import httpx

from .config import get_settings

log = logging.getLogger(__name__)


def _trace(kind: str, request: Any, response: Any) -> None:
    """When AUDITOR_DEBUG_LLM is on, print the exact request/response for an
    outbound AI call to stderr (and append to AUDITOR_LLM_LOG if set). This is
    how you see the prompts/payloads going to Azure OpenAI and Content Safety."""
    s = get_settings()
    if not s.debug_llm:
        return
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    req = request if isinstance(request, str) else json.dumps(request, indent=2, default=str)
    res = response if isinstance(response, str) else json.dumps(response, indent=2, default=str)
    block = (f"\n===== [{ts}] {kind} =====\n"
             f"--- REQUEST ---\n{req[:6000]}\n"
             f"--- RESPONSE ---\n{res[:6000]}\n"
             f"{'=' * 52}")
    print(block, file=sys.stderr, flush=True)
    if s.llm_log_file:
        try:
            with open(s.llm_log_file, "a", encoding="utf-8") as fh:
                fh.write(block + "\n")
        except OSError as exc:
            log.warning("Could not write AUDITOR_LLM_LOG: %s", exc)


def _build_client():
    """Return an OpenAI-compatible client for the configured endpoint.

    Two endpoint styles are supported:

    * Classic Azure OpenAI  (``https://<res>.openai.azure.com``) -> ``AzureOpenAI``
      client with an API key + api-version.
    * Microsoft Foundry "v1" (``https://<res>.services.ai.azure.com/openai/v1``)
      -> the plain ``OpenAI`` client pointed at ``base_url``, authenticated with
      either an API key or a Microsoft Entra ID bearer token.

    Both expose ``.chat.completions.create(...)``.
    """
    s = get_settings()

    if s.is_foundry_v1:
        from openai import OpenAI  # imported lazily so mock mode needs no SDK

        base = s.azure_openai_endpoint.rstrip("/")
        if not base.endswith("/openai/v1"):
            base = base + "/openai/v1"

        if s.azure_auth_mode == "entra":
            # Microsoft Entra ID (managed identity / az login / DefaultAzureCredential).
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            token_provider = get_bearer_token_provider(
                DefaultAzureCredential(), "https://ai.azure.com/.default"
            )
            # The token expires; fetch a fresh one per client build.
            return OpenAI(base_url=base, api_key=token_provider())

        # API-key auth against the v1 endpoint.
        return OpenAI(base_url=base, api_key=s.azure_openai_key)

    # Classic Azure OpenAI.
    from openai import AzureOpenAI

    return AzureOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        api_key=s.azure_openai_key,
        api_version=s.azure_openai_api_version,
    )


def chat(messages: list[dict[str, str]], temperature: float = 0.0, max_tokens: int = 600,
         json_mode: bool = False) -> str | None:
    """Call the configured chat model. Returns None if not configured or on error."""
    s = get_settings()
    if not s.llm_available:
        return None
    try:
        client = _build_client()
        kwargs: dict[str, Any] = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        # Next-gen / reasoning models (gpt-5*, o1*, o3*, o4*) rename the token cap to
        # max_completion_tokens and only accept the default temperature. They also
        # spend part of the budget on hidden "reasoning" tokens, so a small cap can
        # leave zero tokens for the visible answer (an empty reply). We therefore (a)
        # give the budget a floor and (b) ask for minimal reasoning on these simple
        # classification/answer tasks, so output isn't eaten by reasoning.
        dep = s.azure_openai_deployment.lower()
        next_gen = dep.startswith(("gpt-5", "o1", "o3", "o4"))
        if next_gen:
            kwargs["max_completion_tokens"] = max(max_tokens, 2048)
            if dep.startswith("gpt-5"):
                kwargs["reasoning_effort"] = "minimal"
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = temperature

        try:
            resp = client.chat.completions.create(
                model=s.azure_openai_deployment,
                messages=messages,
                **kwargs,
            )
        except Exception:
            # Some deployments reject reasoning_effort; retry once without it.
            kwargs.pop("reasoning_effort", None)
            resp = client.chat.completions.create(
                model=s.azure_openai_deployment,
                messages=messages,
                **kwargs,
            )
        content = resp.choices[0].message.content or ""
        _trace("Azure OpenAI · chat.completions",
               {"model": s.azure_openai_deployment, "messages": messages, **kwargs}, content)
        return content
    except Exception as exc:  # content filter blocks, network errors, quota...
        log.warning("Azure OpenAI call failed: %s", exc)
        return None


def chat_json(messages: list[dict[str, str]], **kwargs: Any) -> dict | None:
    raw = chat(messages, json_mode=True, **kwargs)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("LLM returned non-JSON output: %s", raw[:200])
        return None


def prompt_shield(user_prompt: str, documents: list[str] | None = None) -> dict | None:
    """Azure AI Content Safety Prompt Shields. Returns
    {"user_attack": bool, "document_attack": bool} or None when not configured."""
    s = get_settings()
    if not s.content_safety_available:
        return None
    url = s.content_safety_endpoint.rstrip("/") + "/contentsafety/text:shieldPrompt?api-version=2024-09-01"
    try:
        r = httpx.post(
            url,
            headers={"Ocp-Apim-Subscription-Key": s.content_safety_key},
            json={"userPrompt": user_prompt, "documents": documents or []},
            timeout=15,
        )
        r.raise_for_status()
        body = r.json()
        _trace("Azure AI Content Safety · Prompt Shields",
               {"url": url, "payload": {"userPrompt": user_prompt, "documents": documents or []}}, body)
        return {
            "user_attack": bool(body.get("userPromptAnalysis", {}).get("attackDetected")),
            "document_attack": any(d.get("attackDetected") for d in body.get("documentsAnalysis", [])),
        }
    except Exception as exc:
        log.warning("Prompt Shields call failed: %s", exc)
        return None
