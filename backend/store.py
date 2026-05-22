from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import httpx

from backend.config import get_settings
from backend.models import GroundTruth, LeaderboardRow, LiveCheck, ModelRun
from backend.task_bank import get_official_task_ids


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonl_path(name: str) -> Path:
    settings = get_settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    return settings.storage_dir / name


def append_jsonl(name: str, payload: dict[str, Any]) -> None:
    path = _jsonl_path(name)
    with path.open("a", encoding="utf-8") as handle:
        # Keep JSONL physically one-line even when scraped pages contain Unicode
        # line separators such as U+2028.
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_jsonl(name: str) -> list[dict[str, Any]]:
    path = _jsonl_path(name)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # Ignore malformed historical rows so one interrupted scrape cannot
            # poison the entire benchmark cache.
            continue
    return rows


def _supabase_live_checks_enabled() -> bool:
    settings = get_settings()
    return bool(settings.supabase_url and settings.supabase_service_key)


def _supabase_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
    }


def _supabase_live_checks_url() -> str:
    settings = get_settings()
    return f"{settings.supabase_url}/rest/v1/live_checks"


def save_live_check_to_supabase(payload: dict[str, Any]) -> None:
    if not _supabase_live_checks_enabled():
        return
    body = {
        "check_id": payload["check_id"],
        "created_at": payload["created_at"],
        "task_id": payload.get("task", {}).get("id", ""),
        "payload": payload,
    }
    headers = {
        **_supabase_headers(),
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    with httpx.Client(timeout=10) as client:
        response = client.post(_supabase_live_checks_url(), headers=headers, json=body)
        response.raise_for_status()


def read_live_checks_from_supabase() -> list[dict[str, Any]]:
    if not _supabase_live_checks_enabled():
        return []
    params = {
        "select": "payload",
        "order": "created_at.asc",
    }
    with httpx.Client(timeout=10) as client:
        response = client.get(
            _supabase_live_checks_url(),
            headers=_supabase_headers(),
            params=params,
        )
        response.raise_for_status()
    return [row["payload"] for row in response.json() if row.get("payload")]


def save_ground_truth(item: GroundTruth) -> None:
    append_jsonl("ground_truth.jsonl", item.model_dump())


def save_run(item: ModelRun) -> None:
    append_jsonl("runs.jsonl", item.model_dump())


def save_live_check(item: LiveCheck) -> None:
    payload = item.model_dump()
    append_jsonl("live_checks.jsonl", payload)
    try:
        save_live_check_to_supabase(payload)
    except Exception:
        # Do not fail the public demo after the expensive live check has completed.
        pass


def list_runs() -> list[ModelRun]:
    return [ModelRun.model_validate(row) for row in read_jsonl("runs.jsonl")]


def list_live_checks() -> list[LiveCheck]:
    try:
        rows = read_live_checks_from_supabase()
    except Exception:
        rows = []
    if not rows:
        rows = read_jsonl("live_checks.jsonl")
    return [LiveCheck.model_validate(row) for row in rows]


def latest_ground_truth_by_task() -> dict[str, GroundTruth]:
    latest: dict[str, GroundTruth] = {}
    for row in read_jsonl("ground_truth.jsonl"):
        item = GroundTruth.model_validate(row)
        latest[item.task_id] = item
    return latest


def build_leaderboard() -> list[LeaderboardRow]:
    # Development leaderboard over all currently official tasks. The public v1
    # site computes its launch leaderboard in the frontend from the frozen
    # 32-task public launch set, so do not use this function as the v1
    # public scoreboard without applying the same task filter.
    settings = get_settings()
    default_models = set(settings.default_models)
    official_task_ids = get_official_task_ids()
    latest_by_model_task: dict[tuple[str, str], list[ModelRun]] = defaultdict(list)
    for run in list_runs():
        if run.error or run.model not in default_models or run.task_id not in official_task_ids:
            continue
        latest_by_model_task[(run.model, run.task_id)].append(run)

    runs_by_model: dict[str, list[ModelRun]] = defaultdict(list)
    for (model, _task_id), runs in latest_by_model_task.items():
        runs.sort(key=lambda item: item.created_at)
        runs_by_model[model].extend(runs[-3:])

    rows: list[LeaderboardRow] = []
    for model, runs in runs_by_model.items():
        scored = [run for run in runs if run.error is None]
        if not scored:
            continue
        pass_values = [1.0 if run.passed else 0.0 for run in scored]
        accuracy = mean(pass_values)
        costs = [run.estimated_cost_usd for run in scored]
        avg_cost = mean(costs) if costs else 0.0
        verified_correct = [run for run in scored if run.passed and run.verified_retrieval]
        correct = [run for run in scored if run.passed]
        verified_rate = len(verified_correct) / len(correct) if correct else 0.0
        rows.append(
            LeaderboardRow(
                model=model,
                total_runs=len(runs),
                scored_runs=len(scored),
                live_exact_accuracy=round(accuracy, 4),
                verified_retrieval_rate=round(verified_rate, 4),
                avg_tool_calls=round(mean(run.tool_calls for run in scored), 3),
                avg_latency_ms=round(mean(run.latency_ms for run in scored), 2),
                avg_cost_usd=round(avg_cost, 5),
                accuracy_per_dollar=round(accuracy / avg_cost, 3) if avg_cost else None,
                consistency_stddev=round(pstdev(pass_values), 4)
                if len(pass_values) > 1
                else None,
            )
        )
    rows.sort(
        key=lambda row: (
            -row.live_exact_accuracy,
            row.avg_cost_usd,
            row.avg_latency_ms,
        )
    )
    return rows
