from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(title="Agent Royale Browser Use Target Example")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    output = await run_browser_use(req.question, req.task)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    output.setdefault("trace", {})
    output["trace"]["latency_ms"] = latency_ms
    return output


async def run_browser_use(question: str, task: dict[str, Any]) -> dict[str, Any]:
    try:
        from browser_use_sdk.v3 import AsyncBrowserUse
    except ImportError as exc:
        raise RuntimeError("Install this example's dependencies with: pip install -r examples/browser-use-agent/requirements.txt") from exc

    source_url = source_to_url(task.get("required_source", ""))
    client = AsyncBrowserUse()
    result = await client.run(
        (
            "Open the required source and return only the single exact value requested by this task. "
            "Do not abbreviate numbers. Do not include explanation. "
            f"Required source: {source_url}. Task: {question}"
        ),
        start_url=source_url,
        allowed_domains=[domain_from_url(source_url)],
    )
    answer_value = str(getattr(result, "output", "") or result).strip()
    return {
        "answer": answer_value,
        "citations": [{"url": source_url, "quote": ""}],
        "trace": {
            "tools_used": ["browser_use.agent"],
            "search_queries": [f"required_source={source_url}"],
            "cost_usd": None,
            "provider_metadata": {
                "provider": "browser-use",
            },
        },
    }


def source_to_url(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return "https://" + source.lstrip("/")


def domain_from_url(url: str) -> str:
    return url.split("://", 1)[-1].split("/", 1)[0]
