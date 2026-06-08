from __future__ import annotations

import math
import json
import re
from datetime import datetime
from typing import Any

from agent_royale.schema import Task


def extract_claim(answer: str, answer_type: str, truth: str | float | None = None) -> str:
    text = str(answer or "").strip()
    if not text:
        return ""
    text = unwrap_answer_payload(text)
    if answer_type == "currency":
        match = re.search(r"\$?\s*-?\d[\d,]*(?:\.\d+)?", text)
        return match.group(0).strip() if match else text
    if answer_type in {"number", "percentage"}:
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?\s*(?:%|k|m|b|t|thousand|million|billion|trillion)?", text, re.I)
        return match.group(0).strip() if match else text
    if answer_type == "date":
        match = re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b[A-Z][a-z]+ \d{1,2}, \d{4}\b", text)
        return match.group(0).strip() if match else text
    if answer_type in {"string", "enum"}:
        return extract_string_claim(text, truth)
    return text.split("\n", 1)[0].strip()


def unwrap_answer_payload(text: str) -> str:
    """Handle adapters that return a JSON response body as their answer string."""
    stripped = text.strip()
    if not stripped.startswith("{"):
        return text
    try:
        payload = json.loads(stripped)
    except Exception:
        return text
    answer = payload.get("answer") if isinstance(payload, dict) else None
    if answer is None:
        return ""
    return str(answer).strip()


def extract_string_claim(text: str, truth: str | float | None = None) -> str:
    truth_text = str(truth or "").strip()
    if truth_text:
        normalized_truth = normalize_string(truth_text)
        if normalized_truth and normalized_truth in normalize_string(text):
            return truth_text
        shaped = extract_by_truth_shape(text, truth_text)
        if shaped:
            return shaped

    phrased = phrase_value_candidate(text)
    if phrased:
        return phrased

    candidates = quoted_candidates(text) + token_candidates(text)
    if candidates:
        return candidates[0]
    return text.split("\n", 1)[0].strip()


def extract_by_truth_shape(text: str, truth: str) -> str:
    patterns: list[str] = []
    if "@" in truth:
        patterns.append(r"\b[A-Za-z0-9._-]+@[A-Za-z0-9._+-]+\b")
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0).strip()
        return ""
    if re.search(r"\d", truth) and "." in truth:
        patterns.append(r"\bv?\d+(?:\.\d+)+(?:[-+][A-Za-z0-9._-]+)?\b")
    if "-" in truth or "." in truth:
        patterns.append(r"\b[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)+\b")
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return ""


def quoted_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"`([^`]+)`|\"([^\"]+)\"|'([^']+)'", text):
        value = next(part for part in match.groups() if part is not None).strip()
        if not value or ":" in value:
            continue
        candidates.append(value)
    return candidates


def phrase_value_candidate(text: str) -> str:
    patterns = [
        r"\b(?:is|are|was|were|listed as|value is|value listed is)\s+[`\"']?([A-Za-z0-9._@+-]+)",
        r":\s*[`\"']?([A-Za-z0-9._@+-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = match.group(1).strip().strip("`\"'.")
            if value.lower() not in {"the", "a", "an"}:
                return value
    return ""


def token_candidates(text: str) -> list[str]:
    patterns = [
        r"\b[A-Za-z0-9._-]+@[A-Za-z0-9._+-]+\b",
        r"\bv?\d+(?:\.\d+)+(?:[-+][A-Za-z0-9._-]+)?\b",
        r"\b[A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*)?\b",
        r"\b(?:main|master|trunk|develop|dev|npm|pnpm|yarn|bun)\b",
    ]
    candidates: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            value = match.group(0).strip()
            if value and value not in candidates:
                candidates.append(value)
    return candidates


def normalize_value(value: Any, answer_type: str) -> str | float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if answer_type in {"number", "currency", "percentage"}:
        return parse_number(raw)
    if answer_type == "date":
        return normalize_date(raw)
    return normalize_string(raw)


def grade_with_trace(task: Task, truth: str | float, answer: str) -> dict[str, Any]:
    claim = extract_claim(answer, task.answer_type, truth)
    normalized_claim = normalize_value(claim, task.answer_type)
    normalized_truth = normalize_value(truth, task.answer_type)
    trace: dict[str, Any] = {
        "answer_type": task.answer_type,
        "raw_answer": str(answer or ""),
        "raw_claim": claim,
        "raw_truth": truth,
        "normalized_claim": normalized_claim,
        "normalized_truth": normalized_truth,
        "tolerance": None,
        "comparison": "unparseable",
        "matched": False,
    }
    if normalized_claim is None or normalized_truth is None:
        return {
            "passed": False,
            "claim": claim,
            "normalized_claim": normalized_claim,
            "normalized_truth": normalized_truth,
            "trace": trace,
        }
    if isinstance(normalized_claim, (int, float)) and isinstance(normalized_truth, (int, float)):
        tolerance = parse_tolerance(task.tolerance, float(normalized_truth))
        matched = math.isclose(
            float(normalized_claim),
            float(normalized_truth),
            abs_tol=tolerance,
        )
        trace.update(
            {
                "tolerance": tolerance,
                "comparison": "numeric_abs_tolerance",
                "delta": abs(float(normalized_claim) - float(normalized_truth)),
                "matched": matched,
            }
        )
        return {
            "passed": matched,
            "claim": claim,
            "normalized_claim": normalized_claim,
            "normalized_truth": normalized_truth,
            "trace": trace,
        }
    if normalized_truth and task.answer_type in {"string", "enum", "date"}:
        normalized_answer = normalize_string(answer)
        if str(normalized_truth) in normalized_answer:
            trace.update(
                {
                    "raw_claim": str(truth),
                    "normalized_claim": normalized_truth,
                    "comparison": "truth_substring_in_answer",
                    "matched": True,
                }
            )
            return {
                "passed": True,
                "claim": str(truth),
                "normalized_claim": normalized_truth,
                "normalized_truth": normalized_truth,
                "trace": trace,
            }
    matched = normalized_claim == normalized_truth
    trace.update({"comparison": "normalized_exact", "matched": matched})
    return {
        "passed": matched,
        "claim": claim,
        "normalized_claim": normalized_claim,
        "normalized_truth": normalized_truth,
        "trace": trace,
    }


def grade(task: Task, truth: str | float, answer: str) -> tuple[bool, str, str | float | None, str | float | None]:
    result = grade_with_trace(task, truth, answer)
    return (
        bool(result["passed"]),
        str(result["claim"]),
        result["normalized_claim"],
        result["normalized_truth"],
    )


def parse_number(value: str) -> float | None:
    text = str(value).replace(",", "").replace("$", "").strip().lower()
    match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*(k|m|b|t|thousand|million|billion|trillion)?",
        text,
    )
    if not match:
        return None
    number = float(match.group(1))
    suffix = match.group(2)
    if suffix:
        number *= {
            "k": 1e3,
            "thousand": 1e3,
            "m": 1e6,
            "million": 1e6,
            "b": 1e9,
            "billion": 1e9,
            "t": 1e12,
            "trillion": 1e12,
        }[suffix]
    return number


def parse_tolerance(value: str | float, truth: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    if not text or text in {"exact", "$0"}:
        return 0.005
    if "%" in text:
        parsed = parse_number(text)
        return abs(truth) * ((parsed or 0) / 100)
    parsed = parse_number(text)
    return float(parsed or 0)


def normalize_string(value: str) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[\u2013\u2014]", "-", text)
    text = re.sub(r"[^a-z0-9.%$+\-/ ]", "", text)
    return text.strip()


def normalize_date(value: str) -> str:
    text = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return normalize_string(text)
