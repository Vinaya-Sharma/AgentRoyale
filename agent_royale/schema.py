from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


AnswerType = Literal["string", "number", "currency", "percentage", "date", "enum"]
GroundTruthMethod = Literal["static", "http_json", "http_regex", "bright_data"]


class Citation(BaseModel):
    url: str = ""
    quote: str = ""


class StackTrace(BaseModel):
    search_queries: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    latency_ms: float | None = None
    cost_usd: float | None = None


class StackResponse(BaseModel):
    answer: str = ""
    citations: list[Citation] = Field(default_factory=list)
    trace: StackTrace = Field(default_factory=StackTrace)


class GroundTruthSpec(BaseModel):
    method: GroundTruthMethod
    value: str | float | int | None = None
    source_url: str | None = None
    url: str | None = None
    tool: str | None = None
    field: str | None = None
    regex: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_method_fields(self) -> "GroundTruthSpec":
        if self.method == "static" and self.value is None:
            raise ValueError("ground_truth.value is required for method=static")
        if self.method == "http_json" and (not self.url or not self.field):
            raise ValueError("ground_truth.url and ground_truth.field are required for method=http_json")
        if self.method == "http_regex" and (not self.url or not self.regex):
            raise ValueError("ground_truth.url and ground_truth.regex are required for method=http_regex")
        if self.method == "bright_data":
            if not self.url or not self.tool:
                raise ValueError("ground_truth.url and ground_truth.tool are required for method=bright_data")
            if not self.field and not self.regex:
                raise ValueError("ground_truth.field or ground_truth.regex is required for method=bright_data")
        return self


class Task(BaseModel):
    id: str
    question: str
    required_source: str
    answer_type: AnswerType = "string"
    tolerance: float | str = 0
    labels: list[str] = Field(default_factory=list)
    ground_truth: GroundTruthSpec
    notes: str = ""


class TaskPack(BaseModel):
    name: str = "custom"
    description: str = ""
    tasks: list[Task]


class RunRecord(BaseModel):
    run_id: str
    task_id: str
    task_question: str
    target: str
    answer: str
    extracted_claim: str | float | None
    ground_truth: str | float
    normalized_claim: str | float | None
    normalized_truth: str | float | None
    passed: bool
    outcome: str
    failure_mode: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    citation_supported: bool = False
    required_source: str
    latency_ms: float
    cost_usd: float | None = None
    created_at: str
    error: str | None = None


def load_task_pack(path: Path) -> TaskPack:
    data = _load_data(path)
    if isinstance(data, list):
        data = {"name": path.stem, "tasks": data}
    if isinstance(data, dict) and "tasks" not in data and "id" in data:
        data = {"name": path.stem, "tasks": [data]}
    return TaskPack.model_validate(data)


def load_task_packs(paths: list[Path]) -> list[TaskPack]:
    packs: list[TaskPack] = []
    for path in paths:
        if path.is_dir():
            files = sorted(
                item for item in path.rglob("*") if item.suffix.lower() in {".yaml", ".yml", ".json"}
            )
            if not files:
                raise ValueError(f"No task files found in {path}")
            packs.extend(load_task_pack(item) for item in files)
        else:
            packs.append(load_task_pack(path))
    return packs


def flatten_tasks(packs: list[TaskPack]) -> list[Task]:
    tasks: list[Task] = []
    seen: set[str] = set()
    for pack in packs:
        for task in pack.tasks:
            if task.id in seen:
                raise ValueError(f"Duplicate task id: {task.id}")
            seen.add(task.id)
            tasks.append(task)
    return tasks


def validation_errors(path: Path) -> list[str]:
    try:
        load_task_pack(path)
    except ValidationError as exc:
        return [f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()]
    except Exception as exc:
        return [str(exc)]
    return []


def _load_data(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)
