from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent_royale.grading import grade
from agent_royale.ground_truth import fetch_ground_truth_snapshot
from agent_royale.schema import RunRecord, Task
from agent_royale.targets import call_target


async def run_tasks(
    tasks: list[Task],
    *,
    target: str,
    output: Path,
    runs_per_task: int = 1,
    concurrency: int = 4,
    timeout_seconds: float = 120,
) -> list[RunRecord]:
    output.parent.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(concurrency)
    records: list[RunRecord] = []

    async def run_one(task: Task, repetition: int) -> RunRecord:
        async with semaphore:
            return await evaluate_one(task, target, timeout_seconds)

    jobs = [run_one(task, rep) for task in tasks for rep in range(runs_per_task)]
    for coro in asyncio.as_completed(jobs):
        record = await coro
        records.append(record)
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(), ensure_ascii=True) + "\n")
        status = "PASS" if record.passed and not record.failure_mode else ("ISSUE" if record.passed else "FAIL")
        detail = record.failure_mode or "correct"
        if record.error:
            detail = f"{detail}: {record.error}"
        print(f"{status} {record.task_id} {detail}")
    return records


async def evaluate_one(task: Task, target: str, timeout_seconds: float) -> RunRecord:
    created_at = datetime.now(timezone.utc).isoformat()
    run_id = str(uuid.uuid4())
    try:
        truth_snapshot = await fetch_ground_truth_snapshot(task, timeout_seconds=timeout_seconds)
        if truth_snapshot.status != "verified" or truth_snapshot.value is None:
            return RunRecord(
                run_id=run_id,
                task_id=task.id,
                task_question=task.question,
                target=target,
                answer="",
                extracted_claim="",
                ground_truth="",
                ground_truth_snapshot=truth_snapshot,
                oracle_status=truth_snapshot.status,
                scoreable=False,
                normalized_claim=None,
                normalized_truth=None,
                passed=False,
                outcome="ground_truth_ambiguous" if "ambiguous" in truth_snapshot.status else "oracle_failed",
                failure_mode="ground_truth_ambiguous" if "ambiguous" in truth_snapshot.status else "oracle_failed",
                citations=[],
                citation_supported=False,
                required_source=truth_snapshot.source_url or task.required_source,
                latency_ms=0,
                cost_usd=None,
                created_at=created_at,
                error=truth_snapshot.error,
            )
        truth = truth_snapshot.value
        stack_response, latency_ms = await asyncio.wait_for(
            call_target(target, task, timeout_seconds=timeout_seconds),
            timeout=timeout_seconds,
        )
        passed, claim, normalized_claim, normalized_truth = grade(task, truth, stack_response.answer)
        citation_supported = citations_support(
            stack_response.citations,
            required_source=task.required_source,
            claim=str(claim),
        )
        failure_mode = classify_failure(
            passed=passed,
            answer=stack_response.answer,
            citation_supported=citation_supported,
            required_source=task.required_source,
            citations=[item.url for item in stack_response.citations],
        )
        return RunRecord(
            run_id=run_id,
            task_id=task.id,
            task_question=task.question,
            target=target,
            answer=stack_response.answer,
            extracted_claim=claim,
            ground_truth=truth,
            ground_truth_snapshot=truth_snapshot,
            oracle_status=truth_snapshot.status,
            scoreable=True,
            normalized_claim=normalized_claim,
            normalized_truth=normalized_truth,
            passed=passed,
            outcome="correct" if passed else "failed",
            failure_mode=failure_mode,
            citations=stack_response.citations,
            citation_supported=citation_supported,
            required_source=truth_snapshot.source_url or task.required_source,
            latency_ms=latency_ms,
            cost_usd=stack_response.trace.cost_usd,
            created_at=created_at,
        )
    except Exception as exc:
        return RunRecord(
            run_id=run_id,
            task_id=task.id,
            task_question=task.question,
            target=target,
            answer="",
            extracted_claim="",
            ground_truth="",
            ground_truth_snapshot=None,
            oracle_status="oracle_failed",
            scoreable=False,
            normalized_claim=None,
            normalized_truth=None,
            passed=False,
            outcome="error",
            failure_mode="tool_failure",
            citations=[],
            citation_supported=False,
            required_source=task.required_source,
            latency_ms=0,
            cost_usd=None,
            created_at=created_at,
            error=str(exc),
        )


def citations_support(citations: list, *, required_source: str, claim: str) -> bool:
    required = normalize_url(required_source)
    claim_norm = claim.strip().lower()
    for citation in citations:
        url = normalize_url(citation.url)
        if required and required not in url and url not in required:
            continue
        quote = citation.quote.lower()
        if not quote or claim_norm in quote or digits(claim_norm) in digits(quote):
            return True
    return False


def classify_failure(
    *,
    passed: bool,
    answer: str,
    citation_supported: bool,
    required_source: str,
    citations: list[str],
) -> str | None:
    if passed:
        if citation_supported or not citations:
            return None
        return "unsupported_citation"
    if not answer.strip():
        return "no_answer"
    if citations and not any(normalize_url(required_source) in normalize_url(url) for url in citations):
        return "wrong_source"
    return "wrong_value"


def normalize_url(value: str) -> str:
    return str(value or "").lower().replace("https://", "").replace("http://", "").rstrip("/")


def digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit() or ch == ".")
