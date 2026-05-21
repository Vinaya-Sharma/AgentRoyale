from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.store import build_leaderboard, latest_ground_truth_by_task, read_jsonl
from backend.task_bank import get_excluded_tasks, get_official_tasks


LEADERBOARD_FIELDS = [
    "rank",
    "model",
    "total_runs",
    "scored_runs",
    "live_exact_accuracy",
    "verified_retrieval_rate",
    "avg_tool_calls",
    "avg_latency_ms",
    "avg_cost_usd",
    "accuracy_per_dollar",
    "consistency_stddev",
]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_leaderboard_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEADERBOARD_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_official_tasks_csv(path: Path) -> None:
    tasks = get_official_tasks()
    if not tasks:
        path.write_text("", encoding="utf-8")
        return

    fields = list(tasks[0].model_dump().keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for task in tasks:
            writer.writerow(task.model_dump())


def latest_created_at() -> str | None:
    values = [
        row.get("created_at")
        for row in read_jsonl("runs.jsonl")
        if isinstance(row.get("created_at"), str)
    ]
    return max(values) if values else None


def latest_ground_truth_at() -> str | None:
    values = [
        item.fetched_at
        for item in latest_ground_truth_by_task().values()
        if isinstance(item.fetched_at, str)
    ]
    return max(values) if values else None


def main() -> None:
    settings = get_settings()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = settings.storage_dir / "launch-snapshots" / timestamp
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    leaderboard_rows = [
        {"rank": rank, **row.model_dump()}
        for rank, row in enumerate(build_leaderboard(), start=1)
    ]

    write_json(
        snapshot_dir / "manifest.json",
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "official_task_count": len(get_official_tasks()),
            "quarantined_task_count": len(get_excluded_tasks()),
            "model_count": len(leaderboard_rows),
            "latest_result_at": latest_created_at(),
            "latest_ground_truth_at": latest_ground_truth_at(),
            "notes": (
                "Official tasks are audited tasks only. Quarantined tasks are "
                "exported for transparency but are excluded from leaderboard scoring."
            ),
        },
    )
    write_json(snapshot_dir / "leaderboard.json", leaderboard_rows)
    write_leaderboard_csv(snapshot_dir / "leaderboard.csv", leaderboard_rows)
    write_official_tasks_csv(snapshot_dir / "official_tasks.csv")
    write_json(snapshot_dir / "excluded_tasks.json", get_excluded_tasks())

    for filename in ["runs.jsonl", "ground_truth.jsonl", "live_checks.jsonl"]:
        source = settings.storage_dir / filename
        if source.exists():
            shutil.copy2(source, snapshot_dir / filename)

    print(snapshot_dir)


if __name__ == "__main__":
    main()
