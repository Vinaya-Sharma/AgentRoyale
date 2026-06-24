from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml

from agent_royale import __version__
from agent_royale.compare import compare_run_files, render_markdown_report, render_terminal_summary
from agent_royale.ground_truth import fetch_ground_truth, fetch_ground_truth_snapshot
from agent_royale.lint import lint_task_paths, render_lint_findings
from agent_royale.report import (
    load_records,
    record_source_supported,
    record_verdict,
    write_html_report,
    write_junit_report,
    write_summary_json,
)
from agent_royale.runner import run_tasks
from agent_royale.schema import flatten_tasks, load_task_packs, validation_errors
from agent_royale.targets import call_target


EXAMPLE_TASK_PACK = {
    "name": "agent-royale-example",
    "version": "1.0.0",
    "description": "Tiny static task pack for testing the Agent Royale runner.",
    "tasks": [
        {
            "id": "example_static_price",
            "question": "Using the example source, what is the current Pro plan price in USD?",
            "required_source": "example.com/pricing",
            "answer_type": "currency",
            "tolerance": 0,
            "labels": ["example", "pricing"],
            "source_policy": {"match": "same_path"},
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
        "version": "0.1.0",
        "description": f"Starter task pack for {slug.replace('-', ' ')} retrieval tests.",
        "tasks": [
            {
                "id": f"{slug.replace('-', '_')}_example_value",
                "question": "Using the example source, what is the current Pro plan price in USD?",
                "required_source": "example.com/pricing",
                "answer_type": "currency",
                "tolerance": 0,
                "labels": [slug, "example", "pricing"],
                "source_policy": {"match": "same_path"},
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
        "version": "0.1.0",
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
                "source_policy": {"match": "same_path"},
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
    if args.command == "audit-errors":
        return asyncio.run(cmd_audit_errors(args))
    if args.command == "lint":
        return cmd_lint(args)
    if args.command == "demo":
        return asyncio.run(cmd_demo(args))
    if args.command == "run":
        return asyncio.run(cmd_run(args))
    if args.command == "sweep":
        return asyncio.run(cmd_sweep(args))
    if args.command == "compare":
        return cmd_compare(args)
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
    audit.add_argument("--only", default="", help="Comma-separated task IDs to audit.")

    audit_errors = sub.add_parser(
        "audit-errors",
        help="Audit task oracle failures and export a salvage/debug report.",
    )
    audit_errors.add_argument("paths", nargs="+", help="Task YAML/JSON files or directories.")
    audit_errors.add_argument("--timeout", type=float, default=30)
    audit_errors.add_argument("--only", default="", help="Comma-separated task IDs to audit.")
    audit_errors.add_argument("--output", default="reports/oracle-error-audit.md", help="Markdown output path.")
    audit_errors.add_argument("--json", default="", help="Optional JSON output path.")
    audit_errors.add_argument("--csv", default="", help="Optional CSV output path.")
    audit_errors.add_argument("--include-ok", action="store_true", help="Include verified tasks in the export.")

    lint = sub.add_parser("lint", help="Check task packs for fragile oracle and CI patterns.")
    lint.add_argument("paths", nargs="+", help="Task YAML/JSON files or directories.")
    lint.add_argument("--strict", action="store_true", help="Treat warnings as failures.")

    demo = sub.add_parser("demo", help="Run the offline failure demo and generate reports.")
    demo.add_argument("--output-dir", default="reports/demo", help="Directory for demo outputs.")
    demo.add_argument("--target", default="examples/flaky_agent.py:answer", help="Demo target to evaluate.")

    run = sub.add_parser("run", help="Run tasks against a target stack.")
    run.add_argument("paths", nargs="+", help="Task YAML/JSON files or directories.")
    run.add_argument("--target", required=True, help="http(s) endpoint, openrouter:<model>, or path.py:function.")
    run.add_argument("--output", default="runs/agent-royale-runs.jsonl")
    run.add_argument("--report", default="")
    run.add_argument("--summary", default="", help="Optional machine-readable JSON summary output.")
    run.add_argument("--junit", default="", help="Optional JUnit XML output for CI systems.")
    run.add_argument("--only", default="", help="Comma-separated task IDs to run.")
    run.add_argument("--runs-per-task", type=int, default=1)
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument("--timeout", type=float, default=120)
    run.add_argument("--fail-under-exact", type=float, default=None)
    run.add_argument("--ci", action="store_true", help="Run only tasks marked ci_safe=true.")

    report = sub.add_parser("report", help="Generate an HTML report from JSONL runs.")
    report.add_argument("input", help="Run JSONL file.")
    report.add_argument("--output", default="reports/agent-royale-report.html")
    report.add_argument("--summary", default="", help="Optional machine-readable JSON summary output.")
    report.add_argument("--junit", default="", help="Optional JUnit XML output.")

    sweep = sub.add_parser("sweep", help="Run one task pack across several models or targets.")
    sweep.add_argument("paths", nargs="+", help="Task YAML/JSON files or directories.")
    sweep.add_argument(
        "--models",
        default="",
        help="Comma-separated OpenRouter model IDs. Values are converted to openrouter:<model>.",
    )
    sweep.add_argument(
        "--targets",
        default="",
        help="Comma-separated raw targets: http(s) endpoint, openrouter:<model>, or path.py:function.",
    )
    sweep.add_argument("--output-dir", default="", help="Directory for sweep outputs.")
    sweep.add_argument("--only", default="", help="Comma-separated task IDs to run.")
    sweep.add_argument("--runs-per-task", type=int, default=1)
    sweep.add_argument("--concurrency", type=int, default=4)
    sweep.add_argument("--timeout", type=float, default=120)
    sweep.add_argument("--ci", action="store_true", help="Run only tasks marked ci_safe=true.")

    compare = sub.add_parser("compare", help="Compare two JSONL run logs.")
    compare.add_argument("before", help="Baseline run JSONL file.")
    compare.add_argument("after", help="Candidate run JSONL file.")
    compare.add_argument("--markdown", default="", help="Optional Markdown output path.")
    compare.add_argument("--fail-on-regression", action="store_true", help="Exit 2 if any common task regressed.")
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
    tasks = filter_tasks(flatten_tasks(packs), args.only)
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


async def cmd_audit_errors(args: argparse.Namespace) -> int:
    packs = load_task_packs([Path(item) for item in args.paths])
    tasks = filter_tasks(flatten_tasks(packs), args.only)
    rows = []
    print(f"Auditing {len(tasks)} task oracle{'s' if len(tasks) != 1 else ''} for errors")
    for task in tasks:
        snapshot = await fetch_ground_truth_snapshot(task, timeout_seconds=args.timeout)
        if snapshot.status == "verified" and not args.include_ok:
            print(f"OK {task.id}")
            continue
        row = oracle_audit_row(task, snapshot)
        rows.append(row)
        label = "OK" if snapshot.status == "verified" else "ISSUE"
        print(f"{label} {task.id}: {snapshot.status} {row['suggested_action']}")
    output = Path(args.output)
    write_oracle_error_markdown(rows, output)
    print(f"\nError audit: {output}")
    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({"tasks": rows}, indent=2, sort_keys=True), encoding="utf-8")
        print(f"JSON: {json_path}")
    if args.csv:
        csv_path = Path(args.csv)
        write_oracle_error_csv(rows, csv_path)
        print(f"CSV: {csv_path}")
    issue_count = sum(1 for row in rows if row["status"] != "verified")
    print(f"Exported {len(rows)} row{'s' if len(rows) != 1 else ''}; issues: {issue_count}")
    return 0 if issue_count == 0 else 1


def cmd_lint(args: argparse.Namespace) -> int:
    task_files = expand_task_files(args.paths)
    findings = lint_task_paths(task_files)
    print(render_lint_findings(findings))
    has_errors = any(finding.severity == "error" for finding in findings)
    has_warnings = any(finding.severity == "warning" for finding in findings)
    if has_errors or (args.strict and has_warnings):
        return 1
    return 0


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


async def cmd_demo(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "demo-runs.jsonl"
    report = output_dir / "demo-report.html"
    summary = output_dir / "demo-summary.json"
    junit = output_dir / "demo-junit.xml"
    if output.exists():
        output.unlink()
    packs = load_task_packs([Path("task-packs/static-smoke.yaml")])
    tasks = flatten_tasks(packs)
    print(f"Running Agent Royale demo against {args.target}")
    records = await run_tasks(
        tasks,
        target=args.target,
        output=output,
        runs_per_task=1,
        concurrency=2,
        timeout_seconds=30,
    )
    write_html_report(records, report)
    write_summary_json(records, summary)
    write_junit_report(records, junit)
    scoreable = [record for record in records if record.scoreable]
    passed = sum(1 for record in scoreable if record.passed)
    issues = [record for record in records if record_verdict(record) != "correct"]
    print(f"\nDemo exact accuracy: {passed}/{len(scoreable)}")
    if issues:
        print("Representative issue:")
        issue = issues[0]
        print(f"- {issue.task_id}: {record_verdict(issue)}")
        print(f"  expected: {issue.ground_truth}")
        print(f"  got: {issue.extracted_claim or issue.answer}")
    print(f"\nReport: {report}")
    print(f"Summary: {summary}")
    print(f"JUnit: {junit}")
    return 0


async def cmd_run(args: argparse.Namespace) -> int:
    output = Path(args.output)
    if output.exists():
        output.unlink()
    packs = load_task_packs([Path(item) for item in args.paths])
    tasks = filter_tasks(flatten_tasks(packs), args.only)
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
    if args.summary:
        summary_path = Path(args.summary)
        write_summary_json(records, summary_path)
        print(f"Summary: {summary_path}")
    if args.junit:
        junit_path = Path(args.junit)
        write_junit_report(records, junit_path)
        print(f"JUnit: {junit_path}")
    if args.fail_under_exact is not None and accuracy < args.fail_under_exact:
        print(f"Failed threshold: {accuracy:.1%} < {args.fail_under_exact:.1%}")
        return 2
    return 0


async def cmd_sweep(args: argparse.Namespace) -> int:
    targets = sweep_targets(args.models, args.targets)
    if not targets:
        print("Pass at least one --models or --targets value.")
        return 1
    output_dir = Path(args.output_dir or default_sweep_dir())
    output_dir.mkdir(parents=True, exist_ok=True)
    packs = load_task_packs([Path(item) for item in args.paths])
    tasks = filter_tasks(flatten_tasks(packs), args.only)
    if args.ci:
        skipped = [task for task in tasks if not task.ci_safe]
        tasks = [task for task in tasks if task.ci_safe]
        if skipped:
            print(f"Skipping {len(skipped)} non-CI-safe task{'s' if len(skipped) != 1 else ''}.")
    print(f"Running sweep: {len(tasks)} task(s) across {len(targets)} target(s)")
    rows = []
    for target in targets:
        slug = slugify(target.replace(":", "-").replace("/", "-"))
        run_path = output_dir / f"{slug}.jsonl"
        report_path = output_dir / f"{slug}.html"
        summary_path = output_dir / f"{slug}-summary.json"
        junit_path = output_dir / f"{slug}.xml"
        if run_path.exists():
            run_path.unlink()
        print(f"\nTarget: {target}")
        records = await run_tasks(
            tasks,
            target=target,
            output=run_path,
            runs_per_task=args.runs_per_task,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout,
        )
        write_html_report(records, report_path)
        write_summary_json(records, summary_path)
        write_junit_report(records, junit_path)
        row = sweep_row(target, records, run_path, report_path, summary_path, junit_path)
        rows.append(row)
        print(
            f"Exact: {row['exact_accuracy']:.1%}; "
            f"source-supported: {row['source_supported_accuracy']:.1%}; "
            f"median latency: {row['median_latency_ms']:.0f} ms"
        )
    rows.sort(
        key=lambda item: (
            -item["source_supported_accuracy"],
            -item["exact_accuracy"],
            item["median_latency_ms"],
        )
    )
    write_sweep_outputs(rows, output_dir)
    print(f"\nSweep summary: {output_dir / 'sweep-summary.md'}")
    print(f"Sweep JSON: {output_dir / 'sweep-summary.json'}")
    print("\nTop target:")
    winner = rows[0]
    print(
        f"- {winner['target']} "
        f"({winner['exact_accuracy']:.1%} exact, "
        f"{winner['source_supported_accuracy']:.1%} source-supported)"
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    records = load_records(Path(args.input))
    output = Path(args.output)
    write_html_report(records, output)
    print(f"Report: {output}")
    if args.summary:
        summary_path = Path(args.summary)
        write_summary_json(records, summary_path)
        print(f"Summary: {summary_path}")
    if args.junit:
        junit_path = Path(args.junit)
        write_junit_report(records, junit_path)
        print(f"JUnit: {junit_path}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    comparison = compare_run_files(Path(args.before), Path(args.after))
    print(render_terminal_summary(comparison))
    if args.markdown:
        output = Path(args.markdown)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_markdown_report(comparison), encoding="utf-8")
        print(f"\nMarkdown: {output}")
    if args.fail_on_regression and comparison.regressions:
        return 2
    return 0


def filter_tasks(tasks: list, only: str) -> list:
    if not only:
        return tasks
    wanted = {item.strip() for item in only.split(",") if item.strip()}
    filtered = [task for task in tasks if task.id in wanted]
    missing = sorted(wanted - {task.id for task in filtered})
    if missing:
        raise ValueError(f"Unknown task id(s) for --only: {', '.join(missing)}")
    return filtered


def oracle_audit_row(task, snapshot) -> dict:
    return {
        "task_id": task.id,
        "task_pack": task.task_pack_name,
        "labels": ",".join(task.labels),
        "domain": citation_domain(task.required_source),
        "required_source": task.required_source,
        "ground_truth_method": task.ground_truth.method,
        "bright_data_tool": task.ground_truth.tool or "",
        "source_url": task.ground_truth.source_url or task.ground_truth.url or task.required_source,
        "status": snapshot.status,
        "error": snapshot.error or "",
        "parser": snapshot.parser,
        "final_url": snapshot.final_url,
        "evidence_text": snapshot.evidence_text,
        "ambiguity_flags": ",".join(snapshot.ambiguity_flags),
        "validation_checks": json.dumps(snapshot.validation_checks, sort_keys=True),
        "suggested_action": suggested_oracle_action(task, snapshot),
        "salvage_priority": salvage_priority(snapshot.status),
    }


def suggested_oracle_action(task, snapshot) -> str:
    if snapshot.status == "verified":
        return "No action needed."
    if task.ground_truth.method == "bright_data" and "BRIGHT_DATA_API_KEY" in str(snapshot.error or ""):
        return "Set Bright Data credentials and rerun; task was not actually fetched."
    if snapshot.status == "selector_broken":
        return "Update regex/field or add require_near_text around the exact source value."
    if snapshot.status == "ground_truth_ambiguous":
        return "Tighten parser context or split the task so the oracle has one candidate."
    if snapshot.status == "source_unreachable":
        return "Check source URL/tool availability; try another Bright Data endpoint or rendered workflow."
    if snapshot.status == "low_confidence":
        return "Inspect evidence text and policy checks; strengthen evidence or relax policy intentionally."
    if snapshot.status == "oracle_failed":
        return "Inspect raw excerpt/error; likely adapter config, parser, or credentials issue."
    return "Inspect snapshot evidence and raw excerpt."


def salvage_priority(status: str) -> str:
    if status in {"selector_broken", "ground_truth_ambiguous", "low_confidence"}:
        return "high"
    if status in {"source_unreachable", "oracle_failed"}:
        return "medium"
    return "low"


def write_oracle_error_markdown(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    issue_rows = [row for row in rows if row["status"] != "verified"]
    counts = Counter(row["status"] for row in rows)
    lines = [
        "# Agent Royale Oracle Error Audit",
        "",
        f"Rows exported: {len(rows)}",
        f"Issues: {len(issue_rows)}",
        "",
        "## Status Counts",
        "",
    ]
    if counts:
        for status, count in sorted(counts.items()):
            lines.append(f"- `{status}`: {count}")
    else:
        lines.append("- No rows exported. Use `--include-ok` to include verified tasks.")
    if issue_rows:
        lines.extend(
            [
                "",
                "## Salvage List",
                "",
                "| Priority | Task | Status | Tool | Source | Suggested action |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for row in sorted(issue_rows, key=lambda item: (priority_rank(item["salvage_priority"]), item["task_id"])):
            lines.append(
                f"| {row['salvage_priority']} | `{row['task_id']}` | `{row['status']}` | "
                f"`{row['bright_data_tool'] or row['ground_truth_method']}` | {row['source_url']} | "
                f"{row['suggested_action']} |"
            )
        lines.extend(["", "## Details", ""])
        for row in issue_rows:
            lines.extend(
                [
                    f"### {row['task_id']}",
                    "",
                    f"- Status: `{row['status']}`",
                    f"- Error: {row['error'] or 'n/a'}",
                    f"- Required source: {row['required_source']}",
                    f"- Ground-truth method: `{row['ground_truth_method']}`",
                    f"- Bright Data tool: `{row['bright_data_tool'] or 'n/a'}`",
                    f"- Parser: `{row['parser'] or 'n/a'}`",
                    f"- Validation checks: `{row['validation_checks']}`",
                    f"- Suggested action: {row['suggested_action']}",
                    "",
                ]
            )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def priority_rank(value: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(value, 3)


def write_oracle_error_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "task_id",
        "task_pack",
        "labels",
        "domain",
        "required_source",
        "ground_truth_method",
        "bright_data_tool",
        "source_url",
        "status",
        "error",
        "parser",
        "final_url",
        "ambiguity_flags",
        "validation_checks",
        "suggested_action",
        "salvage_priority",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def citation_domain(value: str) -> str:
    parsed = urlparse(str(value or "") if "://" in str(value or "") else f"https://{value}")
    return parsed.netloc.lower().removeprefix("www.")


def sweep_targets(models: str, targets: str) -> list[str]:
    values = []
    for model in split_csv(models):
        values.append(model if model.startswith("openrouter:") else f"openrouter:{model}")
    values.extend(split_csv(targets))
    seen = set()
    deduped = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def default_sweep_dir() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"runs/sweeps/{stamp}"


def sweep_row(
    target: str,
    records: list,
    run_path: Path,
    report_path: Path,
    summary_path: Path,
    junit_path: Path,
) -> dict:
    scoreable = [record for record in records if record.scoreable]
    exact = sum(1 for record in scoreable if record.passed)
    supported = sum(1 for record in scoreable if record_source_supported(record))
    latencies = sorted(record.latency_ms for record in records if record.latency_ms)
    median_latency = latencies[len(latencies) // 2] if latencies else 0
    costs = [record.cost_usd for record in records if record.cost_usd is not None]
    outcomes = Counter(record_verdict(record) for record in records)
    return {
        "target": target,
        "runs": len(records),
        "scoreable": len(scoreable),
        "exact_correct": exact,
        "exact_accuracy": exact / len(scoreable) if scoreable else 0,
        "source_supported_correct": supported,
        "source_supported_accuracy": supported / len(scoreable) if scoreable else 0,
        "oracle_skips": len(records) - len(scoreable),
        "median_latency_ms": median_latency,
        "total_cost_usd": sum(costs) if costs else None,
        "outcomes": dict(outcomes),
        "run_path": str(run_path),
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "junit_path": str(junit_path),
    }


def write_sweep_outputs(rows: list[dict], output_dir: Path) -> None:
    json_path = output_dir / "sweep-summary.json"
    md_path = output_dir / "sweep-summary.md"
    json_path.write_text(json.dumps({"targets": rows}, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Agent Royale Sweep Summary",
        "",
        sweep_recommendation(rows),
        "",
        "| Rank | Target | Exact | Source-supported | Median latency | Cost | Report |",
        "| ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for idx, row in enumerate(rows, start=1):
        cost = "" if row["total_cost_usd"] is None else f"${row['total_cost_usd']:.4f}"
        lines.append(
            f"| {idx} | `{row['target']}` | {row['exact_accuracy']:.1%} | "
            f"{row['source_supported_accuracy']:.1%} | {row['median_latency_ms']:.0f} ms | "
            f"{cost} | [{Path(row['report_path']).name}]({Path(row['report_path']).name}) |"
        )
    lines.append("")
    lines.append("Targets are ranked by source-supported accuracy, then exact accuracy, then median latency.")
    lines.extend(["", "## Outcome Breakdown", ""])
    for row in rows:
        outcomes = ", ".join(f"`{name}`={count}" for name, count in sorted(row["outcomes"].items()))
        lines.append(f"- `{row['target']}`: {outcomes or 'no outcomes'}")
    lines.extend(
        [
            "",
            "## How To Use This",
            "",
            "- If a simpler model has comparable source-supported accuracy, prefer it for lower operational complexity.",
            "- If source-supported accuracy is low across models, try a specialized search, scraping, or browser stack.",
            "- If exact accuracy is high but source-supported accuracy is low, inspect citation/source policy failures.",
            "- Rerun the sweep after prompt, model, tool, or routing changes to catch regressions.",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sweep_recommendation(rows: list[dict]) -> str:
    if not rows:
        return "No targets were evaluated."
    winner = rows[0]
    if winner["source_supported_accuracy"] >= 0.9:
        return (
            f"Recommendation: `{winner['target']}` is the strongest fit in this sweep "
            f"with {winner['source_supported_accuracy']:.1%} source-supported accuracy."
        )
    if winner["exact_accuracy"] >= 0.8 and winner["source_supported_accuracy"] < 0.8:
        return (
            "Recommendation: the best target is often finding the right value, but source support is weak. "
            "Inspect citation failures before trusting this stack."
        )
    return (
        "Recommendation: no target cleared a strong source-supported threshold. "
        "Try a more specialized search, scraping, browser, or custom-agent workflow for this task pack."
    )
