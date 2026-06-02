from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Agent Royale Jina Reader Target Example")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    output = await run_jina_reader(req.question, req.task)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    output.setdefault("trace", {})
    output["trace"]["latency_ms"] = latency_ms
    return output


async def run_jina_reader(question: str, task: dict[str, Any]) -> dict[str, Any]:
    timeout_seconds = float(os.getenv("JINA_READER_TIMEOUT_SECONDS", "60"))
    required_source = task.get("required_source", "")
    answer_type = task.get("answer_type", "string")
    source_url = source_to_url(required_source)
    reader_url = "https://r.jina.ai/" + source_url
    headers = {"Accept": "text/plain"}
    token = os.getenv("JINA_API_KEY", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        response = await client.get(reader_url, headers=headers)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:1000]
        raise HTTPException(
            status_code=502,
            detail=f"Jina Reader returned {exc.response.status_code}: {detail}",
        ) from exc

    markdown = response.text
    answer_value = extract_value(markdown, question, answer_type)
    return {
        "answer": answer_value,
        "citations": [{"url": source_url, "quote": ""}],
        "trace": {
            "tools_used": ["jina.reader"],
            "search_queries": [f"required_source={source_url}"],
            "cost_usd": 0,
            "provider_metadata": {
                "provider": "jina",
                "endpoint": "https://r.jina.ai",
                "strategy": "reader_regex",
            },
        },
    }


def source_to_url(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        return source
    return "https://" + source.lstrip("/")


def extract_value(markdown: str, question: str, answer_type: str) -> str:
    lower_question = question.lower()
    lower_doc = markdown.lower()

    if "default branch" in lower_question:
        match = re.search(r"default branch(?:\s*[:\-]|\s+is)?\s*`?([A-Za-z0-9._/\-]+)`?", markdown, re.IGNORECASE)
        if match:
            return clean_token(match.group(1))
        for candidate in ("main", "master", "develop", "dev"):
            if re.search(rf"\b{re.escape(candidate)}\b", lower_doc):
                return candidate

    if "packageManager" in question or "packagemanager" in lower_question:
        match = re.search(r'"packageManager"\s*:\s*"([^"]+)"', markdown)
        if match:
            return match.group(1)
        match = re.search(r"packageManager\s*[:=]\s*`?([A-Za-z0-9@._/\-]+)`?", markdown)
        if match:
            return clean_token(match.group(1))

    if "version" in lower_question:
        match = re.search(r'"version"\s*:\s*"([^"]+)"', markdown)
        if match:
            return match.group(1)
        match = re.search(r"\bversion\b\s*[:=]\s*`?v?([0-9]+(?:\.[0-9A-Za-z\-]+)+)`?", markdown, re.IGNORECASE)
        if match:
            return match.group(1)

    if "latest release tag" in lower_question or "release tag" in lower_question:
        match = re.search(r"\bv[0-9]+(?:\.[0-9]+)+(?:[-A-Za-z0-9.]*)?\b", markdown)
        if match:
            return match.group(0)

    if "spdx" in lower_question or "license" in lower_question:
        for identifier in ("Apache-2.0", "MIT", "BSD-3-Clause", "MPL-2.0", "ISC"):
            if identifier.lower() in lower_doc:
                return identifier

    if answer_type in {"number", "currency", "percentage"}:
        labels = ("stars", "forks", "open issues", "issues", "downloads", "followers")
        for label in labels:
            if label in lower_question:
                pattern = rf"([0-9][0-9,]*(?:\.[0-9]+)?\s*[kKmMbB]?)\s+{re.escape(label)}"
                match = re.search(pattern, markdown, re.IGNORECASE)
                if match:
                    return normalize_numeric_string(match.group(1))
        match = re.search(r"\b[0-9][0-9,]*(?:\.[0-9]+)?\s*[kKmMbB]?\b", markdown)
        if match:
            return normalize_numeric_string(match.group(0))

    return markdown[:1000].strip()


def clean_token(value: str) -> str:
    return value.strip().strip("`'\".,:;)")


def normalize_numeric_string(value: str) -> str:
    compact = value.replace(",", "").strip()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([kKmMbB])", compact)
    if not match:
        return compact
    number = float(match.group(1))
    suffix = match.group(2).lower()
    multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suffix]
    return str(int(number * multiplier))
