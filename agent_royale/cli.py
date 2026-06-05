from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml

from agent_royale import __version__
from agent_royale.ground_truth import fetch_ground_truth, fetch_ground_truth_snapshot
from agent_royale.report import load_records, write_html_report
from agent_royale.runner import run_tasks
from agent_royale.schema import flatten_tasks, load_task_packs, validation_errors
from agent_royale.targets import call_target


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


def task_pack_template(slug: str, ground_truth: str = "static") -> dict:
    if ground_truth == "bright-data-rapid":
        return bright_data_rapid_task_pack_template(slug)
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


def bright_data_rapid_task_pack_template(slug: str) -> dict:
    return {
        "name": slug,
        "description": (
            f"Starter Bright Data Rapid-mode task pack for {slug.replace('-', ' ')} retrieval tests."
        ),
        "tasks": [
            {
                "id": f"{slug.replace('-', '_')}_example_page_value",
                "question": "Using the example pricing page, what is the current Pro plan price in USD?",
                "required_source": "example.com/pricing",
                "answer_type": "currency",
                "tolerance": 0,
                "labels": [slug, "bright_data", "rapid_mode", "pricing"],
                "notes": (
                    "Replace the URL and regex with a source-specific live page. "
                    "Rapid-mode Bright Data tasks should use search_engine or scrape_as_markdown; "
                    "use structured web_data_* tools only when your MCP configuration enables them."
                ),
                "ground_truth": {
                    "method": "bright_data",
                    "tool": "scrape_as_markdown",
                    "url": "https://example.com/pricing",
                    "regex": "Pro[\\s\\S]{0,800}?\\$\\s*([0-9]+(?:\\.[0-9]{2})?)",
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
    if args.command == "doctor":
        return asyncio.run(cmd_doctor(args))
    if args.command == "audit":
        return asyncio.run(cmd_audit(args))
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
    init.add_argument(
        "--ground-truth",
        choices=["static", "bright-data-rapid"],
        default="static",
        help="Starter oracle style for newly created task packs.",
    )

    validate = sub.add_parser("validate", help="Validate one or more task packs.")
    validate.add_argument("paths", nargs="+")

    doctor = sub.add_parser("doctor", help="Check environment, task-pack readiness, and target contract.")
    doctor.add_argument("paths", nargs="*", help="Optional task YAML/JSON files or directories.")
    doctor.add_argument("--target", default="", help="Optional target to probe with the first loaded task.")
    doctor.add_argument(
        "--check-ground-truth",
        action="store_true",
        help="Fetch each loaded task oracle to catch parser/API failures before a full run.",
    )
    doctor.add_argument("--timeout", type=float, default=30)

    audit = sub.add_parser("audit", help="Audit task-pack oracle health without running a target.")
    audit.add_argument("paths", nargs="+", help="Task YAML/JSON files or directories.")
    audit.add_argument("--timeout", type=float, default=30)
    audit.add_argument("--jsonl", default="", help="Optional JSONL output path for oracle snapshots.")

    run = sub.add_parser("run", help="Run tasks against a target stack.")
    run.add_argument("paths", nargs="+", help="Task YAML/JSON files or directories.")
    run.add_argument("--target", required=True, help="http(s) endpoint, openrouter:<model>, or path.py:function.")
    run.add_argument("--output", default="runs/agent-royale-runs.jsonl")
    run.add_argument("--report", default="")
    run.add_argument("--runs-per-task", type=int, default=1)
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument("--timeout", type=float, default=120)
    run.add_argument("--fail-under-exact", type=float, default=None)
    run.add_argument("--ci", action="store_true", help="Run only tasks marked ci_safe=true.")

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
        task_pack = task_pack_template(slug, args.ground_truth)
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
    for item in expand_task_files(args.paths):
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


def expand_task_files(raw_paths: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in raw_paths:
        path = Path(raw)
        if path.is_dir():
            paths.extend(
                sorted(item for item in path.rglob("*") if item.suffix.lower() in {".yaml", ".yml", ".json"})
            )
        else:
            paths.append(path)
    return paths


async def cmd_doctor(args: argparse.Namespace) -> int:
    ok = True
    print(f"Agent Royale {__version__}")

    try:
        from backend.config import get_settings

        settings = get_settings()
        openrouter_key = bool(settings.openrouter_api_key)
        bright_data_key = bool(settings.bright_data_api_key)
        openrouter_base_url = settings.openrouter_base_url
        bright_data_url = settings.bright_data_mcp_url_with_token
        bright_data_mode = bright_data_mode_label(bright_data_url)
    except Exception:
        openrouter_key = bool(os.getenv("OPENROUTER_API_KEY"))
        bright_data_key = bool(os.getenv("BRIGHT_DATA_API_KEY"))
        openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        bright_data_url = os.getenv("BRIGHT_DATA_MCP_URL", "https://mcp.brightdata.com/mcp")
        bright_data_mode = bright_data_mode_label(bright_data_url)

    print("\nEnvironment")
    print(check_line("OPENROUTER_API_KEY", openrouter_key, "set", "missing"))
    print(f"  OpenRouter base URL: {redact_url(openrouter_base_url)}")
    print(check_line("BRIGHT_DATA_API_KEY", bright_data_key, "set", "missing"))
    print(f"  Bright Data MCP URL: {redact_url(bright_data_url)}")
    print(f"  Bright Data MCP mode: {bright_data_mode}")

    tasks = []
    if args.paths:
        print("\nTask packs")
        task_files = expand_task_files(args.paths)
        for item in task_files:
            errors = validation_errors(item)
            if errors:
                ok = False
                print(f"FAIL {item}")
                for error in errors:
                    print(f"  - {error}")
            else:
                pack = load_task_packs([item])[0]
                print(f"OK {item} ({len(pack.tasks)} task{'s' if len(pack.tasks) != 1 else ''})")
        if ok:
            packs = load_task_packs(task_files)
            tasks = flatten_tasks(packs)
            print_task_summary(tasks)
            if any(task.ground_truth.method == "bright_data" for task in tasks) and not bright_data_key:
                ok = False
                print("FAIL Bright Data task packs require BRIGHT_DATA_API_KEY.")
            pro_tools = [
                task.ground_truth.tool
                for task in tasks
                if task.ground_truth.tool and task.ground_truth.tool.startswith("web_data_")
            ]
            if pro_tools and bright_data_mode.startswith("Rapid"):
                ok = False
                print("FAIL Structured Bright Data tools require Pro mode or explicit tool/group configuration.")
    else:
        print("\nTask packs")
        print("No task packs supplied. Pass paths to check pack readiness.")

    if args.target:
        print("\nTarget")
        if args.target.startswith("openrouter:") and not openrouter_key:
            ok = False
            print("FAIL OpenRouter targets require OPENROUTER_API_KEY.")
        elif not tasks:
            print("SKIP target probe; pass a task pack path so doctor has a representative task.")
        else:
            try:
                response, latency_ms = await call_target(args.target, tasks[0], timeout_seconds=args.timeout)
                if response.answer.strip():
                    citation_count = len(response.citations)
                    print(
                        f"OK target returned an answer for {tasks[0].id} "
                        f"({latency_ms:.0f} ms, {citation_count} citation{'s' if citation_count != 1 else ''})"
                    )
                else:
                    ok = False
                    print(f"FAIL target returned an empty answer for {tasks[0].id}.")
            except Exception as exc:
                ok = False
                print(f"FAIL target probe failed: {exc}")

    if args.check_ground_truth and tasks:
        print("\nGround truth")
        for task in tasks:
            try:
                snapshot = await fetch_ground_truth_snapshot(task, timeout_seconds=args.timeout)
                if snapshot.status == "verified":
                    print(f"OK {task.id}: {snapshot.value!r} from {snapshot.source_url}")
                else:
                    ok = False
                    print(f"FAIL {task.id}: {snapshot.status}: {snapshot.error}")
            except Exception as exc:
                ok = False
                print(f"FAIL {task.id}: {exc}")
    elif args.check_ground_truth:
        print("\nGround truth")
        print("SKIP ground-truth checks; pass at least one task pack path.")

    print(f"\n{'OK' if ok else 'FAIL'} doctor checks complete.")
    return 0 if ok else 1


async def cmd_audit(args: argparse.Namespace) -> int:
    packs = load_task_packs([Path(item) for item in args.paths])
    tasks = flatten_tasks(packs)
    snapshots = []
    print(f"Auditing {len(tasks)} task oracle{'s' if len(tasks) != 1 else ''}")
    for task in tasks:
        snapshot = await fetch_ground_truth_snapshot(task, timeout_seconds=args.timeout)
        snapshots.append(snapshot)
        label = "OK" if snapshot.status == "verified" else "WARN"
        detail = snapshot.value if snapshot.status == "verified" else snapshot.error
        print(f"{label} {task.id}: {snapshot.status} {detail!r}")
        if snapshot.status != "verified" and snapshot.ambiguity_flags:
            print(f"  flags: {', '.join(snapshot.ambiguity_flags)}")
    counts = Counter(snapshot.status for snapshot in snapshots)
    print("\nOracle audit complete")
    for status, count in sorted(counts.items()):
        print(f"{status}: {count}")
    verified = counts.get("verified", 0)
    print(f"Scoreable: {verified}/{len(snapshots)}")
    if args.jsonl:
        output = Path(args.jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for snapshot in snapshots:
                handle.write(json.dumps(snapshot.model_dump(), ensure_ascii=True) + "\n")
        print(f"Snapshots: {output}")
    return 0 if verified == len(snapshots) else 1


def check_line(name: str, ok: bool, ok_text: str, missing_text: str) -> str:
    return f"{'OK' if ok else 'WARN'} {name}: {ok_text if ok else missing_text}"


def bright_data_mode_label(url: str) -> str:
    query = dict(parse_qsl(urlparse(url).query, keep_blank_values=True))
    if query.get("tools"):
        return f"tools={query['tools']}"
    if query.get("groups"):
        return f"groups={query['groups']}"
    if query.get("pro") in {"1", "true"}:
        return "Pro"
    return "Rapid (free-tier friendly)"


def redact_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.query:
        return value
    redacted = []
    for key, raw_value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in {"token", "api_key", "apikey", "key"}:
            redacted.append((key, "redacted"))
        else:
            redacted.append((key, raw_value))
    return urlunparse(parsed._replace(query=urlencode(redacted, safe=",")))


def print_task_summary(tasks: list) -> None:
    method_counts = Counter(task.ground_truth.method for task in tasks)
    answer_counts = Counter(task.answer_type for task in tasks)
    print(f"Tasks: {len(tasks)}")
    print("Ground truth: " + ", ".join(f"{name}={count}" for name, count in sorted(method_counts.items())))
    print("Answer types: " + ", ".join(f"{name}={count}" for name, count in sorted(answer_counts.items())))


async def cmd_run(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists():
        output.unlink()
    packs = load_task_packs([Path(item) for item in args.paths])
    tasks = flatten_tasks(packs)
    if args.ci:
        skipped = [task for task in tasks if not task.ci_safe]
        tasks = [task for task in tasks if task.ci_safe]
        if skipped:
            print(f"Skipping {len(skipped)} non-CI-safe task{'s' if len(skipped) != 1 else ''}.")
    print(f"Running {len(tasks)} task(s) against {args.target}")
    records = await run_tasks(
        tasks,
        target=args.target,
        output=output,
        runs_per_task=args.runs_per_task,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout,
    )
    scoreable = [item for item in records if item.scoreable]
    passed = sum(1 for item in scoreable if item.passed)
    accuracy = passed / len(scoreable) if scoreable else 0
    skipped = len(records) - len(scoreable)
    print(f"\nExact accuracy: {accuracy:.1%} ({passed}/{len(scoreable)} scoreable)")
    if skipped:
        print(f"Skipped oracle issues: {skipped}")
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
