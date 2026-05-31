from __future__ import annotations

import json
import os
import time
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


app = FastAPI(title="Agent Royale OpenAI Agents SDK Example")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    output = await run_openai_agent(req.question, req.task)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    output.setdefault("trace", {})
    output["trace"].setdefault("tools_used", ["openai_agents_sdk"])
    output["trace"]["latency_ms"] = latency_ms
    return output


async def run_openai_agent(question: str, task: dict[str, Any]) -> dict[str, Any]:
    try:
        from agents import Agent, Runner, WebSearchTool
    except ImportError as exc:
        raise RuntimeError(
            "Install this example's dependencies with: "
            "pip install -r examples/openai-agent/requirements.txt"
        ) from exc

    required_source = task.get("required_source", "")
    answer_type = task.get("answer_type", "string")
    model = os.getenv("OPENAI_AGENT_MODEL", "gpt-4.1-mini")
    agent = Agent(
        name="Agent Royale OpenAI web agent",
        model=model,
        instructions=(
            "You answer exact, source-specific live-web retrieval questions. "
            "Use web search. Do not answer from memory. "
            "Return compact JSON only with keys: answer, citations. "
            "citations must be a list of objects with url and quote keys. "
            f"The required source is: {required_source}. "
            f"The answer type is: {answer_type}."
        ),
        tools=[WebSearchTool(search_context_size="medium")],
    )
    prompt = (
        f"Question: {question}\n"
        f"Required source: {required_source}\n"
        "Return JSON only. The answer field should contain the single value Agent Royale should grade."
    )
    result = await Runner.run(agent, prompt, max_turns=4)
    text = str(result.final_output or "").strip()
    parsed = parse_agent_json(text)
    parsed.setdefault("answer", text)
    parsed.setdefault("citations", [])
    parsed["trace"] = {
        "tools_used": ["openai_agents_sdk", "openai_web_search"],
        "search_queries": [f"required_source={required_source}"],
        "cost_usd": None,
    }
    return parsed


def parse_agent_json(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return {"answer": text, "citations": []}
        try:
            payload = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return {"answer": text, "citations": []}
    if not isinstance(payload, dict):
        return {"answer": text, "citations": []}
    citations = payload.get("citations")
    if not isinstance(citations, list):
        payload["citations"] = []
    return payload
