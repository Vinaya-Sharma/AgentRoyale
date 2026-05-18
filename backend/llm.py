from __future__ import annotations

import json
from typing import Any

import httpx
from openai import AsyncOpenAI

from backend.config import Settings, get_settings


def get_openrouter_client(settings: Settings | None = None) -> AsyncOpenAI:
    settings = settings or get_settings()
    return AsyncOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout=settings.openrouter_timeout_seconds,
        max_retries=0,
        default_headers={
            "HTTP-Referer": settings.app_url,
            "X-Title": settings.app_name,
        },
    )


def parse_json_object(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])


async def complete_json(
    messages: list[dict[str, str]],
    *,
    model: str,
    schema_name: str,
    schema: dict[str, Any],
) -> dict[str, Any]:
    client = get_openrouter_client()
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
        extra_body={"plugins": [{"id": "response-healing"}]},
    )
    content = _chat_completion_content(response)
    if not content:
        raise RuntimeError("OpenRouter returned no text content for JSON extraction")
    try:
        return parse_json_object(content)
    except Exception:
        repair_messages = [
            {
                "role": "system",
                "content": (
                    "Return only one compact valid JSON object. No markdown. "
                    "Escape all quotes and newlines inside string values."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Convert this malformed/verbose response into valid JSON matching "
                    f"this schema name {schema_name}. Keep the same keys and values.\n\n"
                    f"Schema: {json.dumps(schema)}\n\nResponse:\n{content[:6000]}"
                ),
            },
        ]
        repaired = await client.chat.completions.create(
            model=model,
            messages=repair_messages,
            response_format={"type": "json_object"},
        )
        repaired_content = _chat_completion_content(repaired)
        if not repaired_content:
            raise RuntimeError(
                f"OpenRouter returned malformed JSON and repair produced no content. Original preview: {content[:500]}"
            )
        try:
            return parse_json_object(repaired_content)
        except Exception as exc:
            raise RuntimeError(
                f"Could not parse JSON extraction response. Original preview: {content[:500]} Repaired preview: {repaired_content[:500]}"
            ) from exc


async def complete_text(messages: list[dict[str, str]], *, model: str) -> str:
    client = get_openrouter_client()
    response = await client.chat.completions.create(model=model, messages=messages)
    return _chat_completion_content(response)


async def complete_raw_chat(
    messages: list[dict[str, str]],
    *,
    model: str,
) -> dict[str, Any]:
    settings = get_settings()
    payload = {"model": model, "messages": messages}
    async with httpx.AsyncClient(timeout=settings.openrouter_timeout_seconds) as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.app_url,
                "X-Title": settings.app_name,
            },
            json=payload,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:1200]
            raise RuntimeError(
                f"OpenRouter {response.status_code} for model {model}: {detail}"
            ) from exc
        return response.json()


async def complete_with_web_search(
    messages: list[dict[str, str]],
    *,
    model: str,
    allowed_domains: list[str] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    parameters: dict[str, Any] = {
        "engine": settings.search_engine,
        "max_results": settings.search_max_results,
        "max_total_results": settings.search_max_total_results,
        "user_location": {
            "type": "approximate",
            "country": "US",
            "timezone": "America/Los_Angeles",
        },
    }
    if allowed_domains:
        parameters["allowed_domains"] = allowed_domains
    payload = {
        "model": model,
        "messages": messages,
        "tools": [{"type": "openrouter:web_search", "parameters": parameters}],
    }
    async with httpx.AsyncClient(timeout=settings.openrouter_timeout_seconds) as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.app_url,
                "X-Title": settings.app_name,
            },
            json=payload,
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:1200]
            raise RuntimeError(
                f"OpenRouter {response.status_code} for model {model}: {detail}"
            ) from exc
        return response.json()


def _chat_completion_content(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            elif item is not None:
                parts.append(str(item))
        return "\n".join(parts)
    return ""
