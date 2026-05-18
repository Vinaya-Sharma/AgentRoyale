from __future__ import annotations

from pathlib import Path
import csv
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import APP_DIR, get_settings
from backend.batch import run_batch_collect
from backend.evaluator import evaluate_models, refresh_ground_truth
from backend.models import BatchRequest, ConfigResponse, EvaluationRequest, EvaluationResponse, LiveCheck, Vote, VoteRequest
from backend.store import build_leaderboard, latest_ground_truth_by_task, list_correct_runs_by_task, list_live_checks, list_runs, list_votes, now_iso, save_live_check, save_vote
from backend.task_bank import get_excluded_tasks, get_task, get_tasks


settings = get_settings()
frontend_dir = APP_DIR / "frontend"

app = FastAPI(title="Agent Royale API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config", response_model=ConfigResponse)
async def config() -> ConfigResponse:
    return ConfigResponse(
        app_name=settings.app_name,
        default_models=list(settings.default_models),
        has_openrouter_key=bool(settings.openrouter_api_key),
        has_bright_data_key=bool(settings.bright_data_api_key),
    )


@app.get("/api/tasks")
async def tasks() -> list[dict]:
    excluded = get_excluded_tasks()
    return [
        {
            **task.model_dump(),
            "official": task.id not in excluded,
            "exclusion_reason": excluded.get(task.id, ""),
        }
        for task in get_tasks()
    ]


@app.get("/api/tasks/{task_id}")
async def task(task_id: str) -> dict:
    try:
        return get_task(task_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/ground-truth")
async def ground_truth(task_id: str) -> dict:
    try:
        item = await refresh_ground_truth(get_task(task_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return item.model_dump()


@app.post("/api/evaluations", response_model=EvaluationResponse)
async def evaluations(req: EvaluationRequest) -> EvaluationResponse:
    try:
        selected = get_task(req.task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        ground_truth, runs = await evaluate_models(
            selected,
            req.models,
            refresh=req.refresh_ground_truth,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return EvaluationResponse(task=selected, ground_truth=ground_truth, runs=runs)


@app.get("/api/runs")
async def runs() -> list[dict]:
    return [run.model_dump() for run in list_runs()]


@app.get("/api/ground-truth")
async def ground_truth_items() -> list[dict]:
    return [item.model_dump() for item in latest_ground_truth_by_task().values()]


@app.get("/api/live-checks")
async def live_checks() -> list[dict]:
    return [item.model_dump() for item in list_live_checks()]


@app.post("/api/live-checks", response_model=LiveCheck)
async def create_live_check(req: EvaluationRequest) -> LiveCheck:
    try:
        selected = get_task(req.task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        ground_truth, runs = await evaluate_models(
            selected,
            req.models,
            refresh=req.refresh_ground_truth,
            save_runs=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    item = LiveCheck(
        check_id=str(uuid.uuid4()),
        task=selected,
        ground_truth=ground_truth,
        runs=runs,
        created_at=now_iso(),
    )
    save_live_check(item)
    return item


@app.get("/api/leaderboard")
async def leaderboard() -> list[dict]:
    return [row.model_dump() for row in build_leaderboard()]


@app.post("/api/batch-runs")
async def batch_runs(req: BatchRequest) -> dict:
    try:
        return await run_batch_collect(
            models=req.models or None,
            repetitions=req.repetitions,
            domain=req.domain,
            limit=req.limit,
            refresh_ground_truth=req.refresh_ground_truth,
            include_excluded=req.include_excluded,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/arena/pairs")
async def arena_pairs() -> list[dict]:
    tasks_by_id = {task.id: task for task in get_tasks()}
    pairs: list[dict] = []
    for task_id, runs in list_correct_runs_by_task().items():
        unique: list = []
        seen_models: set[str] = set()
        for run in reversed(runs):
            if run.model in seen_models:
                continue
            seen_models.add(run.model)
            unique.append(run)
            if len(unique) == 2:
                break
        if len(unique) < 2:
            continue
        task = tasks_by_id.get(task_id)
        if not task:
            continue
        pairs.append(
            {
                "task": task.model_dump(),
                "left": unique[0].model_dump(),
                "right": unique[1].model_dump(),
            }
        )
    return pairs


@app.get("/api/votes")
async def votes() -> list[dict]:
    return [vote.model_dump() for vote in list_votes()]


@app.get("/api/ground-truth-audit")
async def ground_truth_audit() -> list[dict]:
    path = APP_DIR / "storage" / "ground_truth_audit.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@app.post("/api/votes")
async def vote(req: VoteRequest) -> dict:
    item = Vote(**req.model_dump(), created_at=now_iso())
    save_vote(item)
    return item.model_dump()


if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/{path:path}")
async def spa(path: str) -> FileResponse:
    static_file = frontend_dir / path
    if static_file.exists() and static_file.is_file():
        return FileResponse(static_file)
    return FileResponse(frontend_dir / "index.html")
