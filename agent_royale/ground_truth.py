from __future__ import annotations

import os
import re
from typing import Any

import httpx

from agent_royale.schema import Task


async def fetch_ground_truth(task: Task, timeout_seconds: float = 30) -> tuple[str | float, str]:
    spec = task.ground_truth
    if spec.method == "static":
        source = spec.source_url or task.required_source
        return str(spec.value), source
    if spec.method == "http_json":
        assert spec.url and spec.field
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(spec.url, headers=spec.headers)
            response.raise_for_status()
            payload = response.json()
        value = read_field(payload, spec.field)
        return str(value), spec.source_url or spec.url
    if spec.method == "http_regex":
        assert spec.url and spec.regex
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            response = await client.get(spec.url, headers=spec.headers)
            response.raise_for_status()
            text = response.text
        match = re.search(spec.regex, text, re.I | re.S)
        if not match:
            raise RuntimeError(f"Regex did not match ground-truth source for {task.id}")
        value = match.group(1) if match.groups() else match.group(0)
        return value.strip(), spec.source_url or spec.url
    if spec.method == "bright_data":
        value = await fetch_bright_data_ground_truth(task)
        return str(value), spec.source_url or spec.url or task.required_source
    raise RuntimeError(f"Unsupported ground-truth method: {spec.method}")


async def fetch_bright_data_ground_truth(task: Task) -> str:
    spec = task.ground_truth
    if not os.getenv("BRIGHT_DATA_API_KEY"):
        raise RuntimeError(
            "BRIGHT_DATA_API_KEY is required for ground_truth.method=bright_data. "
            "Use public API task packs to run Agent Royale without Bright Data."
        )
    assert spec.tool and spec.url
    from backend.bright_data import fetch_url_with_fallbacks, result_text

    result = await fetch_url_with_fallbacks(spec.tool, spec.url)
    if result.is_error:
        raise RuntimeError(result.error or f"Bright Data tool {spec.tool} failed")
    if spec.field:
        payload = result.structured_content
        if payload is None:
            text = result_text(result, limit=50000)
            payload = parse_structured_text(text)
        value = read_field(payload, spec.field)
        return str(value)
    assert spec.regex
    text = result_text(result, limit=50000)
    match = re.search(spec.regex, text, re.I | re.S)
    if not match:
        raise RuntimeError(f"Regex did not match Bright Data output for {task.id}")
    value = match.group(1) if match.groups() else match.group(0)
    return value.strip()


def parse_structured_text(text: str) -> Any:
    import json

    marker = "STRUCTURED_CONTENT:"
    if marker in text:
        text = text.split(marker, 1)[1].strip()
    return json.loads(text)


def read_field(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(f"Cannot read {part!r} from non-container in {path!r}")
    return current
