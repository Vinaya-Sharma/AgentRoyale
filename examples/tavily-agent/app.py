from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Agent Royale Tavily Target Example")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    output = await run_tavily(req.question, req.task)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    output.setdefault("trace", {})
    output["trace"]["latency_ms"] = latency_ms
    return output


async def run_tavily(question: str, task: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set TAVILY_API_KEY before starting this example.")

    strategy = os.getenv("TAVILY_STRATEGY", "search").strip().lower()
    if strategy == "search":
        return await run_search(api_key, question, task)
    if strategy == "extract":
        return await run_extract(api_key, question, task)
    raise RuntimeError("TAVILY_STRATEGY must be 'search' or 'extract'.")


async def run_search(api_key: str, question: str, task: dict[str, Any]) -> dict[str, Any]:
    required_source = task.get("required_source", "")
    answer_type = task.get("answer_type", "string")
    source_url = source_to_url(required_source)
    timeout_seconds = float(os.getenv("TAVILY_TIMEOUT_SECONDS", "120"))
    payload = {
        "query": (
            "Return the exact single value for this source-specific task. "
            "Do not abbreviate numbers. "
            f"Required source: {required_source}. Task: {question}"
        ),
        "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
        "topic": os.getenv("TAVILY_TOPIC", "general"),
        "include_answer": True,
        "include_raw_content": os.getenv("TAVILY_INCLUDE_RAW_CONTENT", "markdown"),
        "max_results": int(os.getenv("TAVILY_MAX_RESULTS", "5")),
        "include_domains": [domain_from_source(required_source)] if required_source else [],
    }
    data = await post_tavily(api_key, "/search", payload, timeout_seconds)
    answer_value = extract_value(data, question, answer_type)
    citations = extract_citations(data) or [{"url": source_url, "quote": ""}]
    return stack_response(answer_value, citations, "tavily.search", "/search", "search")


async def run_extract(api_key: str, question: str, task: dict[str, Any]) -> dict[str, Any]:
    required_source = task.get("required_source", "")
    answer_type = task.get("answer_type", "string")
    source_url = source_to_url(required_source)
    timeout_seconds = float(os.getenv("TAVILY_TIMEOUT_SECONDS", "120"))
    payload = {
        "urls": [source_url],
        "extract_depth": os.getenv("TAVILY_EXTRACT_DEPTH", "basic"),
        "format": os.getenv("TAVILY_EXTRACT_FORMAT", "markdown"),
        "include_images": False,
    }
    data = await post_tavily(api_key, "/extract", payload, timeout_seconds)
    answer_value = extract_value(data, question, answer_type)
    citations = extract_citations(data) or [{"url": source_url, "quote": ""}]
    return stack_response(answer_value, citations, "tavily.extract", "/extract", "extract")


async def post_tavily(api_key: str, path: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"https://api.tavily.com{path}",
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
        raise HTTPException(status_code=502, detail=f"Tavily {path} returned {exc.response.status_code}: {detail}") from exc
    return response.json()


def stack_response(answer: str, citations: list[dict[str, str]], tool: str, endpoint: str, strategy: str) -> dict[str, Any]:
    return {
        "answer": answer,
        "citations": citations,
        "trace": {
            "tools_used": [tool],
            "search_queries": [endpoint],
            "cost_usd": None,
            "provider_metadata": {
                "provider": "tavily",
                "endpoint": endpoint,
                "strategy": strategy,
            },
        },
    }


def source_to_url(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return "https://" + source.lstrip("/")


def domain_from_source(source: str) -> str:
    url = source_to_url(source)
    without_scheme = re.sub(r"^https?://", "", url)
    return without_scheme.split("/", 1)[0]


def extract_citations(value: Any) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in walk_dicts(value):
        url = str(item.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        citations.append({"url": url, "quote": str(item.get("content", "") or item.get("raw_content", "") or item.get("title", ""))[:500]})
    return citations


def extract_value(value: Any, question: str, answer_type: str) -> str:
    search_space = json.dumps(value, ensure_ascii=False)
    direct = find_direct_answer(value)
    if direct:
        candidate = extract_from_text(direct, question, answer_type)
        if candidate and candidate != direct[:1000].strip():
            return candidate
        return direct
    candidate = extract_from_text(search_space, question, answer_type)
    if candidate:
        return candidate
    return search_space[:1000].strip()


def find_direct_answer(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("answer", "response", "content", "raw_content"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for nested in value.values():
            candidate = find_direct_answer(nested)
            if candidate:
                return candidate
    if isinstance(value, list):
        for item in value:
            candidate = find_direct_answer(item)
            if candidate:
                return candidate
    return ""


def extract_from_text(text: str, question: str, answer_type: str) -> str:
    lower_question = question.lower()
    if "default branch" in lower_question:
        match = re.search(r"default branch(?:\s*[:\-]|\s+is\s+|\s+listed\s+as\s+)`?([A-Za-z0-9._/\-]+)`?", text, re.IGNORECASE)
        if match:
            token = clean_token(match.group(1))
            if token.lower() not in {"does", "is", "listed", "currently"}:
                return token
        for candidate in ("main", "master", "develop", "dev"):
            if re.search(rf"\b{re.escape(candidate)}\b", text, re.IGNORECASE):
                return candidate

    if "packageManager" in question or "packagemanager" in lower_question:
        match = re.search(r'"packageManager"\s*:\s*"([^"]+)"', text)
        if match:
            return match.group(1)
        match = re.search(r"packageManager\s*[:=]\s*`?([A-Za-z0-9@._/\-]+)`?", text)
        if match:
            return clean_token(match.group(1))

    if "version" in lower_question:
        match = re.search(r'"version"\s*:\s*"([^"]+)"', text)
        if match:
            return match.group(1)
        match = re.search(r"\bversion\b\s*[:=]\s*`?v?([0-9]+(?:\.[0-9A-Za-z\-]+)+)`?", text, re.IGNORECASE)
        if match:
            return match.group(1)

    if "latest release tag" in lower_question or "release tag" in lower_question:
        match = re.search(r"\bv[0-9]+(?:\.[0-9]+)+(?:[-A-Za-z0-9.]*)?\b", text)
        if match:
            return match.group(0)

    if "spdx" in lower_question or "license" in lower_question:
        for identifier in ("Apache-2.0", "MIT", "BSD-3-Clause", "MPL-2.0", "ISC"):
            if identifier.lower() in text.lower():
                return identifier

    if answer_type in {"number", "currency", "percentage"}:
        match = re.search(r"\b[0-9][0-9,]*(?:\.[0-9]+)?\s*[kKmMbB]?\b", text)
        if match:
            return normalize_numeric_string(match.group(0))
    return ""


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from walk_dicts(nested)
    elif isinstance(value, list):
        for item in value:
            yield from walk_dicts(item)


def clean_token(value: str) -> str:
    return value.strip().strip("`'\".,:;)")


def normalize_numeric_string(value: str) -> str:
    compact = value.replace(",", "").strip()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([kKmMbB])", compact)
    if not match:
        return compact
    number = float(match.group(1))
    multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[match.group(2).lower()]
    return str(int(number * multiplier))
