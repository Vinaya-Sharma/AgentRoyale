from __future__ import annotations

import re
from typing import Any
from datetime import datetime, timezone

import httpx

from agent_royale.grading import normalize_value
from agent_royale.schema import GroundTruthSnapshot, Task


async def fetch_ground_truth(task: Task, timeout_seconds: float = 30) -> tuple[str | float, str]:
    snapshot = await fetch_ground_truth_snapshot(task, timeout_seconds=timeout_seconds)
    if snapshot.status != "verified" or snapshot.value is None:
        raise RuntimeError(snapshot.error or f"Ground truth for {task.id} is {snapshot.status}")
    return snapshot.value, snapshot.source_url or task.required_source


async def fetch_ground_truth_snapshot(task: Task, timeout_seconds: float = 30) -> GroundTruthSnapshot:
    spec = task.ground_truth
    fetched_at = now_utc()
    try:
        if spec.method == "static":
            source = spec.source_url or task.required_source
            return verified_snapshot(
                task,
                value=str(spec.value),
                source_url=source,
                fetched_at=fetched_at,
                parser="static value",
                evidence_text=str(spec.value),
                raw_excerpt=str(spec.value),
            )
        if spec.method == "http_json":
            assert spec.url and spec.field
            async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
                response = await client.get(spec.url, headers=spec.headers)
                response.raise_for_status()
                payload = response.json()
            value = read_field(payload, spec.field)
            return verified_snapshot(
                task,
                value=str(value),
                source_url=spec.source_url or spec.url,
                final_url=str(response.url),
                fetched_at=fetched_at,
                parser=f"field:{spec.field}",
                evidence_text=compact_excerpt(value),
                raw_excerpt=compact_excerpt(payload),
            )
        if spec.method == "http_regex":
            assert spec.url and spec.regex
            async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
                response = await client.get(spec.url, headers=spec.headers)
                response.raise_for_status()
                text = response.text
            return snapshot_from_regex(
                task,
                text=text,
                source_url=spec.source_url or spec.url,
                final_url=str(response.url),
                fetched_at=fetched_at,
                parser=f"regex:{spec.regex}",
            )
        if spec.method == "bright_data":
            return await fetch_bright_data_ground_truth_snapshot(task, fetched_at=fetched_at)
    except httpx.HTTPStatusError as exc:
        return failed_snapshot(
            task,
            status="source_unreachable",
            fetched_at=fetched_at,
            error=f"{exc.response.status_code} {exc.response.reason_phrase}",
        )
    except Exception as exc:
        return failed_snapshot(task, status="oracle_failed", fetched_at=fetched_at, error=str(exc))
    return failed_snapshot(
        task,
        status="oracle_failed",
        fetched_at=fetched_at,
        error=f"Unsupported ground-truth method: {spec.method}",
    )


async def fetch_bright_data_ground_truth(task: Task) -> str:
    snapshot = await fetch_bright_data_ground_truth_snapshot(task, fetched_at=now_utc())
    if snapshot.status != "verified" or snapshot.value is None:
        raise RuntimeError(snapshot.error or f"Bright Data oracle for {task.id} is {snapshot.status}")
    return str(snapshot.value)


async def fetch_bright_data_ground_truth_snapshot(task: Task, fetched_at: str) -> GroundTruthSnapshot:
    spec = task.ground_truth
    from backend.config import get_settings

    if not get_settings().bright_data_api_key:
        return failed_snapshot(
            task,
            status="oracle_failed",
            fetched_at=fetched_at,
            error=(
                "BRIGHT_DATA_API_KEY is required for ground_truth.method=bright_data. "
                "Use public API task packs to run Agent Royale without Bright Data."
            ),
        )
    assert spec.tool and spec.url
    from backend.bright_data import fetch_url_with_fallbacks, result_text

    result = await fetch_url_with_fallbacks(spec.tool, spec.url)
    if result.is_error:
        return failed_snapshot(
            task,
            status="source_unreachable",
            fetched_at=fetched_at,
            error=result.error or f"Bright Data tool {spec.tool} failed",
            raw_excerpt=compact_excerpt(result.raw),
        )
    if spec.field:
        payload = result.structured_content
        if payload is None:
            text = result_text(result, limit=50000)
            payload = parse_structured_text(text)
        value = read_field(payload, spec.field)
        return verified_snapshot(
            task,
            value=str(value),
            source_url=spec.source_url or spec.url or task.required_source,
            final_url=str(result.raw.get("final_url") or spec.url or ""),
            fetched_at=fetched_at,
            parser=f"bright_data_field:{spec.field}",
            evidence_text=compact_excerpt(value),
            raw_excerpt=compact_excerpt(payload),
            tool=result.endpoint,
            validation_checks={"structured_content": result.structured_content is not None},
        )
    assert spec.regex
    text = result_text(result, limit=50000)
    snapshot = snapshot_from_regex(
        task,
        text=text,
        source_url=spec.source_url or spec.url or task.required_source,
        final_url=str(result.raw.get("final_url") or spec.url or ""),
        fetched_at=fetched_at,
        parser=f"bright_data_regex:{spec.regex}",
        tool=result.endpoint,
    )
    snapshot.raw_excerpt = compact_excerpt(text)
    return snapshot


def snapshot_from_regex(
    task: Task,
    *,
    text: str,
    source_url: str,
    final_url: str,
    fetched_at: str,
    parser: str,
    tool: str | None = None,
) -> GroundTruthSnapshot:
    spec = task.ground_truth
    assert spec.regex
    candidates = list(regex_candidates(text, spec.regex))
    if spec.require_near_text:
        candidates = [
            item for item in candidates if all(term.lower() in item["context"].lower() for term in spec.require_near_text)
        ]
    if spec.reject_near_text:
        candidates = [
            item for item in candidates if not any(term.lower() in item["context"].lower() for term in spec.reject_near_text)
        ]
    checks = {
        "regex_matched": bool(candidates),
        "required_context_found": not spec.require_near_text or bool(candidates),
        "reject_context_absent": True,
        "single_candidate": len(candidates) == 1,
    }
    if not candidates:
        return failed_snapshot(
            task,
            status="selector_broken",
            fetched_at=fetched_at,
            source_url=source_url,
            final_url=final_url,
            parser=parser,
            tool=tool,
            raw_excerpt=compact_excerpt(text),
            error=f"Regex did not match verified context for {task.id}",
            validation_checks=checks,
        )
    unique_values = {candidate["value"] for candidate in candidates}
    if len(unique_values) > 1:
        return failed_snapshot(
            task,
            status="ground_truth_ambiguous",
            fetched_at=fetched_at,
            source_url=source_url,
            final_url=final_url,
            parser=parser,
            tool=tool,
            evidence_text=" | ".join(candidate["evidence"] for candidate in candidates[:3]),
            raw_excerpt=compact_excerpt(text),
            error=f"Regex found {len(unique_values)} plausible values for {task.id}",
            ambiguity_flags=["multiple_candidate_values"],
            validation_checks=checks,
        )
    candidate = candidates[0]
    return verified_snapshot(
        task,
        value=candidate["value"],
        source_url=source_url,
        final_url=final_url,
        fetched_at=fetched_at,
        parser=parser,
        evidence_text=candidate["evidence"],
        raw_excerpt=compact_excerpt(text),
        tool=tool,
        validation_checks=checks,
    )


def regex_candidates(text: str, pattern: str) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for match in re.finditer(pattern, text, re.I | re.S):
        value = match.group(1) if match.groups() else match.group(0)
        value = str(value).strip()
        start, end = match.span()
        context = text[max(0, start - 240) : min(len(text), end + 240)]
        candidates.append(
            {
                "value": value,
                "context": context,
                "evidence": " ".join(context.split())[:600],
            }
        )
    return candidates


def verified_snapshot(
    task: Task,
    *,
    value: str | float,
    source_url: str,
    fetched_at: str,
    final_url: str = "",
    parser: str,
    evidence_text: str,
    raw_excerpt: str,
    tool: str | None = None,
    validation_checks: dict[str, bool] | None = None,
) -> GroundTruthSnapshot:
    return GroundTruthSnapshot(
        task_id=task.id,
        status="verified",
        value=value,
        normalized_value=normalize_value(value, task.answer_type),
        source_url=source_url,
        final_url=final_url or source_url,
        method=task.ground_truth.method,
        tool=tool or task.ground_truth.tool,
        fetched_at=fetched_at,
        parser=parser,
        evidence_text=compact_excerpt(evidence_text, limit=600),
        raw_excerpt=compact_excerpt(raw_excerpt),
        confidence="verified",
        validation_checks=validation_checks or {"value_found": True},
    )


def failed_snapshot(
    task: Task,
    *,
    status: str,
    fetched_at: str,
    error: str,
    source_url: str = "",
    final_url: str = "",
    parser: str = "",
    tool: str | None = None,
    evidence_text: str = "",
    raw_excerpt: str = "",
    ambiguity_flags: list[str] | None = None,
    validation_checks: dict[str, bool] | None = None,
) -> GroundTruthSnapshot:
    return GroundTruthSnapshot(
        task_id=task.id,
        status=status,  # type: ignore[arg-type]
        value=None,
        normalized_value=None,
        source_url=source_url or task.ground_truth.source_url or task.ground_truth.url or task.required_source,
        final_url=final_url or source_url or task.ground_truth.url or task.required_source,
        method=task.ground_truth.method,
        tool=tool or task.ground_truth.tool,
        fetched_at=fetched_at,
        parser=parser,
        evidence_text=compact_excerpt(evidence_text, limit=600),
        raw_excerpt=compact_excerpt(raw_excerpt),
        confidence="ambiguous" if "ambiguous" in status or status == "conflicting_values" else "failed",
        ambiguity_flags=ambiguity_flags or [],
        validation_checks=validation_checks or {},
        error=error,
    )


def compact_excerpt(value: Any, limit: int = 2000) -> str:
    text = str(value)
    return " ".join(text.split())[:limit]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_structured_text(text: str) -> Any:
    import json

    marker = "STRUCTURED_CONTENT:"
    if marker in text:
        text = text.split(marker, 1)[1].strip()
    return json.loads(text)


def read_field(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(f"Cannot read {part!r} from non-container in {path!r}")
    return current
