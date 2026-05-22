from __future__ import annotations

from pathlib import Path
import csv
import io
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from backend.config import APP_DIR, get_settings
from backend.batch import run_batch_collect
from backend.evaluator import evaluate_models, refresh_ground_truth
from backend.models import BatchRequest, ConfigResponse, EvaluationRequest, EvaluationResponse, LiveCheck
from backend.store import build_leaderboard, latest_ground_truth_by_task, list_live_checks, list_runs, now_iso, save_live_check
from backend.task_bank import get_excluded_tasks, get_task, get_tasks


# Launch note:
# The public v1 site intentionally presents a frozen 32-task launch set computed in
# the frontend from complete model coverage. Some backend endpoints still expose
# broader development data and utilities used during benchmark construction.
# Treat those as internal/debug surfaces unless they are explicitly wired into
# the launch UI.
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


@app.get("/api/results.csv")
async def results_csv() -> Response:
    # Internal/dev export. The launch UI hides this endpoint because it is based
    # on the broader backend leaderboard, not the frontend's frozen 32-task v1
    # launch set.
    rows = build_leaderboard()
    fieldnames = [
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
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for rank, row in enumerate(rows, start=1):
        payload = row.model_dump()
        payload["rank"] = rank
        writer.writerow({key: payload.get(key, "") for key in fieldnames})
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=agent-royale-results.csv"},
    )


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


@app.get("/api/ground-truth-audit")
async def ground_truth_audit() -> list[dict]:
    storage_dir = APP_DIR / "storage"
    paths = sorted(storage_dir.glob("*audit*.csv"))
    rows_by_task: dict[str, dict] = {}
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                row["audit_file"] = path.name
                task_id = row.get("task_id", "")
                if not task_id:
                    continue
                current = rows_by_task.get(task_id)
                if current is None or _audit_priority(row) > _audit_priority(current):
                    rows_by_task[task_id] = row
    return list(rows_by_task.values())


def _audit_priority(row: dict) -> int:
    status = str(row.get("status", "")).lower()
    if status == "ok":
        return 4
    if status == "changed":
        return 3
    if row.get("audited_value"):
        return 2
    if status:
        return 1
    return 0


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
