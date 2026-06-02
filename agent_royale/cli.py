from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

import yaml

from agent_royale import __version__
from agent_royale.report import load_records, write_html_report
from agent_royale.runner import run_tasks
from agent_royale.schema import flatten_tasks, load_task_packs, validation_errors


EXAMPLE_TASK_PACK = {
    "name": "agent-royale-example",
    "description": "Tiny static task pack for testing the Agent Royale runner.",
    "tasks": [
        {
            "id": "example_static_price",
            "question": "Using the example source, what is the current Pro plan price in USD?",
            "required_source": "example.com/pricing",
            "answer_type": "currency",
            "tolerance": 0,
            "labels": ["example", "pricing"],
            "ground_truth": {
                "method": "static",
                "value": "$19.00",
                "source_url": "example.com/pricing",
            },
        }
    ],
}


def task_pack_template(slug: str) -> dict:
    return {
        "name": slug,
        "description": f"Starter task pack for {slug.replace('-', ' ')} retrieval tests.",
        "tasks": [
            {
                "id": f"{slug.replace('-', '_')}_example_value",
                "question": "Using the example source, what is the current Pro plan price in USD?",
                "required_source": "example.com/pricing",
                "answer_type": "currency",
                "tolerance": 0,
                "labels": [slug, "example", "pricing"],
                "notes": (
                    "Replace this static smoke task with a source-specific oracle. "
                    "Good task packs use public APIs when they expose the exact field, "
                    "and maintained page extraction when the source is only available on the web."
                ),
                "ground_truth": {
                    "method": "static",
                    "value": "$19.00",
                    "source_url": "example.com/pricing",
                },
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        return cmd_init(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "run":
        return asyncio.run(cmd_run(args))
    if args.command == "report":
        return cmd_report(args)
    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-royale", description="Eval AI search stacks against live-web ground truth.")
    parser.add_argument("--version", action="version", version=f"agent-royale {__version__}")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Create a starter task pack.")
    init.add_argument(
        "target",
        nargs="?",
        default="agent-royale-tasks.yaml",
        help="Output YAML path, or 'task-pack' to create task-packs/<name>/example.yaml.",
    )
    init.add_argument("name", nargs="?", default="", help="Task-pack name when using 'init task-pack <name>'.")
    init.add_argument("--root", default=".", help="Repo root for 'init task-pack <name>'.")

    validate = sub.add_parser("validate", help="Validate one or more task packs.")
    validate.add_argument("paths", nargs="+")

    run = sub.add_parser("run", help="Run tasks against a target stack.")
    run.add_argument("paths", nargs="+", help="Task YAML/JSON files or directories.")
    run.add_argument("--target", required=True, help="http(s) endpoint, openrouter:<model>, or path.py:function.")
    run.add_argument("--output", default="runs/agent-royale-runs.jsonl")
    run.add_argument("--report", default="")
    run.add_argument("--runs-per-task", type=int, default=1)
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument("--timeout", type=float, default=120)
    run.add_argument("--fail-under-exact", type=float, default=None)

    report = sub.add_parser("report", help="Generate an HTML report from JSONL runs.")
    report.add_argument("input", help="Run JSONL file.")
    report.add_argument("--output", default="reports/agent-royale-report.html")
    return parser


def cmd_init(args: argparse.Namespace) -> int:
    if args.target == "task-pack":
        if not args.name:
            print("Usage: agent-royale init task-pack <domain-name>")
            return 1
        slug = slugify(args.name)
        path = Path(args.root) / "task-packs" / slug / "example.yaml"
        task_pack = task_pack_template(slug)
    else:
        if args.name:
            print("Usage: agent-royale init [path] or agent-royale init task-pack <domain-name>")
            return 1
        path = Path(args.target)
        task_pack = EXAMPLE_TASK_PACK
    if path.exists():
        print(f"Refusing to overwrite existing file: {path}")
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(task_pack, sort_keys=False), encoding="utf-8")
    print(f"Created {path}")
    print("Next: agent-royale validate", path)
    return 0


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "custom"


def cmd_validate(args: argparse.Namespace) -> int:
    ok = True
    for raw in args.paths:
        path = Path(raw)
        paths = [path]
        if path.is_dir():
            paths = sorted(item for item in path.rglob("*") if item.suffix.lower() in {".yaml", ".yml", ".json"})
        for item in paths:
            errors = validation_errors(item)
            if errors:
                ok = False
                print(f"FAIL {item}")
                for error in errors:
                    print(f"  - {error}")
            else:
                pack = load_task_packs([item])[0]
                print(f"OK {item} ({len(pack.tasks)} task{'s' if len(pack.tasks) != 1 else ''})")
    return 0 if ok else 1


async def cmd_run(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists():
        output.unlink()
    packs = load_task_packs([Path(item) for item in args.paths])
    tasks = flatten_tasks(packs)
    print(f"Running {len(tasks)} task(s) against {args.target}")
    records = await run_tasks(
        tasks,
        target=args.target,
        output=output,
        runs_per_task=args.runs_per_task,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout,
    )
    passed = sum(1 for item in records if item.passed)
    accuracy = passed / len(records) if records else 0
    print(f"\nExact accuracy: {accuracy:.1%} ({passed}/{len(records)})")
    print(f"Runs: {output}")
    if args.report:
        report_path = Path(args.report)
        write_html_report(records, report_path)
        print(f"Report: {report_path}")
    if args.fail_under_exact is not None and accuracy < args.fail_under_exact:
        print(f"Failed threshold: {accuracy:.1%} < {args.fail_under_exact:.1%}")
        return 2
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    records = load_records(Path(args.input))
    output = Path(args.output)
    write_html_report(records, output)
    print(f"Report: {output}")
    return 0
