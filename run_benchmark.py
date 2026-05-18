from __future__ import annotations

import argparse
import asyncio

from backend.batch import run_batch
from backend.config import get_settings
from backend.store import build_leaderboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Agent Royale over the task bank.")
    parser.add_argument("--models", default="", help="Comma-separated OpenRouter model IDs.")
    parser.add_argument("--domain", default="", help="Optional domain filter, e.g. prices.")
    parser.add_argument("--limit", type=int, default=0, help="Optional task limit for smoke tests.")
    parser.add_argument("--start-at", default="", help="Optional task id to resume from.")
    parser.add_argument("--task-ids", default="", help="Comma-separated task IDs to run.")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--no-refresh-ground-truth", action="store_true")
    parser.add_argument("--include-excluded", action="store_true", help="Also run quarantined tasks.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    settings = get_settings()
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    if not models:
        models = list(settings.default_models)

    print("Agent Royale batch run")
    print(f"Models: {', '.join(models)}")
    if args.domain:
        print(f"Domain: {args.domain}")
    if args.limit:
        print(f"Limit: {args.limit}")
    task_ids = [item.strip() for item in args.task_ids.split(",") if item.strip()]
    if task_ids:
        print(f"Task IDs: {', '.join(task_ids)}")
    if not args.include_excluded:
        print("Task set: verified official tasks only")
    print(f"Repetitions: {args.repetitions}")

    async for progress in run_batch(
        models=models,
        repetitions=args.repetitions,
        domain=args.domain or None,
        limit=args.limit or None,
        start_at=args.start_at or None,
        task_ids=task_ids or None,
        refresh_ground_truth=not args.no_refresh_ground_truth,
        include_excluded=args.include_excluded,
    ):
        prefix = f"[{progress.task_index}/{progress.task_total}] {progress.task_id} rep {progress.repetition}"
        if progress.error:
            print(f"{prefix} ERROR {progress.error}")
            continue
        passes = sum(1 for run in progress.runs if run.passed)
        print(f"{prefix} {passes}/{len(progress.runs)} passed")

    print("\nLeaderboard")
    for idx, row in enumerate(build_leaderboard(), start=1):
        print(
            f"{idx}. {row.model} accuracy={row.live_exact_accuracy:.1%} "
            f"vrr={row.verified_retrieval_rate:.1%} runs={row.scored_runs} "
            f"cost=${row.avg_cost_usd:.4f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
