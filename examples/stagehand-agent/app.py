from __future__ import annotations

import json
import os
import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(title="Agent Royale Stagehand Target Example")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    output = run_stagehand(req.question, req.task)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    output.setdefault("trace", {})
    output["trace"]["latency_ms"] = latency_ms
    return output


def run_stagehand(question: str, task: dict[str, Any]) -> dict[str, Any]:
    try:
        from stagehand import Stagehand
    except ImportError as exc:
        raise RuntimeError("Install this example's dependencies with: pip install -r examples/stagehand-agent/requirements.txt") from exc

    source_url = source_to_url(task.get("required_source", ""))
    model_name = os.getenv("STAGEHAND_MODEL", "google/gemini-3-flash-preview")
    client = Stagehand(
        browserbase_api_key=os.getenv("BROWSERBASE_API_KEY") or None,
        browserbase_project_id=os.getenv("BROWSERBASE_PROJECT_ID") or None,
        model_api_key=os.getenv("STAGEHAND_MODEL_API_KEY") or None,
    )
    session_id = ""
    try:
        response = client.sessions.start(model_name=model_name)
        session_id = nested_get(response, "data.session_id") or nested_get(response, "session_id")
        client.sessions.navigate(id=session_id, url=source_url)
        result = client.sessions.extract(
            id=session_id,
            instruction=(
                "Extract the single exact value requested by this Agent Royale task. "
                "Use only the current page. Do not abbreviate numbers. "
                f"Task: {question}"
            ),
            schema={
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "The single exact value requested by the task.",
                    }
                },
                "required": ["answer"],
                "additionalProperties": False,
            },
        )
        answer_value = extract_answer(result)
        return {
            "answer": answer_value,
            "citations": [{"url": source_url, "quote": ""}],
            "trace": {
                "tools_used": ["stagehand.extract"],
                "search_queries": [f"required_source={source_url}"],
                "cost_usd": None,
                "provider_metadata": {
                    "provider": "stagehand",
                    "model": model_name,
                    "session_id": session_id,
                },
            },
        }
    finally:
        if session_id:
            try:
                client.sessions.end(id=session_id)
            except Exception:
                pass


def source_to_url(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return "https://" + source.lstrip("/")


def nested_get(value: Any, path: str) -> str:
    current = value
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return ""
    return str(current)


def extract_answer(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("answer", "value", "result", "data", "extraction", "content", "text"):
            if key in value:
                text = extract_answer(value[key])
                if text:
                    return text
    if isinstance(value, list):
        for item in value:
            text = extract_answer(item)
            if text:
                return text
    try:
        dumped = value.model_dump()
    except Exception:
        try:
            dumped = vars(value)
        except Exception:
            return json.dumps(str(value), ensure_ascii=False)
    return extract_answer(dumped) or json.dumps(dumped, ensure_ascii=False)
