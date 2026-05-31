from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

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
    passed = sum(1 for item in records if item.passed)
    accuracy = passed / total if total else 0
    wrong = sum(1 for item in records if item.failure_mode in {"wrong_value", "wrong_source", "unsupported_citation"})
    no_answer = sum(1 for item in records if item.failure_mode == "no_answer")
    latencies = [item.latency_ms for item in records if item.latency_ms]
    failures = Counter(item.failure_mode or "correct" for item in records)
    median_latency = median(latencies) if latencies else 0
    by_task = defaultdict(list)
    for record in records:
        by_task[record.task_id].append(record)
    target = records[0].target if records else "unknown"
    created_at = records[0].created_at if records else ""
    rows = "\n".join(render_record(record) for record in sorted(records, key=lambda item: (item.passed, item.task_id)))
    failing_records = [record for record in records if not record.passed]
    catch_cards = "\n".join(render_catch(record) for record in failing_records[:3])
    failure_rows = "\n".join(
        f"<tr><td><span class=\"status-dot {status_class(name)}\"></span>{esc(pretty_label(name))}</td><td>{count}</td><td>{pct(count, total)}</td></tr>"
        for name, count in failures.most_common()
    )
    task_rows = "\n".join(
        f"<tr><td><code>{esc(task_id)}</code></td><td>{sum(1 for r in runs if r.passed)}/{len(runs)}</td>"
        f"<td>{esc(', '.join(pretty_label(item) for item in sorted(set(r.failure_mode or 'correct' for r in runs))))}</td></tr>"
        for task_id, runs in sorted(by_task.items())
    )
    verdict = "Launch-safe" if accuracy >= 0.8 else "Needs attention" if accuracy >= 0.6 else "High risk"
    caught = short_summary(failing_records)
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
    .eyebrow {{ color:var(--blue); font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px; }}
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
    .catch-list {{ display:grid; gap:10px; }}
    .catch {{ border:1px solid var(--line); border-left:4px solid var(--bad); border-radius:8px; background:#fff; padding:13px 14px; }}
    .catch-title {{ display:flex; justify-content:space-between; gap:14px; align-items:center; margin-bottom:8px; }}
    .catch-title code {{ color:var(--bad); font-weight:800; }}
    .catch-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    .mini-label {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; margin-bottom:3px; font-weight:800; }}
    .status-dot {{ display:inline-block; width:8px; height:8px; border-radius:999px; margin-right:8px; background:var(--muted); }}
    .status-dot.correct {{ background:var(--good); }}
    .status-dot.wrong-value,.status-dot.wrong-source,.status-dot.unsupported-citation,.status-dot.no-answer {{ background:var(--bad); }}
    footer {{ margin-top:24px; color:var(--muted); font-size:12px; }}
    @media(max-width:860px) {{ header,.split {{ grid-template-columns:1fr; }} .grid {{ grid-template-columns:1fr 1fr; }} .insight {{ grid-template-columns:1fr; }} th:nth-child(6),td:nth-child(6) {{ display:none; }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <header>
      <div>
        <div class="eyebrow">Agent Royale V2</div>
        <h1>Agent Royale Report</h1>
        <p class="subhead">Unit-test results for an AI agent that browses the web. Ground truth is fetched independently, then each answer is graded without an LLM judge.</p>
        <div class="meta">
          <span class="pill">target: {esc(target)}</span>
          <span class="pill">runs: {total}</span>
          <span class="pill">generated: {esc(created_at[:10])}</span>
        </div>
      </div>
      <div class="verdict">
        <div class="score">{accuracy:.0%}</div>
        <div class="verdict-label">{esc(verdict)}</div>
        <p>Exact accuracy across {total} run{'s' if total != 1 else ''}</p>
      </div>
    </header>

    <section class="grid">
      <div class="card"><div class="num">{passed}</div><div class="label">Correct</div></div>
      <div class="card"><div class="num">{wrong}</div><div class="label">Bad claims</div></div>
      <div class="card"><div class="num">{no_answer}</div><div class="label">No answer</div></div>
      <div class="card"><div class="num">{median_latency:.0f}ms</div><div class="label">Median latency</div></div>
    </section>

    <section class="insight">
      <strong>What it caught</strong>
      <p>{esc(caught)}</p>
    </section>

    <section class="split">
      <div>
        <h2>Failure Breakdown</h2>
        <table><thead><tr><th>Outcome</th><th>Runs</th><th>Share</th></tr></thead><tbody>{failure_rows}</tbody></table>

        <h2>Representative Catches</h2>
        <div class="catch-list">{catch_cards or '<p class="muted">No failures in this run.</p>'}</div>
      </div>

      <div>
        <h2>Task-Level Results</h2>
        <table><thead><tr><th>Task</th><th>Passed</th><th>Observed outcomes</th></tr></thead><tbody>{task_rows}</tbody></table>
      </div>
    </section>

    <h2>Run Details</h2>
    <table>
      <thead><tr><th>Status</th><th>Task</th><th>Claim</th><th>Ground truth</th><th>Failure</th><th>Answer</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <footer>Generated from Agent Royale run data.</footer>
  </main>
</body>
</html>
"""
    output.write_text(html_text, encoding="utf-8")


def render_record(record: RunRecord) -> str:
    status = '<span class="pass">PASS</span>' if record.passed else '<span class="fail">FAIL</span>'
    return (
        "<tr>"
        f"<td>{status}</td>"
        f"<td><code>{esc(record.task_id)}</code></td>"
        f"<td class=\"claim\">{esc(record.extracted_claim)}</td>"
        f"<td class=\"truth\">{esc(record.ground_truth)}</td>"
        f"<td class=\"failure\">{esc(pretty_label(record.failure_mode or 'correct'))}</td>"
        f"<td class=\"answer\">{esc(record.answer or record.error or '')}</td>"
        "</tr>"
    )


def render_catch(record: RunRecord) -> str:
    return (
        "<div class=\"catch\">"
        f"<div class=\"catch-title\"><code>{esc(record.task_id)}</code><span class=\"failure\">{esc(pretty_label(record.failure_mode or 'failed'))}</span></div>"
        "<div class=\"catch-grid\">"
        f"<div><div class=\"mini-label\">Agent said</div><div class=\"claim\">{esc(record.extracted_claim)}</div></div>"
        f"<div><div class=\"mini-label\">Oracle had</div><div class=\"truth\">{esc(record.ground_truth)}</div></div>"
        "</div>"
        f"<p class=\"muted\" style=\"margin-top:8px;font-size:12px\">Required source: {esc(record.required_source)}</p>"
        "</div>"
    )


def short_summary(records: list[RunRecord]) -> str:
    if not records:
        return "Every answer matched the independent oracle for this run."
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
    return f"Found {len(records)} issue{'s' if len(records) != 1 else ''}: {', '.join(parts)}. Example task{'s' if len(records[:2]) != 1 else ''}: {examples}."


def pretty_label(value: object) -> str:
    return str(value).replace("_", " ")


def status_class(value: object) -> str:
    return str(value).replace("_", "-")


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def pct(count: int, total: int) -> str:
    return f"{(count / total):.0%}" if total else "0%"
