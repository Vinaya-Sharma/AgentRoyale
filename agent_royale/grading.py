from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from agent_royale.schema import Task


def extract_claim(answer: str, answer_type: str) -> str:
    text = str(answer or "").strip()
    if not text:
        return ""
    if answer_type == "currency":
        match = re.search(r"\$?\s*-?\d[\d,]*(?:\.\d+)?", text)
        return match.group(0).strip() if match else text
    if answer_type in {"number", "percentage"}:
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?\s*(?:%|k|m|b|t|thousand|million|billion|trillion)?", text, re.I)
        return match.group(0).strip() if match else text
    if answer_type == "date":
        match = re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b[A-Z][a-z]+ \d{1,2}, \d{4}\b", text)
        return match.group(0).strip() if match else text
    return text.split("\n", 1)[0].strip()


def normalize_value(value: Any, answer_type: str) -> str | float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if answer_type in {"number", "currency", "percentage"}:
        return parse_number(raw)
    if answer_type == "date":
        return normalize_date(raw)
    return normalize_string(raw)


def grade(task: Task, truth: str | float, answer: str) -> tuple[bool, str, str | float | None, str | float | None]:
    claim = extract_claim(answer, task.answer_type)
    normalized_claim = normalize_value(claim, task.answer_type)
    normalized_truth = normalize_value(truth, task.answer_type)
    if normalized_claim is None or normalized_truth is None:
        return False, claim, normalized_claim, normalized_truth
    if isinstance(normalized_claim, (int, float)) and isinstance(normalized_truth, (int, float)):
        tolerance = parse_tolerance(task.tolerance, float(normalized_truth))
        return math.isclose(
            float(normalized_claim),
            float(normalized_truth),
            abs_tol=tolerance,
        ), claim, normalized_claim, normalized_truth
    return normalized_claim == normalized_truth, claim, normalized_claim, normalized_truth


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
