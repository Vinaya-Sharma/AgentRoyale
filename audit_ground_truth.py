from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
from pathlib import Path

from backend.bright_data import fetch_url_with_fallbacks, result_text
from backend.config import APP_DIR
from backend.evaluator import EXTRACTOR_MODEL, evidence_supported
from backend.extractors import extract_ground_truth
from backend.grader import GROUND_TRUTH_SCHEMA, build_ground_truth_messages, normalize_value
from backend.llm import complete_json
from backend.store import latest_ground_truth_by_task
from backend.task_bank import get_official_task_ids, get_tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Agent Royale ground truth extraction.")
    parser.add_argument("--task-id", default="", help="Optional single task id.")
    parser.add_argument("--domain", default="", help="Optional domain filter.")
    parser.add_argument("--output", default="storage/ground_truth_audit.csv")
    parser.add_argument("--include-excluded", action="store_true", help="Audit quarantined tasks too.")
    parser.add_argument("--timeout-seconds", type=float, default=45.0, help="Per-task audit timeout.")
    parser.add_argument("--trim-failures", action="store_true", help="Write failed audited tasks to excluded_tasks.json.")
    return parser.parse_args()


async def audit_task(task, previous):
    row = {
        "task_id": task.id,
        "domain": task.domain,
        "canonical_url": task.canonical_url,
        "previous_value": previous.value if previous else "",
        "previous_fetched_at": previous.fetched_at if previous else "",
        "audited_value": "",
        "audited_normalized": "",
        "confidence": "",
        "evidence": "",
        "status": "",
        "notes": "",
    }
    try:
        result = await fetch_url_with_fallbacks(task.bd_tool, task.canonical_url)
        text = result_text(result, limit=30000)
        if result.is_error or not text:
            row["status"] = "fetch_failed"
            row["notes"] = result.error or "No readable content"
            return row
        deterministic = extract_ground_truth(task, text)
        if deterministic:
            value = deterministic.value.strip()
            evidence = deterministic.evidence.strip()
            confidence = deterministic.confidence
            notes = deterministic.notes
        elif task.bd_tool.startswith("web_data_"):
            row["status"] = "unsupported"
            row["notes"] = f"No deterministic extractor value for {task.bd_tool}"
            return row
        else:
            payload = await complete_json(
                build_ground_truth_messages(task, text),
                model=EXTRACTOR_MODEL,
                schema_name="ground_truth",
                schema=GROUND_TRUTH_SCHEMA,
            )
            value = str(payload.get("value", "")).strip()
            evidence = str(payload.get("evidence", "")).strip()
            confidence = payload.get("confidence", "")
            notes = str(payload.get("notes", ""))
        normalized = normalize_value(value, task.grading)
        supported = evidence_supported(text, evidence, value)
        previous_normalized = previous.normalized_value if previous else None
        changed = previous is not None and str(normalized) != str(previous_normalized)
        row.update(
            {
                "audited_value": value,
                "audited_normalized": normalized,
                "confidence": confidence,
                "evidence": evidence,
                "status": "changed" if changed else "ok",
                "notes": notes,
            }
        )
        if not supported:
            row["status"] = "unsupported"
            row["notes"] = f"{row['notes']} Evidence/value not visible in fetched page.".strip()
        return row
    except Exception as exc:
        row["status"] = "error"
        row["notes"] = str(exc)
        return row


async def main() -> None:
    logging.getLogger().setLevel(logging.ERROR)
    logging.getLogger("mcp").setLevel(logging.ERROR)
    args = parse_args()
    previous = latest_ground_truth_by_task()
    tasks = get_tasks()
    if not args.include_excluded:
        official = get_official_task_ids()
        tasks = [task for task in tasks if task.id in official]
    if args.task_id:
        tasks = [task for task in tasks if task.id == args.task_id]
    if args.domain:
        tasks = [task for task in tasks if task.domain == args.domain]
    rows = []
    for idx, task in enumerate(tasks, start=1):
        print(f"[{idx}/{len(tasks)}] {task.id} {task.question}", flush=True)
        try:
            row = await asyncio.wait_for(
                audit_task(task, previous.get(task.id)),
                timeout=args.timeout_seconds,
            )
        except TimeoutError:
            row = {
                "task_id": task.id,
                "domain": task.domain,
                "canonical_url": task.canonical_url,
                "previous_value": previous.get(task.id).value if previous.get(task.id) else "",
                "previous_fetched_at": previous.get(task.id).fetched_at if previous.get(task.id) else "",
                "audited_value": "",
                "audited_normalized": "",
                "confidence": "",
                "evidence": "",
                "status": "timeout",
                "notes": f"Timed out after {args.timeout_seconds:.0f}s.",
            }
        print(f"  {row['status']}: {row['previous_value']} -> {row['audited_value']} ({row['confidence']})", flush=True)
        rows.append(row)
    output = Path(args.output)
    if not output.is_absolute():
        output = APP_DIR / output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {output}", flush=True)
    if args.trim_failures:
        failed = {
            row["task_id"]: f"Ground-truth audit {row['status']}: {row['notes']}"
            for row in rows
            if row["status"] not in {"ok", "changed"}
        }
        excluded_path = APP_DIR / "data" / "excluded_tasks.json"
        existing = {}
        if excluded_path.exists():
            existing = json.loads(excluded_path.read_text(encoding="utf-8"))
        existing.update(failed)
        excluded_path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Trimmed {len(failed)} failed tasks into {excluded_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
