from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent_royale.grading import grade_with_trace
from agent_royale.ground_truth import fetch_ground_truth_snapshot
from agent_royale.schema import RunRecord, Task
from agent_royale.targets import call_target


GRADER_VERSION = "2"
ORACLE_VERSION = "2"


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
                task_pack_name=task.task_pack_name,
                task_pack_version=task.task_pack_version,
                task_hash=task.stable_hash(),
                grader_version=GRADER_VERSION,
                oracle_version=ORACLE_VERSION,
                value_correct=False,
                source_correct=False,
                citation_supports_claim=False,
                final_verdict=(
                    "ground_truth_ambiguous"
                    if "ambiguous" in truth_snapshot.status
                    else "oracle_failed"
                ),
                normalized_claim=None,
                normalized_truth=None,
                grading_trace={},
                citation_checks=[],
                passed=False,
                outcome=(
                    "ground_truth_ambiguous"
                    if "ambiguous" in truth_snapshot.status
                    else "oracle_failed"
                ),
                failure_mode=(
                    "ground_truth_ambiguous"
                    if "ambiguous" in truth_snapshot.status
                    else "oracle_failed"
                ),
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
        grading = grade_with_trace(task, truth, stack_response.answer)
        passed = bool(grading["passed"])
        claim = str(grading["claim"])
        normalized_claim = grading["normalized_claim"]
        normalized_truth = grading["normalized_truth"]
        citation_result = check_citations(
            stack_response.citations,
            task=task,
            claim=claim,
        )
        source_correct = bool(citation_result["source_correct"])
        citation_supported = bool(citation_result["citation_supports_claim"])
        failure_mode = classify_failure(
            passed=passed,
            answer=stack_response.answer,
            claim=claim,
            source_correct=source_correct,
            citation_supported=citation_supported,
            required_source=task.required_source,
            citations=[item.url for item in stack_response.citations],
        )
        final_verdict = final_verdict_for(
            passed=passed,
            failure_mode=failure_mode,
            scoreable=True,
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
            task_pack_name=task.task_pack_name,
            task_pack_version=task.task_pack_version,
            task_hash=task.stable_hash(),
            grader_version=GRADER_VERSION,
            oracle_version=ORACLE_VERSION,
            value_correct=passed,
            source_correct=source_correct,
            citation_supports_claim=citation_supported,
            final_verdict=final_verdict,
            normalized_claim=normalized_claim,
            normalized_truth=normalized_truth,
            grading_trace=grading["trace"],
            citation_checks=citation_result["checks"],
            passed=passed,
            outcome="correct" if passed else "failed",
            failure_mode=failure_mode,
            citations=stack_response.citations,
            citation_supported=citation_supported,
            search_queries=stack_response.trace.search_queries,
            tools_used=stack_response.trace.tools_used,
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
            task_pack_name=task.task_pack_name,
            task_pack_version=task.task_pack_version,
            task_hash=task.stable_hash(),
            grader_version=GRADER_VERSION,
            oracle_version=ORACLE_VERSION,
            value_correct=False,
            source_correct=False,
            citation_supports_claim=False,
            final_verdict="tool_failure",
            normalized_claim=None,
            normalized_truth=None,
            grading_trace={},
            citation_checks=[],
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


def check_citations(citations: list, *, task: Task, claim: str) -> dict:
    required = normalize_url(task.required_source)
    claim_norm = claim.strip().lower()
    claim_digits = digits(claim_norm)
    checks = []
    source_correct = False
    citation_supports_claim = False
    policy = task.source_policy
    for citation in citations:
        url = normalize_url(citation.url)
        source_matches = source_matches_policy(url, required, task)
        source_correct = source_correct or source_matches
        quote = citation.quote.lower()
        quote_digits = digits(quote)
        quote_supports = bool(
            source_matches
            and (quote or not policy.require_quote)
            and (
                claim_norm in quote
                or (claim_digits and claim_digits in quote_digits)
                or not policy.require_quote
            )
        )
        citation_supports_claim = citation_supports_claim or quote_supports
        checks.append(
            {
                "url": citation.url,
                "source_matches": source_matches,
                "quote_present": bool(quote.strip()),
                "quote_supports_claim": quote_supports,
            }
        )
    return {
        "source_correct": source_correct,
        "citation_supports_claim": citation_supports_claim,
        "checks": checks,
    }


def citations_support(citations: list, *, required_source: str, claim: str) -> bool:
    task = Task(
        id="citation_support",
        question="",
        required_source=required_source,
        ground_truth={"method": "static", "value": "unused"},
    )
    return bool(
        check_citations(citations, task=task, claim=claim)["citation_supports_claim"]
    )


def classify_failure(
    *,
    passed: bool,
    answer: str,
    claim: str = "",
    source_correct: bool,
    citation_supported: bool,
    required_source: str,
    citations: list[str],
) -> str | None:
    if passed:
        if citation_supported:
            return None
        if citations and not source_correct:
            return "wrong_source"
        return "unsupported_citation"
    if not answer.strip() or not claim.strip():
        return "no_answer"
    if citations and not source_correct:
        return "wrong_source"
    return "wrong_value"


def final_verdict_for(*, passed: bool, failure_mode: str | None, scoreable: bool) -> str:
    if not scoreable:
        return failure_mode or "oracle_failed"
    if passed and not failure_mode:
        return "correct"
    if passed and failure_mode:
        return "correct_unsupported"
    return failure_mode or "failed"


def normalize_url(value: str) -> str:
    text = str(value or "").lower().strip()
    text = text.replace("https://", "").replace("http://", "")
    text = text.removeprefix("www.")
    return text.split("#", 1)[0].split("?", 1)[0].rstrip("/")


def source_matches_policy(url: str, required: str, task: Task) -> bool:
    policy = task.source_policy
    candidates = [required, *[normalize_url(item) for item in policy.allowed_sources]]
    if policy.match == "allowed_sources":
        return any(url_matches(url, item, "exact_url") for item in candidates if item)
    return any(url_matches(url, item, policy.match) for item in candidates if item)


def url_matches(url: str, required: str, mode: str) -> bool:
    if not url or not required:
        return False
    if mode == "contains":
        return required in url or url in required
    if mode == "exact_url":
        return url == required
    url_domain, url_path = split_url(url)
    required_domain, required_path = split_url(required)
    if mode == "same_domain":
        return bool(url_domain and url_domain == required_domain)
    if mode == "same_path":
        return bool(url_domain and url_domain == required_domain and url_path == required_path)
    return False


def split_url(value: str) -> tuple[str, str]:
    text = normalize_url(value)
    domain, _, path = text.partition("/")
    return domain, "/" + path if path else ""


def digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit() or ch == ".")
