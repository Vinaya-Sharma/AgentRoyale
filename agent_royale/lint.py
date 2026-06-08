from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from agent_royale.schema import Task, flatten_tasks, load_task_packs


@dataclass(frozen=True)
class LintFinding:
    severity: str
    task_id: str
    message: str
    hint: str = ""


def lint_task_paths(paths: list[Path]) -> list[LintFinding]:
    packs = load_task_packs(paths)
    tasks = flatten_tasks(packs)
    findings: list[LintFinding] = []
    seen_ids: dict[str, str] = {}
    seen_questions: dict[str, str] = {}
    for task in tasks:
        if task.id in seen_ids:
            findings.append(
                LintFinding(
                    "error",
                    task.id,
                    f"Task id duplicates `{seen_ids[task.id]}`.",
                    "Task IDs must be unique across packs that will be run or compared together.",
                )
            )
        else:
            seen_ids[task.id] = task.id
        findings.extend(lint_task(task))
        question_key = normalize_text(task.question)
        if question_key in seen_questions:
            findings.append(
                LintFinding(
                    "warning",
                    task.id,
                    f"Question duplicates `{seen_questions[question_key]}`.",
                    "Duplicate questions make regression reports harder to interpret.",
                )
            )
        else:
            seen_questions[question_key] = task.id
    return findings


def lint_task(task: Task) -> list[LintFinding]:
    findings: list[LintFinding] = []
    ground_truth = task.ground_truth
    if task.stability == "volatile" and task.ci_safe:
        findings.append(
            LintFinding(
                "error",
                task.id,
                "Volatile task is marked ci_safe=true.",
                "Set ci_safe: false for values that can change without a code change.",
            )
        )
    if task.ci_safe and ground_truth.method in {"http_regex", "bright_data"} and task.stability != "stable":
        findings.append(
            LintFinding(
                "warning",
                task.id,
                "CI-safe task uses a live page oracle without stability=stable.",
                "Use CI gates for stable backing sources, or set ci_safe: false and run this pack on demand.",
            )
        )
    if task.ci_safe and not task.task_pack_version:
        findings.append(
            LintFinding(
                "warning",
                task.id,
                "CI-safe task pack does not declare a version.",
                "Add a top-level version so old reports can be tied back to a specific task-pack revision.",
            )
        )
    if task.source_policy.match == "contains" and task.ci_safe:
        findings.append(
            LintFinding(
                "warning",
                task.id,
                "CI-safe task uses permissive source_policy.match=contains.",
                "Use same_path, exact_url, or allowed_sources when citation source precision matters.",
            )
        )
    if ground_truth.method in {"http_json", "http_regex", "bright_data"} and not ground_truth.source_url:
        findings.append(
            LintFinding(
                "warning",
                task.id,
                "Ground truth does not set source_url.",
                "Set source_url so reports show the provenance users should inspect.",
            )
        )
    if ground_truth.regex:
        findings.extend(lint_regex_task(task))
    if ground_truth.method == "bright_data":
        if ground_truth.tool in {"scrape_as_markdown", "search_engine"} and not ground_truth.regex and not ground_truth.field:
            findings.append(
                LintFinding(
                    "error",
                    task.id,
                    "Bright Data page extraction needs a field or regex.",
                    "Use a field for structured tools or a source-specific regex for markdown/page extraction.",
                )
            )
        if ground_truth.tool == "search_engine":
            findings.append(
                LintFinding(
                    "warning",
                    task.id,
                    "Search results are a weak oracle for exact values.",
                    "Prefer a required-source page scrape, structured Bright Data tool, or public source API.",
                )
            )
    if task.answer_type in {"number", "currency", "percentage"} and "current" in normalize_text(task.question):
        if task.stability == "stable":
            findings.append(
                LintFinding(
                    "warning",
                    task.id,
                    "Question asks for a current numeric value but stability is stable.",
                    "Use semi_stable or volatile unless the value is backed by a slow-moving release/API field.",
                )
            )
    if not task.notes and ground_truth.method in {"http_regex", "bright_data"}:
        findings.append(
            LintFinding(
                "warning",
                task.id,
                "Live-web oracle task has no notes.",
                "Document the exact field, parser assumption, and known ambiguity risks.",
            )
        )
    if not source_mentioned(task.required_source, task.question):
        findings.append(
            LintFinding(
                "warning",
                task.id,
                "Question may not name the required source clearly.",
                "Source-specific tasks should make the required source obvious to the target agent.",
            )
        )
    return findings


def lint_regex_task(task: Task) -> list[LintFinding]:
    findings: list[LintFinding] = []
    regex = task.ground_truth.regex or ""
    if has_broad_numeric_capture(regex) and not task.ground_truth.require_near_text:
        findings.append(
            LintFinding(
                "error",
                task.id,
                "Numeric regex has no require_near_text context.",
                "Add nearby labels such as plan name, billing interval, SKU, unit, or field name.",
            )
        )
    if regex.strip() in {r"([0-9]+)", r"(\d+)", r"\$?\s*([0-9]+(?:\.[0-9]{2})?)"}:
        findings.append(
            LintFinding(
                "error",
                task.id,
                "Regex is too broad for a live-web oracle.",
                "Use a source-specific parser that anchors around the field being tested.",
            )
        )
    if task.answer_type == "currency" and not contains_currency_context(regex, task.ground_truth.require_near_text):
        findings.append(
            LintFinding(
                "warning",
                task.id,
                "Currency task does not include obvious currency or billing context.",
                "Anchor on the currency symbol/code and billing interval when the page contains multiple prices.",
            )
        )
    return findings


def has_broad_numeric_capture(regex: str) -> bool:
    numeric_capture = re.search(r"\((?:\?:)?[^)]*(?:\\d|\[0-9\])[^)]*\)", regex)
    if not numeric_capture:
        return False
    contextual_words = re.findall(r"[A-Za-z]{4,}", regex)
    return len(contextual_words) < 2


def contains_currency_context(regex: str, near_text: list[str]) -> bool:
    haystack = " ".join([regex, *near_text]).lower()
    return any(token in haystack for token in ["$", "usd", "monthly", "annual", "year", "billing"])


def source_mentioned(required_source: str, question: str) -> bool:
    source = normalize_text(required_source)
    text = normalize_text(question)
    parsed = urlparse(required_source if "://" in required_source else f"https://{required_source}")
    host = parsed.netloc or source.split("/")[0]
    parts = [part for part in re.split(r"[^a-z0-9]+", host) if len(part) >= 4]
    compact_text = re.sub(r"[^a-z0-9]+", "", text)
    aliases = []
    if "npmjs" in host:
        aliases.append("npm")
    return source in text or any(part in compact_text for part in [*parts, *aliases])


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def render_lint_findings(findings: list[LintFinding]) -> str:
    if not findings:
        return "OK task-pack lint found no issues."
    lines = ["Task-pack lint findings"]
    for finding in findings:
        lines.append(f"{finding.severity.upper()} {finding.task_id}: {finding.message}")
        if finding.hint:
            lines.append(f"  hint: {finding.hint}")
    error_count = sum(1 for finding in findings if finding.severity == "error")
    warning_count = sum(1 for finding in findings if finding.severity == "warning")
    lines.append("")
    lines.append(f"Errors: {error_count}; warnings: {warning_count}")
    return "\n".join(lines)
