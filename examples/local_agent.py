from __future__ import annotations

import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(title="Agent Royale Example Local Agent")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    task_id = str(req.task.get("id", ""))
    payload = answer_task(task_id)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    payload.setdefault("trace", {})
    payload["trace"].setdefault("tools_used", ["example.local_lookup"])
    payload["trace"]["latency_ms"] = latency_ms
    payload["trace"].setdefault("cost_usd", 0)
    return payload


def answer_task(task_id: str) -> dict[str, Any]:
    if task_id == "smoke_price":
        return {
            "answer": "$19.00",
            "citations": [
                {
                    "url": "https://example.com/pricing",
                    "quote": "Pro plan $19.00 per month",
                }
            ],
        }
    if task_id == "smoke_followers":
        return {
            "answer": "12,500",
            "citations": [
                {
                    "url": "https://example.com/social",
                    "quote": "Followers 12,500",
                }
            ],
        }
    return {
        "answer": "",
        "citations": [],
        "trace": {"tools_used": ["example.no_match"]},
    }
