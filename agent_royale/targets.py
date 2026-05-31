from __future__ import annotations

import importlib
import json
import time
from pathlib import Path
from typing import Any

import httpx

from agent_royale.schema import Citation, StackResponse, Task


async def call_target(target: str, task: Task, timeout_seconds: float = 120) -> tuple[StackResponse, float]:
    started = time.perf_counter()
    if target.startswith("http://") or target.startswith("https://"):
        response = await call_endpoint(target, task, timeout_seconds)
    elif target.startswith("openrouter:"):
        response = await call_openrouter(target.removeprefix("openrouter:"), task)
    elif ":" in target and (target.endswith(":answer") or ".py:" in target):
        response = await call_python_function(target, task)
    else:
        raise ValueError(
            "Unsupported target. Use an http(s) endpoint, openrouter:<model>, or path.py:function."
        )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    if response.trace.latency_ms is None:
        response.trace.latency_ms = latency_ms
    return response, latency_ms


async def call_endpoint(url: str, task: Task, timeout_seconds: float) -> StackResponse:
    payload = {
        "question": task.question,
        "task": task.model_dump(),
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
    return coerce_stack_response(response.json())


async def call_openrouter(model: str, task: Task) -> StackResponse:
    from backend.llm import complete_with_web_search

    messages = [
        {
            "role": "system",
            "content": (
                "You are being evaluated on exact live-web retrieval. Use web search, "
                "answer with the requested value, and cite the source. Do not answer from memory."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{task.question}\nRequired source: {task.required_source}\n"
                "Return the exact current value and cite your source."
            ),
        },
    ]
    response = await complete_with_web_search(messages, model=model)
    answer, citations, search_requests, has_search_request_count = parse_search_response(response)
    tools_used = ["openrouter:web_search"] if search_requests > 0 else []
    if not tools_used and not has_search_request_count:
        tools_used = ["openrouter:model"]
    return StackResponse(
        answer=answer,
        citations=[Citation(url=item.get("url", ""), quote=item.get("content", "") or item.get("title", "")) for item in citations],
        trace={
            "tools_used": tools_used,
            "search_queries": [f"{search_requests} search request(s)"] if has_search_request_count else [],
        },
    )


def parse_search_response(response: dict) -> tuple[str, list[dict], int, bool]:
    choice = response.get("choices", [{}])[0]
    message = choice.get("message") or {}
    answer = message_text(message.get("content"))
    citations: list[dict] = []
    for annotation in message.get("annotations") or []:
        if annotation.get("type") == "url_citation":
            citation = annotation.get("url_citation") or annotation
            if citation.get("url"):
                citations.append(citation)
    usage = response.get("usage") or {}
    server_tool_use = usage.get("server_tool_use") or {}
    has_search_request_count = "web_search_requests" in server_tool_use
    search_requests = int(server_tool_use.get("web_search_requests") or 0)
    return answer, citations, search_requests, has_search_request_count


def message_text(content: object) -> str:
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


async def call_python_function(target: str, task: Task) -> StackResponse:
    module_ref, func_name = target.split(":", 1)
    if module_ref.endswith(".py"):
        module_path = Path(module_ref).resolve()
        spec_name = module_path.stem
        import sys

        sys.path.insert(0, str(module_path.parent))
        try:
            module = importlib.import_module(spec_name)
        finally:
            try:
                sys.path.remove(str(module_path.parent))
            except ValueError:
                pass
    else:
        module = importlib.import_module(module_ref)
    func = getattr(module, func_name)
    result = func(task.question, task.model_dump())
    if hasattr(result, "__await__"):
        result = await result
    return coerce_stack_response(result)


def coerce_stack_response(payload: Any) -> StackResponse:
    if isinstance(payload, StackResponse):
        return payload
    if isinstance(payload, str):
        return StackResponse(answer=payload)
    if isinstance(payload, bytes):
        return StackResponse(answer=payload.decode("utf-8"))
    if isinstance(payload, dict):
        if "answer" not in payload and "output" in payload:
            payload = {**payload, "answer": payload["output"]}
        return StackResponse.model_validate(payload)
    return StackResponse(answer=json.dumps(payload, ensure_ascii=False))
