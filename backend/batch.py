from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator

from backend.config import get_settings
from backend.evaluator import evaluate_models
from backend.models import EvaluationResponse, ModelRun, Task
from backend.task_bank import get_official_task_ids, get_tasks


@dataclass
class BatchProgress:
    task_id: str
    repetition: int
    task_index: int
    task_total: int
    runs: list[ModelRun]
    error: str | None = None


def select_tasks(
    domain: str | None = None,
    limit: int | None = None,
    start_at: str | None = None,
    task_ids: list[str] | None = None,
    include_excluded: bool = False,
) -> list[Task]:
    tasks = get_tasks()
    if not include_excluded:
        official = get_official_task_ids()
        tasks = [task for task in tasks if task.id in official]
    if domain and domain != "all":
        tasks = [task for task in tasks if task.domain == domain]
    if task_ids:
        wanted = set(task_ids)
        tasks = [task for task in tasks if task.id in wanted]
    if start_at:
        ids = [task.id for task in tasks]
        if start_at in ids:
            tasks = tasks[ids.index(start_at) :]
    if limit:
        tasks = tasks[:limit]
    return tasks


async def run_batch(
    *,
    models: list[str] | None = None,
    repetitions: int = 3,
    domain: str | None = None,
    limit: int | None = None,
    start_at: str | None = None,
    task_ids: list[str] | None = None,
    refresh_ground_truth: bool = True,
    include_excluded: bool = False,
) -> AsyncIterator[BatchProgress]:
    settings = get_settings()
    selected_models = models or list(settings.default_models)
    selected_tasks = select_tasks(domain, limit, start_at, task_ids, include_excluded)
    total = len(selected_tasks)
    for task_index, task in enumerate(selected_tasks, start=1):
        for rep in range(1, repetitions + 1):
            try:
                _ground_truth, runs = await evaluate_models(
                    task,
                    selected_models,
                    refresh=refresh_ground_truth,
                )
                yield BatchProgress(
                    task_id=task.id,
                    repetition=rep,
                    task_index=task_index,
                    task_total=total,
                    runs=runs,
                )
            except Exception as exc:
                yield BatchProgress(
                    task_id=task.id,
                    repetition=rep,
                    task_index=task_index,
                    task_total=total,
                    runs=[],
                    error=str(exc),
                )
            await asyncio.sleep(0)


async def run_batch_collect(**kwargs) -> dict:
    completed = 0
    errors: list[dict] = []
    run_count = 0
    async for progress in run_batch(**kwargs):
        completed += 1
        run_count += len(progress.runs)
        if progress.error:
            errors.append(
                {
                    "task_id": progress.task_id,
                    "repetition": progress.repetition,
                    "error": progress.error,
                }
            )
    return {"completed_task_repetitions": completed, "run_count": run_count, "errors": errors}
