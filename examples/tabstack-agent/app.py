from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Agent Royale Tabstack Target Example")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    output = await run_tabstack_research(req.question, req.task)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    output.setdefault("trace", {})
    output["trace"].setdefault("tools_used", ["tabstack.research"])
    output["trace"]["latency_ms"] = latency_ms
    return output


async def run_tabstack_research(question: str, task: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("TABSTACK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set TABSTACK_API_KEY before starting this example.")

    strategy = os.getenv("TABSTACK_STRATEGY", "research").strip().lower()
    if strategy == "extract_json":
        return await run_tabstack_extract_json(api_key, question, task)
    if strategy != "research":
        raise RuntimeError("TABSTACK_STRATEGY must be 'research' or 'extract_json'.")

    mode = os.getenv("TABSTACK_RESEARCH_MODE", "fast")
    timeout_seconds = float(os.getenv("TABSTACK_TIMEOUT_SECONDS", "120"))
    fetch_timeout = int(float(os.getenv("TABSTACK_FETCH_TIMEOUT", "30")))
    required_source = task.get("required_source", "")
    answer_type = task.get("answer_type", "string")
    prompt = (
        "Answer this exact live-web retrieval task. Do not answer from memory.\n"
        f"Question: {question}\n"
        f"Required source: {required_source}\n"
        f"Answer type: {answer_type}\n"
        "Return only the single exact value that should be graded. "
        "Do not abbreviate numbers. Do not include explanation. Include source URLs when available."
    )
    payload = {
        "query": prompt,
        "mode": mode,
        "fetch_timeout": fetch_timeout,
    }
    if os.getenv("TABSTACK_NOCACHE", "").lower() in {"1", "true", "yes"}:
        payload["nocache"] = True

    events: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        async with client.stream(
            "POST",
            "https://api.tabstack.ai/v1/research",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json=payload,
        ) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text[:1000]
                raise HTTPException(
                    status_code=502,
                    detail=f"Tabstack /v1/research returned {exc.response.status_code}: {detail}",
                ) from exc
            async for event in iter_sse(response):
                events.append(event)

    answer_text = find_answer_text(events)
    citations = find_citations(events)
    return {
        "answer": answer_text,
        "citations": citations,
        "trace": {
            "tools_used": ["tabstack.research"],
            "search_queries": [f"required_source={required_source}"],
            "cost_usd": None,
            "provider_metadata": {
                "provider": "tabstack",
                "endpoint": "/v1/research",
                "mode": mode,
                "event_count": len(events),
            },
        },
    }


async def run_tabstack_extract_json(api_key: str, question: str, task: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = float(os.getenv("TABSTACK_TIMEOUT_SECONDS", "120"))
    effort = os.getenv("TABSTACK_EXTRACT_EFFORT", "standard")
    required_source = task.get("required_source", "")
    answer_type = task.get("answer_type", "string")
    url = source_to_url(required_source)
    schema_type = "number" if answer_type in {"number", "currency", "percentage"} else "string"
    payload = {
        "url": url,
        "effort": effort,
        "json_schema": {
            "type": "object",
            "properties": {
                "answer": {
                    "type": schema_type,
                    "description": (
                        "The single exact value requested by this Agent Royale task. "
                        f"Question: {question}. Do not abbreviate numbers."
                    ),
                }
            },
            "required": ["answer"],
            "additionalProperties": False,
        },
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            "https://api.tabstack.ai/v1/extract/json",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:1000]
        raise HTTPException(
            status_code=502,
            detail=f"Tabstack /v1/extract/json returned {exc.response.status_code}: {detail}",
        ) from exc
    data = response.json()
    answer = extract_text(data)
    if not answer:
        answer = json.dumps(data, ensure_ascii=False)
    return {
        "answer": str(answer),
        "citations": [{"url": url, "quote": ""}],
        "trace": {
            "tools_used": ["tabstack.extract_json"],
            "search_queries": [f"required_source={required_source}"],
            "cost_usd": None,
            "provider_metadata": {
                "provider": "tabstack",
                "endpoint": "/v1/extract/json",
                "effort": effort,
            },
        },
    }


def source_to_url(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return "https://" + source.lstrip("/")


async def iter_sse(response: httpx.Response):
    event_name = ""
    data_lines: list[str] = []
    async for raw_line in response.aiter_lines():
        line = raw_line.strip()
        if not line:
            if data_lines:
                yield parse_sse_event(event_name, data_lines)
            event_name = ""
            data_lines = []
            continue
        if line.startswith("event:"):
            event_name = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
    if data_lines:
        yield parse_sse_event(event_name, data_lines)


def parse_sse_event(event_name: str, data_lines: list[str]) -> dict[str, Any]:
    raw_data = "\n".join(data_lines)
    try:
        data: Any = json.loads(raw_data)
    except json.JSONDecodeError:
        data = raw_data
    return {"event": event_name, "data": data}


def find_answer_text(events: list[dict[str, Any]]) -> str:
    preferred_events = (
        "writing:end",
        "task:completed",
        "research:completed",
        "complete",
        "completed",
        "result",
    )
    for event in reversed(events):
        name = str(event.get("event", ""))
        if name in preferred_events or "complete" in name or "end" in name:
            text = extract_text(event.get("data"))
            if text:
                return text
    for event in reversed(events):
        text = extract_text(event.get("data"))
        if text:
            return text
    return ""


def extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            nested = extract_text(item)
            if nested:
                return nested
    if isinstance(value, dict):
        text_keys = ("answer", "finalAnswer", "final_answer", "report", "result", "output", "content", "text", "markdown")
        for key in text_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if isinstance(candidate, (dict, list)):
                nested = extract_text(candidate)
                if nested:
                    return nested
        for key in ("data", "message"):
            nested = extract_text(value.get(key))
            if nested:
                return nested
        for nested_value in value.values():
            if isinstance(nested_value, (dict, list)):
                nested = extract_text(nested_value)
                if nested:
                    return nested
    return ""


def find_citations(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for event in events:
        for item in walk_citation_candidates(event.get("data")):
            url = str(item.get("url", "")).strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            citations.append({"url": url, "quote": str(item.get("quote", "") or item.get("title", ""))})
    return citations


def walk_citation_candidates(value: Any):
    if isinstance(value, dict):
        if "url" in value:
            yield value
        for key in ("citations", "sources", "references", "urls", "samples"):
            nested = value.get(key)
            if isinstance(nested, list):
                for item in nested:
                    yield from walk_citation_candidates(item)
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                yield from walk_citation_candidates(nested)
    elif isinstance(value, list):
        for item in value:
            yield from walk_citation_candidates(item)
