from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Task(BaseModel):
    id: str
    domain: str
    difficulty: str
    question: str
    canonical_url: str
    extract_field: str
    grading: str
    bd_tool: str
    update_freq: str
    ground_truth_region: str
    tolerance: str
    optimal_path: str
    grading_notes: str
    why_it_matters: str


class GroundTruth(BaseModel):
    task_id: str
    value: str
    normalized_value: str | float
    source_url: str
    fetched_at: str
    extraction_confidence: Literal["high", "medium", "low"] = "medium"
    notes: str = ""
    raw_preview: str = ""


class TraceStep(BaseModel):
    n: int
    action: str
    target: str
    ok: bool = True
    latency_ms: float | None = None


class ModelRun(BaseModel):
    run_id: str
    task_id: str
    model: str
    answer: str
    extracted_claim: str
    normalized_claim: str | float | None = None
    passed: bool
    verified_retrieval: bool
    trace: list[TraceStep]
    tool_calls: int
    latency_ms: float
    estimated_cost_usd: float
    error: str | None = None
    created_at: str


class EvaluationRequest(BaseModel):
    task_id: str
    models: list[str] = Field(default_factory=list, max_length=6)
    refresh_ground_truth: bool = True


class BatchRequest(BaseModel):
    models: list[str] = Field(default_factory=list, max_length=10)
    repetitions: int = Field(default=3, ge=1, le=5)
    domain: str | None = None
    limit: int | None = Field(default=None, ge=1)
    refresh_ground_truth: bool = True
    include_excluded: bool = False


class EvaluationResponse(BaseModel):
    task: Task
    ground_truth: GroundTruth
    runs: list[ModelRun]


class LiveCheck(BaseModel):
    check_id: str
    task: Task
    ground_truth: GroundTruth
    runs: list[ModelRun]
    created_at: str


class VoteRequest(BaseModel):
    task_id: str
    left_run_id: str
    right_run_id: str
    vote: Literal["left", "right", "tie"]
    left_ideal: bool = False
    right_ideal: bool = False


class Vote(BaseModel):
    task_id: str
    left_run_id: str
    right_run_id: str
    vote: Literal["left", "right", "tie"]
    left_ideal: bool = False
    right_ideal: bool = False
    created_at: str


class LeaderboardRow(BaseModel):
    model: str
    total_runs: int
    scored_runs: int
    live_exact_accuracy: float
    verified_retrieval_rate: float
    avg_tool_calls: float
    avg_latency_ms: float
    avg_cost_usd: float
    accuracy_per_dollar: float | None
    consistency_stddev: float | None


class ConfigResponse(BaseModel):
    app_name: str
    default_models: list[str]
    has_openrouter_key: bool
    has_bright_data_key: bool


JsonDict = dict[str, Any]
