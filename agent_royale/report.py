from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from urllib.parse import urlparse

from agent_royale.schema import RunRecord


def load_records(path: Path) -> list[RunRecord]:
    records: list[RunRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(RunRecord.model_validate(json.loads(line)))
    return records


def write_html_report(records: list[RunRecord], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    total = len(records)
    exact_correct = sum(1 for item in records if item.passed)
    source_supported = sum(1 for item in records if item.passed and not item.failure_mode)
    accuracy = exact_correct / total if total else 0
    issue_count = sum(1 for item in records if item.failure_mode)
    no_answer = sum(1 for item in records if item.failure_mode == "no_answer")
    latencies = [item.latency_ms for item in records if item.latency_ms]
    failures = Counter(item.failure_mode or "source_supported_correct" for item in records)
    median_latency = median(latencies) if latencies else 0
    by_task = defaultdict(list)
    for record in records:
        by_task[record.task_id].append(record)
    target = records[0].target if records else "unknown"
    created_at = records[0].created_at if records else ""
    source_summary = summarize_required_sources(records)
    grading_summary = summarize_grading(records)
    rows = "\n".join(render_record(record) for record in sorted(records, key=lambda item: (not bool(item.failure_mode), item.task_id)))
    issue_records = [record for record in records if record.failure_mode]
    catch_cards = "\n".join(render_catch(record) for record in issue_records[:3])
    failure_rows = "\n".join(
        f"<tr><td><span class=\"status-dot {status_class(name)}\"></span>{esc(pretty_label(name))}</td><td>{count}</td><td>{pct(count, total)}</td></tr>"
        for name, count in failures.most_common()
    )
    task_rows = "\n".join(
        f"<tr><td><code>{esc(task_id)}</code></td><td>{sum(1 for r in runs if r.passed)}/{len(runs)}</td>"
        f"<td>{sum(1 for r in runs if r.passed and not r.failure_mode)}/{len(runs)}</td>"
        f"<td>{esc(', '.join(pretty_label(item) for item in sorted(set(r.failure_mode or 'correct' for r in runs))))}</td></tr>"
        for task_id, runs in sorted(by_task.items())
    )
    verdict = "Launch-safe" if accuracy >= 0.8 else "Needs attention" if accuracy >= 0.6 else "High risk"
    caught = short_summary(issue_records)
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Agent Royale Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink:#15181e; --muted:#667085; --line:#d9dee8; --soft:#f4f7fb;
      --panel:#ffffff; --good:#087f5b; --bad:#c92a2a; --warn:#b76e00; --blue:#2563eb;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:linear-gradient(180deg,#f8fbff 0,#f5f7fb 260px,#ffffff 260px); }}
    .wrap {{ max-width:1200px; margin:0 auto; padding:34px 28px 56px; }}
    header {{ display:grid; grid-template-columns:minmax(0,1fr) 260px; gap:24px; align-items:start; }}
    h1 {{ margin:0 0 8px; font-size:38px; line-height:1.05; letter-spacing:0; }}
    h2 {{ margin:28px 0 12px; font-size:20px; letter-spacing:0; }}
    p {{ margin:0; color:var(--muted); line-height:1.5; }}
    code {{ font-family:"SFMono-Regular", Consolas, monospace; font-size:12px; }}
    .subhead {{ max-width:760px; font-size:16px; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:16px; }}
    .pill {{ border:1px solid var(--line); background:rgba(255,255,255,.82); border-radius:999px; padding:7px 10px; color:#344054; font-size:12px; font-weight:700; }}
    .verdict {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:18px; box-shadow:0 12px 36px rgba(15,23,42,.06); }}
    .score {{ font-size:44px; line-height:1; font-weight:850; color:{'var(--good)' if accuracy >= .8 else 'var(--warn)' if accuracy >= .6 else 'var(--bad)'}; }}
    .verdict-label {{ margin-top:8px; font-size:13px; font-weight:800; color:var(--ink); }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:26px; }}
    .card {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:16px; box-shadow:0 8px 24px rgba(15,23,42,.04); }}
    .num {{ font-size:26px; line-height:1; font-weight:850; }}
    .label {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; margin-top:8px; font-weight:800; }}
    .insight {{ margin-top:16px; border:1px solid #c7d7fe; background:#eff6ff; border-radius:8px; padding:14px 16px; display:grid; grid-template-columns:128px minmax(0,1fr); gap:14px; align-items:start; }}
    .insight strong {{ color:#1d4ed8; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .method {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:16px; }}
    .method-card {{ border:1px solid var(--line); background:#fff; border-radius:8px; padding:14px 16px; }}
    .method-card strong {{ display:block; font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:#344054; margin-bottom:6px; }}
    .split {{ display:grid; grid-template-columns:.82fr 1.18fr; gap:22px; align-items:start; }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; box-shadow:0 8px 24px rgba(15,23,42,.04); }}
    th,td {{ text-align:left; padding:12px 14px; border-bottom:1px solid #e8ecf3; vertical-align:middle; font-size:14px; }}
    th {{ font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); background:#f7f9fc; font-weight:850; }}
    tr:last-child td {{ border-bottom:0; }}
    .pass,.fail {{ font-weight:850; }}
    .pass {{ color:var(--good); }}
    .fail {{ color:var(--bad); }}
    .muted {{ color:var(--muted); }}
    .answer {{ max-width:360px; white-space:pre-wrap; color:#344054; }}
    .claim {{ font-weight:750; }}
    .truth {{ font-weight:750; color:#175cd3; }}
    .failure {{ color:var(--bad); font-weight:750; }}
    .source {{ color:#475467; font-size:12px; max-width:260px; overflow-wrap:anywhere; }}
    .catch-list {{ display:grid; gap:10px; }}
    .catch {{ border:1px solid var(--line); border-left:4px solid var(--bad); border-radius:8px; background:#fff; padding:13px 14px; }}
    .catch-title {{ display:flex; justify-content:space-between; gap:14px; align-items:center; margin-bottom:8px; }}
    .catch-title code {{ color:var(--bad); font-weight:800; }}
    .catch-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    .mini-label {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; margin-bottom:3px; font-weight:800; }}
    .status-dot {{ display:inline-block; width:8px; height:8px; border-radius:999px; margin-right:8px; background:var(--muted); }}
    .status-dot.correct,.status-dot.source-supported-correct {{ background:var(--good); }}
    .status-dot.wrong-value,.status-dot.wrong-source,.status-dot.unsupported-citation,.status-dot.no-answer {{ background:var(--bad); }}
    footer {{ margin-top:24px; color:var(--muted); font-size:12px; }}
    @media(max-width:860px) {{ header,.split,.method {{ grid-template-columns:1fr; }} .grid {{ grid-template-columns:1fr 1fr; }} .insight {{ grid-template-columns:1fr; }} th:nth-child(6),td:nth-child(6) {{ display:none; }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <header>
      <div>
        <h1>Agent Royale Eval Report</h1>
        <p class="subhead">This run tested one agent target against {total} live-web tasks. Each row shows the agent's extracted claim, the oracle value, the required source, and the reason the task passed or failed.</p>
        <div class="meta">
          <span class="pill">target: {esc(target)}</span>
          <span class="pill">runs: {total}</span>
          <span class="pill">generated: {esc(created_at[:10])}</span>
        </div>
      </div>
      <div class="verdict">
        <div class="score">{accuracy:.0%}</div>
        <div class="verdict-label">{esc(verdict)}</div>
        <p>Exact-value pass rate across {total} run{'s' if total != 1 else ''}</p>
      </div>
    </header>

    <section class="grid">
      <div class="card"><div class="num">{exact_correct}</div><div class="label">Exact values</div></div>
      <div class="card"><div class="num">{source_supported}</div><div class="label">Source-supported</div></div>
      <div class="card"><div class="num">{issue_count}</div><div class="label">Issues</div></div>
      <div class="card"><div class="num">{no_answer}</div><div class="label">No answer</div></div>
    </section>

    <section class="method">
      <div class="method-card">
        <strong>Oracle values</strong>
        <p>{esc(source_summary)}</p>
      </div>
      <div class="method-card">
        <strong>Grading</strong>
        <p>{esc(grading_summary)}</p>
      </div>
      <div class="method-card">
        <strong>Source check</strong>
        <p>Each citation URL is checked against the task's required source. Matching values from the wrong source are marked as source failures.</p>
      </div>
    </section>

    <section class="insight">
      <strong>Result</strong>
      <p>{esc(caught)}</p>
    </section>

    <section class="split">
      <div>
        <h2>Outcome Breakdown</h2>
        <table><thead><tr><th>Outcome</th><th>Runs</th><th>Share</th></tr></thead><tbody>{failure_rows}</tbody></table>

        <h2>Representative Catches</h2>
        <div class="catch-list">{catch_cards or '<p class="muted">No failures in this run.</p>'}</div>
      </div>

      <div>
        <h2>Task-Level Results</h2>
        <table><thead><tr><th>Task</th><th>Exact</th><th>Source-supported</th><th>Observed outcomes</th></tr></thead><tbody>{task_rows}</tbody></table>
      </div>
    </section>

    <h2>Run Details</h2>
    <table>
      <thead><tr><th>Status</th><th>Task</th><th>Claim</th><th>Ground truth</th><th>Outcome</th><th>Required source</th><th>Answer</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <footer>Generated from Agent Royale run data.</footer>
  </main>
</body>
</html>
"""
    output.write_text(html_text, encoding="utf-8")


def render_record(record: RunRecord) -> str:
    if record.failure_mode == "wrong_source":
        status_label = "SOURCE FAIL"
    elif record.failure_mode == "unsupported_citation":
        status_label = "SOURCE ISSUE"
    elif record.passed:
        status_label = "PASS"
    else:
        status_label = "FAIL"
    status = f'<span class="{"pass" if record.passed and not record.failure_mode else "fail"}">{status_label}</span>'
    answer_text = compact_text(record.answer or record.error or "")
    return (
        "<tr>"
        f"<td>{status}</td>"
        f"<td><code>{esc(record.task_id)}</code></td>"
        f"<td class=\"claim\">{esc(record.extracted_claim)}</td>"
        f"<td class=\"truth\">{esc(record.ground_truth)}</td>"
        f"<td class=\"failure\">{esc(pretty_label(record.failure_mode or 'correct'))}</td>"
        f"<td class=\"source\">{esc(record.required_source)}</td>"
        f"<td class=\"answer\">{esc(answer_text)}</td>"
        "</tr>"
    )


def render_catch(record: RunRecord) -> str:
    cited = ", ".join(citation_domain(item.url) for item in record.citations[:2]) or "none"
    return (
        "<div class=\"catch\">"
        f"<div class=\"catch-title\"><code>{esc(record.task_id)}</code><span class=\"failure\">{esc(pretty_label(record.failure_mode or 'failed'))}</span></div>"
        "<div class=\"catch-grid\">"
        f"<div><div class=\"mini-label\">Agent said</div><div class=\"claim\">{esc(record.extracted_claim)}</div></div>"
        f"<div><div class=\"mini-label\">Oracle had</div><div class=\"truth\">{esc(record.ground_truth)}</div></div>"
        "</div>"
        f"<p class=\"muted\" style=\"margin-top:8px;font-size:12px\">Required source: {esc(record.required_source)}</p>"
        f"<p class=\"muted\" style=\"margin-top:3px;font-size:12px\">Agent cited: {esc(cited)}</p>"
        "</div>"
    )


def short_summary(records: list[RunRecord]) -> str:
    if not records:
        return "Every answer matched the independent oracle and source-support check for this run."
    modes = Counter(record.failure_mode or "failed" for record in records)
    parts = []
    if modes.get("wrong_source"):
        parts.append("source drift")
    if modes.get("wrong_value"):
        parts.append("stale or incorrect values")
    if modes.get("unsupported_citation"):
        parts.append("answers whose citations did not support the claim")
    if modes.get("no_answer"):
        parts.append("missing answers")
    if not parts:
        parts.append("failed assertions")
    examples = ", ".join(record.task_id for record in records[:2])
    return f"{len(records)} task{'s' if len(records) != 1 else ''} had issues: {', '.join(parts)}. Examples: {examples}."


def summarize_required_sources(records: list[RunRecord]) -> str:
    task_ids = {record.task_id for record in records}
    source_text = " ".join(record.required_source for record in records)
    families = []
    if any(task_id.startswith("github_") for task_id in task_ids):
        families.append("GitHub REST API for repository counts and release tags")
    if "npmjs.com/package" in source_text:
        families.append("npm registry latest-package metadata for versions and licenses")
    if "api.npmjs.org/downloads" in source_text:
        families.append("npm downloads API for weekly download counts")
    if any(task_id.startswith("bd_") for task_id in task_ids) or "linkedin.com" in source_text:
        families.append("Bright Data structured extraction for web pages that need reliable extraction")
    if families:
        return "; ".join(families) + "."
    domains = sorted({citation_domain(record.required_source) for record in records if record.required_source})
    if not domains:
        return "No oracle sources were recorded."
    joined = ", ".join(domains[:4])
    if len(domains) > 4:
        joined += f", +{len(domains) - 4} more"
    return f"Values came from task-pack oracle sources for {joined}; each task row lists the required source used for grading."


def summarize_grading(records: list[RunRecord]) -> str:
    numeric = sum(1 for record in records if isinstance(record.normalized_truth, (int, float)))
    text = len(records) - numeric
    parts = []
    if numeric:
        parts.append(f"{numeric} numeric task{'s' if numeric != 1 else ''} parsed the claimed number and compared it to the oracle with the task tolerance")
    if text:
        parts.append(f"{text} text task{'s' if text != 1 else ''} normalized case and punctuation before comparison")
    return "; ".join(parts) + "."


def citation_domain(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    return parsed.netloc.lower().removeprefix("www.") or text.lower()


def pretty_label(value: object) -> str:
    labels = {
        "source_supported_correct": "correct with source support",
        "unsupported_citation": "unsupported citation",
        "wrong_source": "wrong source",
        "wrong_value": "wrong value",
        "no_answer": "no answer",
        "tool_failure": "tool failure",
        "correct": "correct",
    }
    text = str(value)
    return labels.get(text, text.replace("_", " "))


def status_class(value: object) -> str:
    return str(value).replace("_", "-")


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def compact_text(value: object) -> str:
    return " ".join(str(value if value is not None else "").split())


def pct(count: int, total: int) -> str:
    return f"{(count / total):.0%}" if total else "0%"
