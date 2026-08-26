"""Minimal OpenRouter client with strict JSON, embeddings and cost accounting.

Secrets are read only from OPENROUTER_API_KEY. They are never returned by any
method, persisted, logged, or included in exception messages.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
from dataclasses import dataclass
from typing import Any

import httpx

# 429 retry constants
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 5
_BASE_DELAY = 2.0
_MAX_DELAY = 60.0
_JITTER = 0.5

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "google/gemini-3.7-flash": (0.375, 1.875),
    "google/gemini-3.7-flash:batch": (0.1875, 0.9375),
    "google/gemini-embedding-001": (0.15, 0.0),
    "anthropic/claude-sonnet-5": (2.0, 10.0),
    "anthropic/claude-sonnet-5:batch": (1.0, 5.0),
}


class OpenRouterError(RuntimeError):
    pass


class NoCompatibleEndpoint(OpenRouterError):
    """No provider endpoint can satisfy the requested model/parameters."""


class BudgetExceeded(OpenRouterError):
    pass


@dataclass(repr=False)
class OpenRouterConfig:
    api_key: str
    base_url: str = OPENROUTER_BASE_URL
    primary_model: str = "google/gemini-3.7-flash"
    embedding_model: str = "google/gemini-embedding-001"
    deep_model: str = "anthropic/claude-sonnet-5"
    max_cost_usd: float = 2.0
    max_gigs: int = 25
    gigs_per_batch: int = 1
    max_output_tokens: int = 4000
    request_timeout_seconds: float = 120.0
    allow_parameter_fallback: bool = True
    app_title: str = "Fiverr Market Intelligence"
    app_url: str = "http://localhost:8000"

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("sk-or-"))

    @classmethod
    def from_env(cls) -> "OpenRouterConfig":
        return cls(
            api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
            base_url=os.getenv("OPENROUTER_BASE_URL", OPENROUTER_BASE_URL).rstrip("/"),
            primary_model=os.getenv("OPENROUTER_MODEL", "google/gemini-3.7-flash"),
            embedding_model=os.getenv(
                "OPENROUTER_EMBEDDING_MODEL", "google/gemini-embedding-001"
            ),
            deep_model=os.getenv("OPENROUTER_DEEP_MODEL", "anthropic/claude-sonnet-5"),
            max_cost_usd=max(0.01, float(os.getenv("OPENROUTER_MAX_COST_USD", "2.0"))),
            max_gigs=max(1, min(50, int(os.getenv("OPENROUTER_MAX_GIGS", "25")))),
            gigs_per_batch=max(
                1, min(2, int(os.getenv("OPENROUTER_GIGS_PER_BATCH", "1")))
            ),
            max_output_tokens=max(
                128, min(8000, int(os.getenv("OPENROUTER_MAX_OUTPUT_TOKENS", "4000")))
            ),
            request_timeout_seconds=max(
                15.0, min(300.0, float(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120")))
            ),
            allow_parameter_fallback=os.getenv(
                "OPENROUTER_ALLOW_PARAMETER_FALLBACK", "true"
            ).strip().lower() not in {"0", "false", "no", "off"},
            app_title=os.getenv("OPENROUTER_APP_TITLE", "Fiverr Market Intelligence"),
            app_url=os.getenv("OPENROUTER_APP_URL", "http://localhost:8000"),
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "base_url": self.base_url,
            "primary_model": self.primary_model,
            "embedding_model": self.embedding_model,
            "deep_model": self.deep_model,
            "max_cost_usd": self.max_cost_usd,
            "max_gigs": self.max_gigs,
            "gigs_per_batch": self.gigs_per_batch,
            "max_output_tokens": self.max_output_tokens,
            "allow_parameter_fallback": self.allow_parameter_fallback,
        }


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    cached_tokens: int = 0

    @classmethod
    def from_response(cls, response: dict[str, Any]) -> "Usage":
        usage = response.get("usage") or {}
        prompt_details = usage.get("prompt_tokens_details") or {}
        return cls(
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            cost=float(usage.get("cost") or 0.0),
            cached_tokens=int(prompt_details.get("cached_tokens") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "cached_tokens": self.cached_tokens,
        }


def estimate_tokens(text: str) -> int:
    # Conservative language-agnostic approximation for preflight budgeting.
    return max(1, (len(text) + 2) // 3)


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int = 0
) -> float:
    input_price, output_price = MODEL_PRICES_PER_MILLION.get(model, (2.0, 10.0))
    return (input_tokens / 1_000_000) * input_price + (
        output_tokens / 1_000_000
    ) * output_price


def _content_text(content: Any) -> str:
    """Normalize OpenAI/Anthropic-style content into a plain text payload."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        for key in ("text", "content", "value"):
            value = content.get(key)
            if isinstance(value, str):
                return value
        return json.dumps(content, ensure_ascii=False)
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, dict):
                    text = text.get("value")
                if not isinstance(text, str):
                    text = block.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content)


def _balanced_json_candidates(text: str) -> list[str]:
    """Extract balanced JSON objects/arrays from mixed model prose."""
    candidates: list[str] = []
    for start, character in enumerate(text):
        if character not in "{[":
            continue
        opening, closing = character, "}" if character == "{" else "]"
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            current = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current == opening:
                depth += 1
            elif current == closing:
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : index + 1])
                    break
    return candidates


def parse_structured_content(content: Any) -> dict[str, Any]:
    """Parse structured output across common provider formatting variations."""
    if isinstance(content, dict):
        return content
    text = _content_text(content).strip().lstrip("\ufeff")
    if not text:
        raise ValueError("empty content")

    attempts: list[str] = [text]
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, re.I)
    attempts.extend(value.strip() for value in fenced)
    attempts.extend(_balanced_json_candidates(text))

    seen: set[str] = set()
    for candidate in attempts:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        variants = [
            candidate,
            re.sub(r",\s*([}\]])", r"\1", candidate),
        ]
        for variant in variants:
            try:
                parsed: Any = json.loads(variant)
                # Some gateways return a JSON string containing the real JSON.
                if isinstance(parsed, str):
                    parsed = json.loads(parsed)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                continue
    raise ValueError("unparseable content")


class OpenRouterClient:
    def __init__(
        self,
        config: OpenRouterConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or OpenRouterConfig.from_env()
        self._client = client

    def _headers(self) -> dict[str, str]:
        if not self.config.configured:
            raise OpenRouterError(
                "OPENROUTER_API_KEY is not configured. Set a new rotated key in the environment."
            )
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.config.app_url,
            "X-OpenRouter-Title": self.config.app_title,
            "X-OpenRouter-Cache": "true",
        }

    async def _request(
        self, method: str, path: str, *, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        own_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self.config.request_timeout_seconds, follow_redirects=True
        )
        try:
            last_exc: Exception | None = None
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    response = await client.request(
                        method,
                        f"{self.config.base_url}{path}",
                        headers=self._headers(),
                        json=payload,
                    )
                    if response.status_code < 400:
                        return response.json()

                    # --- Error handling ---
                    message = "OpenRouter request failed"
                    retry_after: float | None = None
                    try:
                        body = response.json()
                        public_error = body.get("error") or {}
                        if isinstance(public_error, dict) and public_error.get("message"):
                            message = str(public_error["message"])
                        # OpenRouter sometimes sends Retry-After in the error body
                        retry_meta = public_error.get("metadata")
                        if isinstance(retry_meta, dict):
                            raw = retry_meta.get("retry_after") or body.get("retry_after")
                            if raw is not None:
                                retry_after = float(raw)
                    except Exception:
                        pass
                    # Also check standard Retry-After header
                    if retry_after is None:
                        raw_header = response.headers.get("Retry-After")
                        if raw_header is not None:
                            try:
                                retry_after = float(raw_header)
                            except (ValueError, TypeError):
                                retry_after = None

                    public_message = f"{message} (HTTP {response.status_code})"

                    # Non-retryable errors — bail immediately
                    if response.status_code in {400, 404} and "no endpoints found" in message.lower():
                        raise NoCompatibleEndpoint(public_message)
                    if response.status_code in {401, 403}:
                        raise OpenRouterError(public_message)
                    if response.status_code == 413:
                        raise OpenRouterError(public_message)

                    # Retryable errors
                    if response.status_code in _RETRYABLE_STATUSES:
                        if attempt < _MAX_RETRIES:
                            delay = _BASE_DELAY * (2 ** (attempt - 1))
                            delay = min(delay, _MAX_DELAY)
                            if retry_after is not None:
                                delay = max(delay, min(retry_after, _MAX_DELAY))
                            # Add jitter
                            delay += _JITTER * (2 * random.random() - 1)
                            await asyncio.sleep(max(0.5, delay))
                            continue
                        raise OpenRouterError(
                            f"{public_message} — retried {_MAX_RETRIES} times, giving up."
                        )

                    raise OpenRouterError(public_message)

                except (NoCompatibleEndpoint, BudgetExceeded):
                    raise
                except OpenRouterError:
                    raise
                except httpx.HTTPError as exc:
                    last_exc = exc
                    if attempt < _MAX_RETRIES:
                        delay = _BASE_DELAY * (2 ** (attempt - 1))
                        delay = min(delay, _MAX_DELAY)
                        delay += _JITTER * (2 * random.random() - 1)
                        await asyncio.sleep(max(0.5, delay))
                        continue
                    raise OpenRouterError(
                        f"OpenRouter network error after {_MAX_RETRIES} retries: "
                        f"{type(exc).__name__}"
                    ) from exc
            # Safety fallback (should not reach here).
            raise OpenRouterError("Unexpected error in OpenRouter request.")
        finally:
            if own_client:
                await client.aclose()

    async def key_status(self) -> dict[str, Any]:
        response = await self._request("GET", "/key")
        data = response.get("data") or response
        # Return only non-secret operational fields.
        return {
            "valid": True,
            "label": data.get("label"),
            "limit": data.get("limit"),
            "limit_remaining": data.get("limit_remaining"),
            "usage": data.get("usage"),
            "is_free_tier": data.get("is_free_tier"),
        }

    async def chat_json(
        self,
        *,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> tuple[dict[str, Any], Usage, str]:
        selected_model = model or self.config.primary_model
        max_tokens = max_tokens or self.config.max_output_tokens
        prompt_text = json.dumps(messages, ensure_ascii=False)
        preflight = estimate_cost(
            selected_model, estimate_tokens(prompt_text), max_tokens
        )
        if preflight > self.config.max_cost_usd:
            raise BudgetExceeded(
                f"Single request estimate ${preflight:.4f} exceeds configured run cap."
            )
        base_payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        strict_payload = {
            **base_payload,
            "provider": {"require_parameters": True},
            "plugins": [{"id": "response-healing"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        payload_attempts = [strict_payload]
        if self.config.allow_parameter_fallback:
            # Some model/provider combinations exist but do not expose strict
            # json_schema on any currently routed endpoint. JSON mode still
            # requests valid JSON while our local parser/validator handles it.
            payload_attempts.extend(
                [
                    {
                        **base_payload,
                        "provider": {"require_parameters": False},
                        "plugins": [{"id": "response-healing"}],
                        "response_format": {"type": "json_object"},
                    },
                    # Last compatibility fallback for a model endpoint that
                    # supports chat but neither structured-output parameter.
                    base_payload,
                ]
            )

        response: dict[str, Any] | None = None
        last_endpoint_error: NoCompatibleEndpoint | None = None
        for candidate_payload in payload_attempts:
            try:
                response = await self._request(
                    "POST", "/chat/completions", payload=candidate_payload
                )
                break
            except NoCompatibleEndpoint as exc:
                last_endpoint_error = exc
                continue
        if response is None:
            raise last_endpoint_error or NoCompatibleEndpoint(
                "No compatible OpenRouter endpoint was found."
            )
        choices = response.get("choices") or []
        if not choices:
            raise OpenRouterError("OpenRouter returned no completion choices.")
        choice = choices[0]
        message = choice.get("message") or {}
        finish_reason = str(choice.get("finish_reason") or "unknown")
        parsed_field = message.get("parsed")
        content = parsed_field if isinstance(parsed_field, dict) else message.get("content")
        refusal = message.get("refusal")
        if refusal:
            raise OpenRouterError("Model refused the structured request.")
        try:
            parsed = parse_structured_content(content)
        except ValueError as exc:
            text_length = len(_content_text(content))
            if finish_reason in {"length", "max_tokens"}:
                raise OpenRouterError(
                    "Model JSON was truncated by the output-token limit. "
                    "The app will use smaller batches after updating; alternatively increase "
                    "OPENROUTER_MAX_OUTPUT_TOKENS to 3500."
                ) from exc
            raise OpenRouterError(
                "Model output could not be parsed as JSON "
                f"(finish_reason={finish_reason}, content_chars={text_length})."
            ) from exc
        return parsed, Usage.from_response(response), str(response.get("id") or "")

    async def embeddings(
        self,
        inputs: list[str],
        *,
        model: str | None = None,
    ) -> tuple[list[list[float]], Usage, str]:
        selected_model = model or self.config.embedding_model
        input_tokens = sum(estimate_tokens(value) for value in inputs)
        preflight = estimate_cost(selected_model, input_tokens, 0)
        if preflight > self.config.max_cost_usd:
            raise BudgetExceeded(
                f"Embedding estimate ${preflight:.4f} exceeds configured run cap."
            )
        response = await self._request(
            "POST",
            "/embeddings",
            payload={"model": selected_model, "input": inputs},
        )
        data = sorted(response.get("data") or [], key=lambda item: item.get("index", 0))
        vectors = [item.get("embedding") or [] for item in data]
        if len(vectors) != len(inputs):
            raise OpenRouterError("Embedding response count did not match input count.")
        return vectors, Usage.from_response(response), str(response.get("id") or "")
