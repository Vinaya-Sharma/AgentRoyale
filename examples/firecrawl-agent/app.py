from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Agent Royale Firecrawl Target Example")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    output = await run_firecrawl(req.question, req.task)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    output.setdefault("trace", {})
    output["trace"]["latency_ms"] = latency_ms
    return output


async def run_firecrawl(question: str, task: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set FIRECRAWL_API_KEY before starting this example.")

    strategy = os.getenv("FIRECRAWL_STRATEGY", "scrape_json").strip().lower()
    if strategy == "scrape_json":
        return await run_scrape_json(api_key, question, task)
    raise RuntimeError("FIRECRAWL_STRATEGY must be 'scrape_json'.")


async def run_scrape_json(api_key: str, question: str, task: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = float(os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "120"))
    required_source = task.get("required_source", "")
    answer_type = task.get("answer_type", "string")
    url = source_to_url(required_source)
    payload = {
        "url": url,
        "formats": [
            {
                "type": "json",
                "schema": answer_schema(answer_type),
                "prompt": extraction_prompt(question),
            }
        ],
        "onlyMainContent": False,
        "maxAge": int(float(os.getenv("FIRECRAWL_MAX_AGE_MS", "0"))),
        "timeout": int(float(os.getenv("FIRECRAWL_FETCH_TIMEOUT_MS", "60000"))),
    }
    data = await post_firecrawl(api_key, "/v2/scrape", payload, timeout_seconds)
    answer = extract_answer(data)
    return stack_response(
        answer=answer,
        url=url,
        tool="firecrawl.scrape_json",
        endpoint="/v2/scrape",
        strategy="scrape_json",
    )


async def post_firecrawl(api_key: str, path: str, payload: dict[str, Any], timeout_seconds: float) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"https://api.firecrawl.dev{path}",
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
        raise HTTPException(status_code=502, detail=f"Firecrawl {path} returned {exc.response.status_code}: {detail}") from exc
    return response.json()


def answer_schema(answer_type: str) -> dict[str, Any]:
    schema_type = "number" if answer_type in {"number", "currency", "percentage"} else "string"
    return {
        "type": "object",
        "properties": {
            "answer": {
                "type": schema_type,
                "description": "The single exact value requested by the task. Do not abbreviate numbers.",
            }
        },
        "required": ["answer"],
        "additionalProperties": False,
    }


def extraction_prompt(question: str) -> str:
    return (
        "Extract the single exact value requested by this Agent Royale task. "
        "Use only the supplied page or required source. Do not abbreviate numbers. "
        "Do not include explanation. "
        f"Task: {question}"
    )


def stack_response(answer: str, url: str, tool: str, endpoint: str, strategy: str) -> dict[str, Any]:
    return {
        "answer": answer,
        "citations": [{"url": url, "quote": ""}],
        "trace": {
            "tools_used": [tool],
            "search_queries": [f"required_source={url}"],
            "cost_usd": None,
            "provider_metadata": {
                "provider": "firecrawl",
                "endpoint": endpoint,
                "strategy": strategy,
            },
        },
    }


def source_to_url(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return "https://" + source.lstrip("/")


def extract_answer(value: Any) -> str:
    text = extract_text(value, answer_only=True)
    if text:
        return text
    text = extract_text(value, answer_only=False)
    if text:
        return text
    return json.dumps(value, ensure_ascii=False)


def extract_text(value: Any, answer_only: bool) -> str:
    if isinstance(value, str):
        return "" if answer_only else value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        for item in value:
            text = extract_text(item, answer_only=answer_only)
            if text:
                return text
    if isinstance(value, dict):
        keys = ("answer",) if answer_only else (
            "answer",
            "json",
            "data",
            "extract",
            "result",
            "content",
            "text",
            "markdown",
        )
        for key in keys:
            if key not in value:
                continue
            candidate = value[key]
            if key == "json" and isinstance(candidate, dict) and "answer" in candidate:
                return extract_text(candidate["answer"], answer_only=False)
            text = extract_text(candidate, answer_only=answer_only)
            if text:
                return text
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                text = extract_text(nested, answer_only=answer_only)
                if text:
                    return text
    return ""
