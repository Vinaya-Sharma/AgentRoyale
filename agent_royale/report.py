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
    rows = "\n".join(render_record(record) for record in records)
    failure_rows = "\n".join(
        f"<tr><td>{esc(name)}</td><td>{count}</td><td>{pct(count, total)}</td></tr>"
        for name, count in failures.most_common()
    )
    task_rows = "\n".join(
        f"<tr><td>{esc(task_id)}</td><td>{sum(1 for r in runs if r.passed)}/{len(runs)}</td>"
        f"<td>{esc(', '.join(sorted(set(r.failure_mode or 'correct' for r in runs))))}</td></tr>"
        for task_id, runs in sorted(by_task.items())
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Agent Royale Report</title>
  <style>
    :root {{ color-scheme: light; --ink:#191816; --muted:#68645d; --line:#ded9cd; --bg:#f7f6f2; --panel:#fffdfa; --good:#0f766e; --bad:#b42318; --warn:#a16207; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:var(--bg); }}
    .wrap {{ max-width:1180px; margin:0 auto; padding:36px 24px 64px; }}
    header {{ display:flex; justify-content:space-between; gap:24px; align-items:flex-start; border-bottom:1px solid var(--line); padding-bottom:22px; }}
    h1 {{ margin:0 0 8px; font-size:34px; letter-spacing:0; }}
    h2 {{ margin:32px 0 12px; font-size:19px; }}
    p {{ margin:0; color:var(--muted); line-height:1.5; }}
    .verdict {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:14px 16px; min-width:220px; }}
    .score {{ font-size:36px; font-weight:800; color:{'var(--good)' if accuracy >= .8 else 'var(--warn)' if accuracy >= .6 else 'var(--bad)'}; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:22px; }}
    .card {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:16px; }}
    .num {{ font-size:24px; font-weight:800; }}
    .label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
    th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid var(--line); vertical-align:top; font-size:14px; }}
    th {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); background:#f0eee7; }}
    tr:last-child td {{ border-bottom:0; }}
    code {{ font-family:"SFMono-Regular", Consolas, monospace; font-size:12px; }}
    .pass {{ color:var(--good); font-weight:700; }}
    .fail {{ color:var(--bad); font-weight:700; }}
    .muted {{ color:var(--muted); }}
    .answer {{ max-width:360px; white-space:pre-wrap; }}
    @media(max-width:800px) {{ header {{ display:block; }} .grid {{ grid-template-columns:1fr 1fr; }} th:nth-child(4), td:nth-child(4) {{ display:none; }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <header>
      <div>
        <h1>Agent Royale Report</h1>
        <p>Exact live-web retrieval evaluation for AI search, RAG, and agent stacks.</p>
      </div>
      <div class="verdict">
        <div class="score">{accuracy:.0%}</div>
        <p>Exact accuracy across {total} run{'s' if total != 1 else ''}</p>
      </div>
    </header>

    <section class="grid">
      <div class="card"><div class="num">{passed}</div><div class="label">Correct</div></div>
      <div class="card"><div class="num">{wrong}</div><div class="label">Wrong usable</div></div>
      <div class="card"><div class="num">{no_answer}</div><div class="label">No answer</div></div>
      <div class="card"><div class="num">{median_latency:.0f}ms</div><div class="label">Median latency</div></div>
    </section>

    <h2>Failure Breakdown</h2>
    <table><thead><tr><th>Outcome</th><th>Runs</th><th>Share</th></tr></thead><tbody>{failure_rows}</tbody></table>

    <h2>Task Summary</h2>
    <table><thead><tr><th>Task</th><th>Passed</th><th>Observed outcomes</th></tr></thead><tbody>{task_rows}</tbody></table>

    <h2>Run Details</h2>
    <table>
      <thead><tr><th>Status</th><th>Task</th><th>Claim</th><th>Ground truth</th><th>Failure</th><th>Answer</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
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
        f"<td>{esc(record.extracted_claim)}</td>"
        f"<td>{esc(record.ground_truth)}</td>"
        f"<td>{esc(record.failure_mode or 'correct')}</td>"
        f"<td class=\"answer\">{esc(record.answer or record.error or '')}</td>"
        "</tr>"
    )


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def pct(count: int, total: int) -> str:
    return f"{(count / total):.0%}" if total else "0%"
