from __future__ import annotations

import math
import re
from typing import Any

from backend.models import Task


def normalize_value(value: str, grading: str) -> str | float:
    raw = str(value or "").strip()
    if grading in {"numeric_range", "currency_range", "currency_exact"}:
        parsed = parse_number(raw)
        if parsed is not None:
            return parsed
    return normalize_string(raw)


def grade_claim(task: Task, ground_truth: str, claim: str) -> tuple[bool, str | float | None]:
    grading = task.grading
    normalized_claim = normalize_value(claim, grading)
    normalized_truth = normalize_value(ground_truth, grading)

    if grading in {"numeric_range", "currency_range"}:
        if not isinstance(normalized_claim, (int, float)) or not isinstance(
            normalized_truth, (int, float)
        ):
            return False, normalized_claim
        return within_tolerance(
            float(normalized_claim), float(normalized_truth), task.tolerance
        ), normalized_claim

    if grading == "currency_exact":
        if not isinstance(normalized_claim, (int, float)) or not isinstance(
            normalized_truth, (int, float)
        ):
            return False, normalized_claim
        return math.isclose(float(normalized_claim), float(normalized_truth), abs_tol=0.005), normalized_claim

    if grading == "structured_match":
        return normalize_string(claim) == normalize_string(ground_truth), normalized_claim

    return normalize_string(claim) == normalize_string(ground_truth), normalized_claim


def parse_number(value: str) -> float | None:
    text = value.replace(",", "").replace("$", "").strip()
    if "=" in text:
        rhs = text.split("=", 1)[1]
        rhs_match = re.search(r"-?\d+(?:\.\d+)?", rhs)
        if rhs_match:
            return float(rhs_match.group(0))
    suffix_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*(k|m|b|t|thousand|million|billion|trillion)\b",
        text,
        re.I,
    )
    if suffix_match:
        number = float(suffix_match.group(1))
        suffix = suffix_match.group(2).lower()
        multiplier = {
            "k": 1e3,
            "thousand": 1e3,
            "m": 1e6,
            "million": 1e6,
            "b": 1e9,
            "billion": 1e9,
            "t": 1e12,
            "trillion": 1e12,
        }[suffix]
        return number * multiplier
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def normalize_string(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\u2013\u2014]", "-", text)
    text = re.sub(r"[^a-z0-9.%$+\-/ ]", "", text)
    text = re.sub(r"^(current )?(app )?version\s+", "", text)
    return text.strip()


def within_tolerance(claim: float, truth: float, tolerance: str) -> bool:
    tol = tolerance.strip().lower()
    if "exact" in tol or tol == "$0":
        return math.isclose(claim, truth, abs_tol=0.005)
    if "%" in tol:
        pct = parse_number(tol)
        if pct is None:
            return False
        if "+/-" in tol or "±" in tol:
            return abs(claim - truth) <= abs(truth) * (pct / 100.0)
        return abs(claim - truth) <= abs(truth) * (pct / 100.0)
    parsed = parse_number(tol)
    if parsed is not None:
        return abs(claim - truth) <= parsed
    return False


GROUND_TRUTH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": {"type": "string"},
        "evidence": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "notes": {"type": "string"},
    },
    "required": ["value", "evidence", "confidence", "notes"],
    "additionalProperties": False,
}


CLAIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claim": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["claim", "notes"],
    "additionalProperties": False,
}


def build_ground_truth_messages(task: Task, page_text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are Agent Royale's ground-truth extractor. Extract exactly one value "
                "from the provided live page content. Do not infer from memory. If several "
                "similar values appear, use the task's field and grading notes to choose. "
                "You must return a short evidence quote copied from the page content that "
                "contains the chosen value or the exact table row/label supporting it. If "
                "the page content does not visibly support the value, return confidence low."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Task ID: {task.id}\n"
                f"Question: {task.question}\n"
                f"Canonical URL: {task.canonical_url}\n"
                f"Field to extract: {task.extract_field}\n"
                f"Grading: {task.grading}\n"
                f"Tolerance: {task.tolerance}\n"
                f"Grading notes: {task.grading_notes}\n\n"
                f"Live page content:\n{page_text}\n\n"
                "Return JSON with value, evidence, confidence, and notes. The evidence must "
                "be copied from the page content, not from memory."
            ),
        },
    ]


def build_model_answer_messages(task: Task) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are a production web retrieval agent being evaluated on live web "
                "retrieval. Use your web search tool to find the current answer. Return "
                "one concise answer with the specific value and cite the source you used. "
                "Do not answer from memory."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {task.question}\n"
                f"Field needed: {task.extract_field}\n"
                "Find the answer using live web search and return the exact value."
            ),
        },
    ]


def build_claim_messages(task: Task, model_answer: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Extract the single factual claim that should be graded from the model "
                "answer. Return only the value, not the full sentence. Do not correct it."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {task.question}\n"
                f"Expected field: {task.extract_field}\n"
                f"Grading notes: {task.grading_notes}\n\n"
                f"Model answer:\n{model_answer}\n\n"
                "Return JSON with claim and notes."
            ),
        },
    ]
