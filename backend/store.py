from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from backend.config import get_settings
from backend.models import GroundTruth, LeaderboardRow, LiveCheck, ModelRun, Vote
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


def save_ground_truth(item: GroundTruth) -> None:
    append_jsonl("ground_truth.jsonl", item.model_dump())


def save_run(item: ModelRun) -> None:
    append_jsonl("runs.jsonl", item.model_dump())


def save_live_check(item: LiveCheck) -> None:
    append_jsonl("live_checks.jsonl", item.model_dump())


def save_vote(item: Vote) -> None:
    append_jsonl("votes.jsonl", item.model_dump())


def list_runs() -> list[ModelRun]:
    return [ModelRun.model_validate(row) for row in read_jsonl("runs.jsonl")]


def list_live_checks() -> list[LiveCheck]:
    return [LiveCheck.model_validate(row) for row in read_jsonl("live_checks.jsonl")]


def list_votes() -> list[Vote]:
    return [Vote.model_validate(row) for row in read_jsonl("votes.jsonl")]


def list_correct_runs_by_task() -> dict[str, list[ModelRun]]:
    grouped: dict[str, list[ModelRun]] = defaultdict(list)
    for run in list_runs():
        if run.passed and not run.error:
            grouped[run.task_id].append(run)
    return grouped


def latest_ground_truth_by_task() -> dict[str, GroundTruth]:
    latest: dict[str, GroundTruth] = {}
    for row in read_jsonl("ground_truth.jsonl"):
        item = GroundTruth.model_validate(row)
        latest[item.task_id] = item
    return latest


def build_leaderboard() -> list[LeaderboardRow]:
    # Development leaderboard over all currently official tasks. The public v1
    # site computes its launch leaderboard in the frontend from the frozen
    # 43-task complete-coverage slice, so do not use this function as the v1
    # public scoreboard without applying the same slice.
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
