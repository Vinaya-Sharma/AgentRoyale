from __future__ import annotations

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
    raise RuntimeError(f"Unsupported ground-truth method: {spec.method}")


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
