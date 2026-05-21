from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.config import APP_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed ground_truth.jsonl from an audit CSV.")
    parser.add_argument("audit_csv")
    parser.add_argument("--replace-existing", action="store_true")
    return parser.parse_args()


def coerce_normalized(value: str) -> str | float:
    try:
        return float(value)
    except ValueError:
        return value


def suspicious_artifact(row: dict[str, str]) -> bool:
    return (
        "finance.yahoo.com/quote/" in row.get("canonical_url", "")
        and row.get("audited_value", "").strip() == "$1.00"
    )


def main() -> None:
    args = parse_args()
    audit_path = Path(args.audit_csv)
    if not audit_path.is_absolute():
        audit_path = APP_DIR / audit_path
    output_path = APP_DIR / "storage" / "ground_truth.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    if output_path.exists():
        existing = [
            json.loads(line)
            for line in output_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    existing_ids = {row["task_id"] for row in existing}

    now = datetime.now(timezone.utc).isoformat()
    seeded: list[dict] = []
    with audit_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["status"] not in {"ok", "changed"}:
                continue
            if suspicious_artifact(row):
                continue
            if row["task_id"] in existing_ids and not args.replace_existing:
                continue
            seeded.append(
                {
                    "task_id": row["task_id"],
                    "value": row["audited_value"],
                    "normalized_value": coerce_normalized(row["audited_normalized"]),
                    "source_url": row["canonical_url"],
                    "fetched_at": now,
                    "extraction_confidence": row["confidence"] or "high",
                    "notes": f"Seeded from Bright Data audit. {row['notes']}".strip(),
                    "raw_preview": row["evidence"][:1200],
                }
            )

    if args.replace_existing:
        seeded_ids = {row["task_id"] for row in seeded}
        existing = [row for row in existing if row["task_id"] not in seeded_ids]

    with output_path.open("w", encoding="utf-8") as handle:
        for row in [*existing, *seeded]:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"seeded {len(seeded)} rows into {output_path}")
    for row in seeded:
        print(f"{row['task_id']}: {row['value']}")


if __name__ == "__main__":
    main()
