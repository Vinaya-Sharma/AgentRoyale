from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path

from backend.config import get_settings
from backend.models import Task


HEADER_MAP = {
    "ID": "id",
    "Domain": "domain",
    "Diff": "difficulty",
    "Question": "question",
    "Canonical URL": "canonical_url",
    "Extract This Field": "extract_field",
    "Grading": "grading",
    "BD Tool": "bd_tool",
    "Update Freq": "update_freq",
    "Ground Truth Region": "ground_truth_region",
    "Tolerance": "tolerance",
    "Optimal Path": "optimal_path",
    "Grading Notes": "grading_notes",
    "Why It Matters": "why_it_matters",
}


def load_tasks_from_csv(path: Path) -> list[Task]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    tasks: list[Task] = []
    for row in rows:
        payload = {field: row.get(header, "") for header, field in HEADER_MAP.items()}
        if payload["id"]:
            tasks.append(Task.model_validate(payload))
    return tasks


@lru_cache(maxsize=1)
def get_tasks() -> list[Task]:
    return load_tasks_from_csv(get_settings().data_path)


def get_task(task_id: str) -> Task:
    for task in get_tasks():
        if task.id == task_id:
            return task
    raise KeyError(f"Unknown task_id: {task_id}")


@lru_cache(maxsize=1)
def get_excluded_tasks() -> dict[str, str]:
    path = get_settings().data_path.parent / "excluded_tasks.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def get_official_task_ids() -> set[str]:
    excluded = get_excluded_tasks()
    return {task.id for task in get_tasks() if task.id not in excluded}


def get_official_tasks() -> list[Task]:
    official = get_official_task_ids()
    return [task for task in get_tasks() if task.id in official]
