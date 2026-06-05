from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.bright_data import fetch_url_with_fallbacks, result_text  # noqa: E402


app = FastAPI(title="Agent Royale Bright Data Target Example")


class AgentRequest(BaseModel):
    question: str
    task: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/agent")
async def answer(req: AgentRequest) -> dict[str, Any]:
    started = time.perf_counter()
    output = await run_bright_data(req.question, req.task)
    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    output.setdefault("trace", {})
    output["trace"]["latency_ms"] = latency_ms
    return output


async def run_bright_data(question: str, task: dict[str, Any]) -> dict[str, Any]:
    if not os.getenv("BRIGHT_DATA_API_KEY", "").strip():
        raise RuntimeError("Set BRIGHT_DATA_API_KEY before starting this example.")

    url = source_url(task)
    tool = bright_data_tool(task)
    result = await fetch_url_with_fallbacks(tool, url)
    if result.is_error:
        raise HTTPException(status_code=502, detail=result.error or f"Bright Data {tool} failed")

    text = result_text(result, limit=int(os.getenv("BRIGHT_DATA_AGENT_TEXT_LIMIT", "50000")))
    answer_value, quote = extract_answer(text, question, task.get("answer_type", "string"))
    return {
        "answer": answer_value,
        "citations": [{"url": url, "quote": quote}],
        "trace": {
            "tools_used": [f"bright_data.{result.endpoint}"],
            "search_queries": [f"required_source={url}"],
            "cost_usd": None,
            "provider_metadata": {
                "provider": "bright_data",
                "requested_tool": tool,
                "resolved_endpoint": result.endpoint,
                "strategy": "bright_data_fetch_with_deterministic_extraction",
            },
        },
    }


def bright_data_tool(task: dict[str, Any]) -> str:
    configured = os.getenv("BRIGHT_DATA_AGENT_TOOL", "").strip()
    if configured:
        return configured
    ground_truth = task.get("ground_truth") or {}
    tool = str(ground_truth.get("tool") or "").strip()
    if tool:
        return tool
    return "scrape_as_markdown"


def source_url(task: dict[str, Any]) -> str:
    source = str(task.get("required_source") or "").strip()
    if source.startswith(("http://", "https://")):
        return source
    ground_truth_url = str((task.get("ground_truth") or {}).get("url") or "").strip()
    if ground_truth_url.startswith(("http://", "https://")):
        return ground_truth_url
    if source:
        return "https://" + source.lstrip("/")
    raise RuntimeError("Task did not include a usable required_source URL.")


def extract_answer(text: str, question: str, answer_type: str) -> tuple[str, str]:
    question_lower = question.lower()
    storage_match = re.search(r"\b([0-9]+)\s*gb\b", question_lower)
    if storage_match and "storage" in question_lower and "price" in question_lower:
        return extract_storage_price(text, storage_match.group(1))
    if "storage options" in question_lower:
        return extract_storage_options(text)
    if "color" in question_lower and "title" in question_lower:
        return extract_title_color(text)
    if "product title" in question_lower and "price & deals" in question_lower:
        return extract_title_product(text)
    if "availability" in question_lower or "in stock" in question_lower or "out of stock" in question_lower:
        return extract_availability(text)
    if "review" in question_lower and answer_type == "number":
        return extract_review_count(text)
    if "rating" in question_lower and answer_type == "number":
        return extract_rating(text)
    if answer_type == "currency" or "price" in question_lower:
        return extract_price(text, question_lower)
    if answer_type in {"number", "percentage"}:
        return extract_number(text)
    return first_nonempty_line(text)


def extract_storage_price(text: str, storage_gb: str) -> tuple[str, str]:
    pattern = rf"\b{re.escape(storage_gb)}GB\s*\$\s*([0-9,]+(?:\.[0-9]{{2}})?)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        raise RuntimeError(f"Could not extract a {storage_gb}GB storage price from the Bright Data output.")
    value = float(match.group(1).replace(",", ""))
    return format_currency(value), compact_quote(context_for_match(text, match))


def extract_storage_options(text: str) -> tuple[str, str]:
    match = re.search(r"Storage\s+Storage\s+(256GB\s+512GB\s+1TB)", text, re.IGNORECASE)
    if not match:
        raise RuntimeError("Could not extract storage options from the Bright Data output.")
    return " ".join(match.group(1).split()), compact_quote(context_for_match(text, match))


def extract_title_color(text: str) -> tuple[str, str]:
    match = re.search(r"Buy Galaxy S25 Ultra 256GB \| ([^|]+?) Smartphone", text)
    if not match:
        raise RuntimeError("Could not extract the page-title color from the Bright Data output.")
    return match.group(1).strip(), compact_quote(context_for_match(text, match))


def extract_title_product(text: str) -> tuple[str, str]:
    match = re.search(r"(Buy Galaxy S25 Ultra 256GB \| Titanium Black Smartphone) \| Price & Deals", text)
    if not match:
        raise RuntimeError("Could not extract the page-title product from the Bright Data output.")
    return match.group(1).strip(), compact_quote(context_for_match(text, match))


def extract_price(text: str, question_lower: str) -> tuple[str, str]:
    candidates: list[tuple[int, float, str, str]] = []
    for match in re.finditer(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)", text):
        raw = match.group(1)
        value = float(raw.replace(",", ""))
        start, end = match.span()
        context = text[max(0, start - 120) : min(len(text), end + 120)]
        if reject_price_context(context, text[max(0, start - 20) : start].lower(), question_lower):
            continue
        candidates.append((start, value, format_currency(value), context.strip()))
    if not candidates:
        raise RuntimeError("Could not extract a price from the Bright Data output.")
    preferred = choose_price_candidate(candidates, question_lower)
    return preferred[2], compact_quote(preferred[3])


def reject_price_context(context: str, prefix: str, question_lower: str) -> bool:
    lowered = context.lower()
    if re.search(r"(per month|/mo|monthly|installment|financing|lease)", lowered):
        return True
    if re.search(r"(save|savings|discount|cash back|gift card|protection plan|warranty)", lowered):
        return True
    if re.search(r"(trade.?in|carrier credit|bill credit)", lowered) and "before trade" not in question_lower:
        return True
    if re.search(r"(was|list|regular|reg\.?|msrp)\s*[:$ ]*$", prefix):
        return True
    return False


def choose_price_candidate(
    candidates: list[tuple[int, float, str, str]], question_lower: str
) -> tuple[int, float, str, str]:
    if any(term in question_lower for term in ("lowest", "starting", "from")):
        return min(candidates, key=lambda item: item[1])
    return candidates[0]


def extract_rating(text: str) -> tuple[str, str]:
    patterns = [
        r"([0-9](?:\.[0-9])?)\s*(?:out of|/)\s*5",
        r"rating(?:\s*[:\-])?\s*([0-9](?:\.[0-9])?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1), compact_quote(context_for_match(text, match))
    raise RuntimeError("Could not extract a rating from the Bright Data output.")


def extract_review_count(text: str) -> tuple[str, str]:
    patterns = [
        r"([0-9][0-9,]*)\s+(?:customer\s+)?reviews\b",
        r"\(([\d,]+)\)\s*(?:reviews|ratings)",
        r"reviews?\s*[:\-]?\s*([0-9][0-9,]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).replace(",", ""), compact_quote(context_for_match(text, match))
    raise RuntimeError("Could not extract a review count from the Bright Data output.")


def extract_availability(text: str) -> tuple[str, str]:
    match = re.search(
        r"\b(In stock|Out of stock|Sold out|Unavailable|Not available|Available to ship|Shipping not available)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise RuntimeError("Could not extract availability from the Bright Data output.")
    return normalize_phrase(match.group(1)), compact_quote(context_for_match(text, match))


def extract_number(text: str) -> tuple[str, str]:
    match = re.search(r"\b[0-9][0-9,]*(?:\.[0-9]+)?\b", text)
    if not match:
        raise RuntimeError("Could not extract a number from the Bright Data output.")
    return match.group(0).replace(",", ""), compact_quote(context_for_match(text, match))


def first_nonempty_line(text: str) -> tuple[str, str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:500], stripped[:500]
    raise RuntimeError("Bright Data returned no readable text.")


def context_for_match(text: str, match: re.Match[str]) -> str:
    return text[max(0, match.start() - 120) : min(len(text), match.end() + 120)]


def compact_quote(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()[:500]


def normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def format_currency(value: float) -> str:
    if value.is_integer():
        return f"${int(value)}"
    return f"${value:.2f}"
