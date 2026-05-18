from __future__ import annotations

import asyncio
import time
import uuid
import re
import html

from backend.bright_data import BrightDataResult, fallback_endpoints, fetch_url, result_text
from backend.config import get_settings
from backend.extractors import extract_ground_truth
from backend.grader import (
    CLAIM_SCHEMA,
    GROUND_TRUTH_SCHEMA,
    build_claim_messages,
    build_ground_truth_messages,
    build_model_answer_messages,
    grade_claim,
    normalize_value,
)
from backend.llm import complete_json, complete_raw_chat
from backend.llm import complete_with_web_search
from backend.models import GroundTruth, ModelRun, Task, TraceStep
from backend.store import latest_ground_truth_by_task, now_iso, save_ground_truth, save_run


EXTRACTOR_MODEL = "openai/gpt-4o-mini"


async def refresh_ground_truth(task: Task) -> GroundTruth:
    result, page_text, value, evidence, confidence, notes = await extract_with_bright_data_tools(task)
    item = GroundTruth(
        task_id=task.id,
        value=value,
        normalized_value=normalize_value(value, task.grading),
        source_url=task.canonical_url,
        fetched_at=result.retrieved_at,
        extraction_confidence=confidence,
        notes=f"{notes} Bright Data endpoint: {result.endpoint}. Evidence: {evidence}".strip(),
        raw_preview=page_text[:800],
    )
    save_ground_truth(item)
    return item


async def extract_with_bright_data_tools(
    task: Task,
) -> tuple[BrightDataResult, str, str, str, str, str]:
    failures: list[str] = []
    for endpoint in fallback_endpoints(task.bd_tool):
        result = await fetch_url(endpoint, task.canonical_url)
        page_text = result_text(result, limit=50000)
        if result.is_error or not page_text:
            failures.append(f"{endpoint}: {result.error or 'no readable Bright Data output'}")
            continue
        try:
            value, evidence, confidence, notes = await extract_supported_value(task, page_text)
            return result, page_text, value, evidence, confidence, notes
        except Exception as exc:
            failures.append(f"{endpoint}: {exc}")
    raise RuntimeError(
        "Bright Data could not produce supported ground truth. "
        + " | ".join(failures)
    )


async def extract_supported_value(task: Task, page_text: str) -> tuple[str, str, str, str]:
    deterministic = extract_ground_truth(task, page_text)
    if deterministic:
        value = deterministic.value.strip()
        evidence = deterministic.evidence.strip()
        confidence = deterministic.confidence
        notes = deterministic.notes
    elif task.bd_tool.startswith("web_data_"):
        raise RuntimeError(f"No deterministic extractor value for {task.bd_tool}")
    else:
        payload = await complete_json(
            build_ground_truth_messages(task, page_text),
            model=EXTRACTOR_MODEL,
            schema_name="ground_truth",
            schema=GROUND_TRUTH_SCHEMA,
        )
        value = str(payload.get("value", "")).strip()
        evidence = str(payload.get("evidence", "")).strip()
        confidence = payload.get("confidence", "medium")
        notes = str(payload.get("notes", "")).strip()
    if not evidence:
        raise RuntimeError(f"Ground truth for {task.id} had no evidence quote")
    if not evidence_supported(page_text, evidence, value):
        raise RuntimeError(
            f"Ground truth for {task.id} was not visibly supported by the fetched page"
        )
    return value, evidence, confidence, notes


def evidence_supported(page_text: str, evidence: str, value: str) -> bool:
    page_norm = normalize_evidence(page_text)
    evidence_norm = normalize_evidence(evidence)
    value_norm = normalize_evidence(value)
    evidence_digits = re.sub(r"[^0-9.]", "", evidence)
    value_digits = re.sub(r"[^0-9.]", "", value)
    evidence_has_value = bool(
        value_norm
        and (
            value_norm in evidence_norm
            or (
                value_digits
                and value_digits in evidence_digits
            )
            or computed_value_supported(evidence, value)
        )
    )
    page_digits = re.sub(r"[^0-9.]", "", page_text)
    if evidence_has_value and (
        evidence_norm in page_norm
        or value_norm in page_norm
        or (value_digits and value_digits in page_digits)
    ):
        return True
    return False


def computed_value_supported(evidence: str, value: str) -> bool:
    value_match = re.search(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", value)
    if not value_match:
        return False
    try:
        target = float(value_match.group(1).replace(",", ""))
    except ValueError:
        return False
    numbers = []
    for match in re.finditer(r"\$([0-9][0-9,]*(?:\.[0-9]{1,2})?)", evidence):
        try:
            numbers.append(float(match.group(1).replace(",", "")))
        except ValueError:
            continue
    for left in numbers:
        for right in numbers:
            if left <= right:
                continue
            if abs((left - right) - target) < 0.01:
                return True
    return False


def normalize_evidence(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[\u2018\u2019]", "'", text)
    text = re.sub(r"[\u201c\u201d]", '"', text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


async def run_model_on_task(
    task: Task,
    ground_truth: GroundTruth,
    model: str,
    *,
    save: bool = True,
) -> ModelRun:
    started = time.perf_counter()
    run_id = str(uuid.uuid4())
    trace: list[TraceStep] = []
    try:
        response = await complete_model_search(task, model)
        answer, citations, search_requests, has_search_request_count = parse_search_response(response)
        for idx, citation in enumerate(citations, start=1):
            trace.append(
                TraceStep(
                    n=idx,
                    action="url_citation",
                    target=citation.get("url", ""),
                    ok=True,
                    latency_ms=None,
                )
            )
        if not trace and search_requests:
            trace.append(
                TraceStep(
                    n=1,
                    action="openrouter:web_search",
                    target=f"{search_requests} search request(s)",
                    ok=True,
                    latency_ms=None,
                )
            )
        tool_calls = search_requests if has_search_request_count else (1 if citations else 0)
        claim_payload = await complete_json(
            build_claim_messages(task, answer),
            model=EXTRACTOR_MODEL,
            schema_name="claim_extraction",
            schema=CLAIM_SCHEMA,
        )
        claim = str(claim_payload.get("claim", "")).strip()
        passed, normalized_claim = grade_claim(task, ground_truth.value, claim)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        run = ModelRun(
            run_id=run_id,
            task_id=task.id,
            model=model,
            answer=answer.strip(),
            extracted_claim=claim,
            normalized_claim=normalized_claim,
            passed=passed,
            verified_retrieval=passed and citations_verify_retrieval(
                citations,
                task.canonical_url,
            ),
            trace=trace,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
            estimated_cost_usd=estimate_cost(model, "", answer, tool_calls),
            created_at=now_iso(),
        )
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        run = ModelRun(
            run_id=run_id,
            task_id=task.id,
            model=model,
            answer="",
            extracted_claim="",
            normalized_claim=None,
            passed=False,
            verified_retrieval=False,
            trace=trace,
            tool_calls=len(trace),
            latency_ms=latency_ms,
            estimated_cost_usd=0.0,
            error=str(exc),
            created_at=now_iso(),
        )
    if save:
        save_run(run)
    return run


async def evaluate_models(
    task: Task,
    models: list[str],
    refresh: bool = True,
    *,
    save_runs: bool = True,
) -> tuple[GroundTruth, list[ModelRun]]:
    settings = get_settings()
    selected = models or list(settings.default_models[:2])
    cached = latest_ground_truth_by_task().get(task.id)
    ground_truth = await refresh_ground_truth(task) if refresh or cached is None else cached
    runs = await asyncio.gather(
        *(run_model_on_task(task, ground_truth, model, save=save_runs) for model in selected)
    )
    return ground_truth, runs


async def complete_model_search(task: Task, model: str) -> dict:
    messages = build_model_answer_messages(task)
    if model.startswith("perplexity/"):
        return await complete_raw_chat(messages, model=model)
    return await complete_with_web_search(messages, model=model)


def parse_search_response(response: dict) -> tuple[str, list[dict], int, bool]:
    choice = response.get("choices", [{}])[0]
    message = choice.get("message") or {}
    answer = _message_text(message.get("content"))
    annotations = message.get("annotations") or []
    citations: list[dict] = []
    for annotation in annotations:
        if annotation.get("type") == "url_citation":
            citation = annotation.get("url_citation") or annotation
            if citation.get("url"):
                citations.append(citation)
    usage = response.get("usage") or {}
    server_tool_use = usage.get("server_tool_use") or {}
    has_search_request_count = "web_search_requests" in server_tool_use
    search_requests = int(server_tool_use.get("web_search_requests") or 0)
    return answer, citations, search_requests, has_search_request_count


def _message_text(content: object) -> str:
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


def citations_verify_retrieval(citations: list[dict], canonical_url: str) -> bool:
    canonical = canonical_url.rstrip("/").lower()
    for citation in citations:
        url = str(citation.get("url", "")).rstrip("/").lower()
        if url == canonical or canonical in url or url in canonical:
            return True
    return False


def estimate_cost(model: str, source: str, answer: str, search_requests: int = 0) -> float:
    # OpenRouter pricing varies by model and changes over time. This MVP stores
    # a transparent rough estimate until provider billing ingestion is added.
    chars = len(source) + len(answer)
    approx_tokens = max(chars / 4, 1)
    if "gpt-4o" in model:
        per_1k = 0.005
    elif "claude" in model:
        per_1k = 0.006
    elif "gemini" in model:
        per_1k = 0.002
    else:
        per_1k = 0.003
    search_cost = search_requests * 0.005
    return round((approx_tokens / 1000) * per_1k + search_cost, 5)
