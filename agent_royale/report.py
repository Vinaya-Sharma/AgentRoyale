from __future__ import annotations

import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from urllib.parse import urlparse
from xml.etree import ElementTree

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
    scoreable_records = [item for item in records if item.scoreable]
    oracle_issue_records = [item for item in records if not item.scoreable]
    scoreable_total = len(scoreable_records)
    exact_correct = sum(1 for item in scoreable_records if item.passed)
    source_supported = sum(1 for item in scoreable_records if record_source_supported(item))
    accuracy = exact_correct / scoreable_total if scoreable_total else 0
    source_supported_accuracy = source_supported / scoreable_total if scoreable_total else 0
    agent_issue_records = [item for item in scoreable_records if record_verdict(item) != "correct"]
    issue_count = len(agent_issue_records)
    no_answer = sum(1 for item in records if item.failure_mode == "no_answer")
    latencies = [item.latency_ms for item in records if item.latency_ms]
    costs = [item.cost_usd for item in records if item.cost_usd is not None]
    failures = Counter(record_verdict(item) for item in records)
    oracle_statuses = Counter(item.oracle_status or "unknown" for item in records)
    median_latency = median(latencies) if latencies else 0
    p95_latency = percentile(latencies, 95)
    total_cost = sum(costs) if costs else None
    by_task = defaultdict(list)
    for record in records:
        by_task[record.task_id].append(record)
    target = records[0].target if records else "unknown"
    created_at = records[0].created_at if records else ""
    source_summary = summarize_required_sources(records)
    grading_summary = summarize_grading(records)
    rows = "\n".join(render_record(record) for record in sorted(records, key=lambda item: (record_verdict(item) == "correct", item.task_id)))
    issue_records = [record for record in records if record_verdict(record) != "correct"]
    catch_cards = "\n".join(render_catch(record) for record in issue_records[:3])
    fix_cards = render_fix_cards(records)
    outcome_bar = render_outcome_bar(failures, total)
    failure_rows = "\n".join(
        f"<tr><td><span class=\"status-dot {status_class(name)}\"></span>{esc(pretty_label(name))}</td><td>{count}</td><td>{pct(count, total)}</td><td>{esc(fix_for_verdict(name))}</td></tr>"
        for name, count in failures.most_common()
    )
    oracle_rows = "\n".join(
        f"<tr><td><span class=\"status-dot {status_class(name)}\"></span>{esc(pretty_label(name))}</td><td>{count}</td><td>{pct(count, total)}</td><td>{esc(fix_for_oracle_status(name))}</td></tr>"
        for name, count in oracle_statuses.most_common()
    )
    task_rows = "\n".join(
        f"<tr><td><code>{esc(task_id)}</code><div class=\"question\">{esc(runs[0].task_question)}</div></td><td>{sum(1 for r in runs if r.passed)}/{len(runs)}</td>"
        f"<td>{sum(1 for r in runs if record_source_supported(r))}/{len(runs)}</td>"
        f"<td>{esc(', '.join(pretty_label(item) for item in sorted(set(record_verdict(r) for r in runs))))}</td></tr>"
        for task_id, runs in sorted(by_task.items())
    )
    verdict = (
        "Ready for this task pack"
        if source_supported_accuracy >= 0.8
        else "Needs fixes before shipping"
        if source_supported_accuracy >= 0.6
        else "High risk on this task pack"
    )
    caught = short_summary(issue_records)
    decision = decision_summary(
        source_supported=source_supported,
        scoreable_total=scoreable_total,
        exact_correct=exact_correct,
        oracle_skips=len(oracle_issue_records),
        issue_records=agent_issue_records,
    )
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
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:linear-gradient(180deg,#f8fbff 0,#ffffff 220px); }}
    .wrap {{ max-width:1440px; margin:0 auto; padding:22px 24px 44px; }}
    header {{ display:grid; grid-template-columns:minmax(0,1fr) 170px; gap:18px; align-items:start; }}
    h1 {{ margin:0 0 6px; font-size:28px; line-height:1.08; letter-spacing:0; }}
    h2 {{ margin:20px 0 10px; font-size:18px; letter-spacing:0; }}
    p {{ margin:0; color:var(--muted); line-height:1.5; }}
    code {{ font-family:"SFMono-Regular", Consolas, monospace; font-size:12px; }}
    .subhead {{ max-width:880px; font-size:14px; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:7px; margin-top:12px; }}
    .pill {{ border:1px solid var(--line); background:rgba(255,255,255,.88); border-radius:999px; padding:6px 9px; color:#344054; font-size:11px; font-weight:700; }}
    .verdict {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:13px; box-shadow:0 10px 28px rgba(15,23,42,.05); }}
    .score {{ font-size:34px; line-height:1; font-weight:850; color:{'var(--good)' if source_supported_accuracy >= .8 else 'var(--warn)' if source_supported_accuracy >= .6 else 'var(--bad)'}; }}
    .verdict-label {{ margin-top:6px; font-size:12px; font-weight:800; color:var(--ink); }}
    .grid {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:10px; margin-top:16px; }}
    .card {{ border:1px solid var(--line); background:var(--panel); border-radius:8px; padding:12px; box-shadow:0 7px 20px rgba(15,23,42,.035); }}
    .num {{ font-size:24px; line-height:1; font-weight:850; }}
    .label {{ color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.08em; margin-top:6px; font-weight:800; }}
    .metric-detail {{ color:var(--muted); font-size:11px; margin-top:5px; line-height:1.3; }}
    .insight {{ margin-top:16px; border:1px solid #c7d7fe; background:#eff6ff; border-radius:8px; padding:14px 16px; display:grid; grid-template-columns:128px minmax(0,1fr); gap:14px; align-items:start; }}
    .insight strong {{ color:#1d4ed8; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .method {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:16px; }}
    .method-card {{ border:1px solid var(--line); background:#fff; border-radius:8px; padding:14px 16px; }}
    .method-card strong {{ display:block; font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:#344054; margin-bottom:6px; }}
    .decision {{ margin-top:16px; border:1px solid #bfdbfe; background:#eff6ff; border-radius:8px; padding:16px; display:grid; grid-template-columns:150px minmax(0,1fr); gap:16px; align-items:start; }}
    .decision strong {{ color:#1d4ed8; font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .fix-grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:12px; }}
    .fix-card {{ border:1px solid var(--line); background:#fff; border-radius:8px; padding:12px; }}
    .fix-card strong {{ display:block; font-size:12px; color:#344054; margin-bottom:5px; }}
    .fix-card .count {{ font-size:22px; font-weight:850; margin-bottom:4px; }}
    .bar {{ display:flex; height:13px; overflow:hidden; border-radius:999px; background:#eef2f7; border:1px solid #e2e8f0; margin:12px 0 10px; }}
    .bar-part {{ min-width:2px; }}
    .badge-list {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:7px; }}
    .badge {{ display:inline-flex; align-items:center; border:1px solid var(--line); border-radius:999px; padding:3px 6px; font-size:10px; font-weight:850; color:#344054; background:#fff; }}
    .badge.good {{ border-color:#a7f3d0; background:#ecfdf3; color:#087f5b; }}
    .badge.bad {{ border-color:#fecaca; background:#fff1f2; color:#b42318; }}
    .badge.warn {{ border-color:#fed7aa; background:#fff7ed; color:#9a3412; }}
    .split {{ display:grid; grid-template-columns:.82fr 1.18fr; gap:22px; align-items:start; }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; box-shadow:0 8px 24px rgba(15,23,42,.04); }}
    th,td {{ text-align:left; padding:10px 11px; border-bottom:1px solid #e8ecf3; vertical-align:top; font-size:13px; }}
    th {{ font-size:10px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); background:#f7f9fc; font-weight:850; }}
    tr:last-child td {{ border-bottom:0; }}
    .pass,.fail {{ font-weight:850; }}
    .pass {{ color:var(--good); }}
    .fail {{ color:var(--bad); }}
    .muted {{ color:var(--muted); }}
    .answer {{ max-width:310px; white-space:pre-wrap; color:#344054; }}
    .question {{ color:var(--muted); font-size:12px; line-height:1.35; max-width:340px; margin-top:5px; }}
    .model {{ max-width:210px; overflow-wrap:anywhere; font-size:12px; color:#344054; }}
    .claim {{ font-weight:750; }}
    .truth {{ font-weight:750; color:#175cd3; }}
    .failure {{ color:var(--bad); font-weight:750; }}
    .fix-next {{ color:#344054; font-size:12px; line-height:1.35; max-width:220px; }}
    .source {{ color:#475467; font-size:12px; max-width:320px; overflow-wrap:anywhere; }}
    .citation-list {{ margin-top:6px; display:grid; gap:3px; }}
    details.debug {{ margin-top:8px; border:1px solid #e8ecf3; border-radius:8px; background:#f8fafc; padding:7px 8px; }}
    details.debug summary {{ cursor:pointer; color:var(--muted); font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }}
    .debug-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px 10px; margin-top:7px; font-size:11px; color:#475467; }}
    .debug-grid code {{ font-size:11px; overflow-wrap:anywhere; }}
    .required {{ font-weight:800; color:#344054; }}
    .catch-list {{ display:grid; gap:10px; }}
    .catch {{ border:1px solid var(--line); border-left:4px solid var(--bad); border-radius:8px; background:#fff; padding:13px 14px; }}
    .catch-title {{ display:flex; justify-content:space-between; gap:14px; align-items:center; margin-bottom:8px; }}
    .catch-title code {{ color:var(--bad); font-weight:800; }}
    .catch-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
    .mini-label {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; margin-bottom:3px; font-weight:800; }}
    .status-dot {{ display:inline-block; width:8px; height:8px; border-radius:999px; margin-right:8px; background:var(--muted); }}
    .status-dot.correct,.status-dot.source-supported-correct {{ background:var(--good); }}
    .status-dot.wrong-value,.status-dot.wrong-source,.status-dot.unsupported-citation,.status-dot.no-answer {{ background:var(--bad); }}
    .status-dot.correct-unsupported {{ background:var(--warn); }}
    footer {{ margin-top:24px; color:var(--muted); font-size:12px; }}
    @media(max-width:980px) {{ header,.split,.method,.decision,.fix-grid {{ grid-template-columns:1fr; }} .grid {{ grid-template-columns:1fr 1fr; }} .insight {{ grid-template-columns:1fr; }} th:nth-child(7),td:nth-child(7) {{ display:none; }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <header>
      <div>
        <h1>Agent Royale Eval Report</h1>
        <p class="subhead">This report shows whether one agent target returned exact values from required sources, whether the citations support those claims, and what to fix next.</p>
        <div class="meta">
          <span class="pill">target: {esc(target)}</span>
          <span class="pill">runs: {total}</span>
          <span class="pill">generated: {esc(created_at[:10])}</span>
        </div>
      </div>
      <div class="verdict">
        <div class="score">{source_supported_accuracy:.0%}</div>
        <div class="verdict-label">{esc(verdict)}</div>
        <p>Source-supported accuracy across {scoreable_total} scoreable task{'s' if scoreable_total != 1 else ''}</p>
      </div>
    </header>

    <section class="decision">
      <strong>Decision</strong>
      <p>{esc(decision)}</p>
    </section>

    <section class="grid">
      <div class="card"><div class="num">{source_supported}/{scoreable_total}</div><div class="label">Source-supported</div><div class="metric-detail">{source_supported_accuracy:.0%} strict pass rate</div></div>
      <div class="card"><div class="num">{exact_correct}/{scoreable_total}</div><div class="label">Exact values</div><div class="metric-detail">{accuracy:.0%} value match</div></div>
      <div class="card"><div class="num">{scoreable_total}/{total}</div><div class="label">Scoreable tasks</div><div class="metric-detail">oracle verified before grading</div></div>
      <div class="card"><div class="num">{len(oracle_issue_records)}</div><div class="label">Oracle skips (not scored)</div><div class="metric-detail">ground truth not safe</div></div>
      <div class="card"><div class="num">{fmt_ms(median_latency)}</div><div class="label">Median latency</div><div class="metric-detail">p95 {fmt_ms(p95_latency)}</div></div>
      <div class="card"><div class="num">{fmt_cost(total_cost)}</div><div class="label">Reported cost</div><div class="metric-detail">{len(costs)}/{total} runs reported cost</div></div>
    </section>

    <section class="method">
      <div class="method-card">
        <strong>Can I trust this run?</strong>
        <p>{esc(source_summary)}</p>
      </div>
      <div class="method-card">
        <strong>How scoring works</strong>
        <p>{esc(grading_summary)}</p>
      </div>
      <div class="method-card">
        <strong>Source support</strong>
        <p>Each citation URL is checked against the task's required source, and citation quotes must support the extracted claim. Correct values without source-backed quotes are separated from fully supported answers.</p>
      </div>
    </section>

    <section class="split">
      <div>
        <h2>What To Fix Next</h2>
        <div class="fix-grid">{fix_cards}</div>

        <h2>Outcome Breakdown</h2>
        {outcome_bar}
        <table><thead><tr><th>Outcome</th><th>Runs</th><th>Share</th><th>Fix next</th></tr></thead><tbody>{failure_rows}</tbody></table>

        <h2>Oracle Health</h2>
        <table><thead><tr><th>Status</th><th>Runs</th><th>Share</th><th>Meaning</th></tr></thead><tbody>{oracle_rows}</tbody></table>

        <h2>Representative Catches</h2>
        <div class="catch-list">{catch_cards or '<p class="muted">No failures in this run.</p>'}</div>
      </div>

      <div>
        <h2>Task-Level Results</h2>
        <table><thead><tr><th>Task</th><th>Exact</th><th>Source-supported</th><th>Observed outcomes</th></tr></thead><tbody>{task_rows}</tbody></table>
      </div>
    </section>

    <h2>Task Details</h2>
    <table>
      <colgroup>
        <col style="width:6%">
        <col style="width:22%">
        <col style="width:11%">
        <col style="width:15%">
        <col style="width:13%">
        <col style="width:11%">
        <col style="width:10%">
        <col style="width:7%">
        <col style="width:5%">
      </colgroup>
      <thead><tr><th>Status</th><th>Task</th><th>Stack / Target</th><th>Got</th><th>Expected</th><th>Source / Citation</th><th>Fix next</th><th>Latency</th><th>Cost</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>

    <footer>Generated from Agent Royale run data.</footer>
  </main>
</body>
</html>
"""
    output.write_text(html_text, encoding="utf-8")


def write_summary_json(records: list[RunRecord], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    total = len(records)
    scoreable = [record for record in records if record.scoreable]
    exact_correct = sum(1 for record in scoreable if record.passed)
    source_supported = sum(1 for record in scoreable if record_source_supported(record))
    payload = {
        "total_runs": total,
        "scoreable_runs": len(scoreable),
        "exact_correct": exact_correct,
        "exact_accuracy": exact_correct / len(scoreable) if scoreable else 0,
        "source_supported_correct": source_supported,
        "source_supported_accuracy": source_supported / len(scoreable) if scoreable else 0,
        "oracle_skips": total - len(scoreable),
        "outcomes": dict(Counter(record_verdict(record) for record in records)),
        "oracle_statuses": dict(Counter(record.oracle_status or "unknown" for record in records)),
        "tasks": [
            {
                "task_id": record.task_id,
                "task_pack_name": record.task_pack_name,
                "task_pack_version": record.task_pack_version,
                "task_hash": record.task_hash,
                "final_verdict": record_verdict(record),
                "value_correct": record.value_correct,
                "source_correct": record.source_correct,
                "citation_supports_claim": record.citation_supports_claim,
                "failure_mode": record.failure_mode,
                "required_source": record.required_source,
                "extracted_claim": record.extracted_claim,
                "ground_truth": record.ground_truth,
                "latency_ms": record.latency_ms,
                "error": record.error,
            }
            for record in records
        ],
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_junit_report(records: list[RunRecord], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    failures = [record for record in records if record_verdict(record) != "correct"]
    suite = ElementTree.Element(
        "testsuite",
        {
            "name": "agent-royale",
            "tests": str(len(records)),
            "failures": str(len(failures)),
            "errors": "0",
        },
    )
    for record in records:
        case = ElementTree.SubElement(
            suite,
            "testcase",
            {
                "classname": record.task_pack_name or "agent_royale",
                "name": record.task_id,
                "time": f"{record.latency_ms / 1000:.3f}" if record.latency_ms else "0",
            },
        )
        verdict = record_verdict(record)
        if verdict != "correct":
            failure = ElementTree.SubElement(
                case,
                "failure",
                {
                    "type": verdict,
                    "message": pretty_label(verdict),
                },
            )
            failure.text = (
                f"Question: {record.task_question}\n"
                f"Expected: {record.ground_truth}\n"
                f"Got: {record.extracted_claim or record.answer}\n"
                f"Required source: {record.required_source}\n"
                f"Error: {record.error or ''}"
            )
    tree = ElementTree.ElementTree(suite)
    ElementTree.indent(tree, space="  ")
    tree.write(output, encoding="utf-8", xml_declaration=True)


def render_record(record: RunRecord) -> str:
    verdict = record_verdict(record)
    if verdict == "wrong_source":
        status_label = "SOURCE FAIL"
    elif verdict in {"unsupported_citation", "correct_unsupported"}:
        status_label = "SOURCE ISSUE"
    elif record.passed:
        status_label = "PASS"
    else:
        status_label = "FAIL"
    status = f'<span class="{"pass" if verdict == "correct" else "fail"}">{status_label}</span>'
    answer_text = truncate_text(compact_text(record.answer or record.error or ""), 260)
    model = model_label(record)
    evidence = ""
    if record.ground_truth_snapshot and record.ground_truth_snapshot.evidence_text:
        evidence_text = truncate_text(record.ground_truth_snapshot.evidence_text, 140)
        evidence = f"<div class=\"muted\" style=\"font-size:11px;margin-top:4px\">Evidence: {esc(evidence_text)}</div>"
    oracle_status = pretty_label(record.oracle_status or "unknown")
    return (
        "<tr>"
        f"<td>{status}{render_quality_badges(record)}</td>"
        f"<td><code>{esc(record.task_id)}</code><div class=\"question\">{esc(record.task_question)}</div><div class=\"muted\" style=\"font-size:11px;margin-top:5px\">Oracle: {esc(oracle_status)}</div></td>"
        f"<td class=\"model\">{esc(model)}{render_tools(record)}</td>"
        f"<td class=\"answer\"><div class=\"mini-label\">Answer</div>{esc(answer_text)}<div class=\"mini-label\" style=\"margin-top:8px\">Claim</div><span class=\"claim\">{esc(record.extracted_claim)}</span>{render_debug(record)}</td>"
        f"<td class=\"truth\">{esc(record.ground_truth)}{evidence}</td>"
        f"<td class=\"source\">{render_citations(record)}</td>"
        f"<td class=\"fix-next\">{esc(fix_for_record(record))}</td>"
        f"<td>{esc(fmt_ms(record.latency_ms))}</td>"
        f"<td>{esc(fmt_cost(record.cost_usd))}</td>"
        "</tr>"
    )


def render_debug(record: RunRecord) -> str:
    trace = record.grading_trace or {}
    if not trace and not record.citation_checks:
        return ""
    claim = trace.get("normalized_claim", record.normalized_claim)
    truth = trace.get("normalized_truth", record.normalized_truth)
    comparison = trace.get("comparison", "")
    tolerance = trace.get("tolerance", "")
    citation_count = len(record.citation_checks)
    quote_support = sum(1 for item in record.citation_checks if item.get("quote_supports_claim"))
    source_matches = sum(1 for item in record.citation_checks if item.get("source_matches"))
    return (
        '<details class="debug">'
        "<summary>grading trace</summary>"
        '<div class="debug-grid">'
        f"<div>normalized claim</div><code>{esc(claim)}</code>"
        f"<div>normalized truth</div><code>{esc(truth)}</code>"
        f"<div>comparison</div><code>{esc(comparison)}</code>"
        f"<div>tolerance</div><code>{esc(tolerance)}</code>"
        f"<div>source matches</div><code>{source_matches}/{citation_count}</code>"
        f"<div>quote supports</div><code>{quote_support}/{citation_count}</code>"
        "</div></details>"
    )


def model_label(record: RunRecord) -> str:
    for value in record.search_queries:
        text = str(value).strip()
        if "/" in text and " " not in text:
            return text
    target = str(record.target)
    if target.startswith("openrouter:"):
        return target.removeprefix("openrouter:")
    return target


def render_tools(record: RunRecord) -> str:
    if not record.tools_used:
        return ""
    tools = ", ".join(record.tools_used[:2])
    if len(record.tools_used) > 2:
        tools += f", +{len(record.tools_used) - 2}"
    return f"<div class=\"muted\" style=\"font-size:11px;margin-top:5px\">tools: {esc(tools)}</div>"


def render_citations(record: RunRecord) -> str:
    required = (
        f"<div><span class=\"required\">Required:</span> {esc(record.required_source)}</div>"
        f"<div class=\"muted\" style=\"font-size:11px\">Source match: {yes_no(record.source_correct)}; quote support: {yes_no(record.citation_supports_claim)}</div>"
    )
    if not record.citations:
        return required + "<div class=\"citation-list muted\">No citations returned</div>"
    citation_rows = []
    for citation in record.citations[:3]:
        citation_rows.append(f"<div>{esc(compact_url(citation.url))}</div>")
    if len(record.citations) > 3:
        citation_rows.append(f"<div class=\"muted\">+{len(record.citations) - 3} more</div>")
    return required + f"<div class=\"citation-list\"><span class=\"required\">Cited:</span>{''.join(citation_rows)}</div>"


def render_catch(record: RunRecord) -> str:
    cited = ", ".join(citation_domain(item.url) for item in record.citations[:2]) or "none"
    return (
        "<div class=\"catch\">"
        f"<div class=\"catch-title\"><code>{esc(record.task_id)}</code><span class=\"failure\">{esc(pretty_label(record_verdict(record)))}</span></div>"
        "<div class=\"catch-grid\">"
        f"<div><div class=\"mini-label\">Agent said</div><div class=\"claim\">{esc(record.extracted_claim)}</div></div>"
        f"<div><div class=\"mini-label\">Oracle had</div><div class=\"truth\">{esc(record.ground_truth)}</div></div>"
        "</div>"
        f"<p class=\"muted\" style=\"margin-top:8px;font-size:12px\">Required source: {esc(record.required_source)}</p>"
        f"<p class=\"muted\" style=\"margin-top:3px;font-size:12px\">Agent cited: {esc(cited)}</p>"
        f"<p class=\"muted\" style=\"margin-top:3px;font-size:12px\">Fix next: {esc(fix_for_record(record))}</p>"
        "</div>"
    )


def short_summary(records: list[RunRecord]) -> str:
    if not records:
        return "Every answer matched the independent oracle and source-support check for this run."
    modes = Counter(record_verdict(record) for record in records)
    parts = []
    if modes.get("wrong_source"):
        parts.append("source drift")
    if modes.get("wrong_value"):
        parts.append("stale or incorrect values")
    if modes.get("unsupported_citation"):
        parts.append("answers whose citations did not support the claim")
    if modes.get("correct_unsupported"):
        parts.append("correct values without source-backed citation quotes")
    if modes.get("no_answer"):
        parts.append("missing answers")
    if not parts:
        parts.append("failed assertions")
    examples = ", ".join(record.task_id for record in records[:2])
    return f"{len(records)} task{'s' if len(records) != 1 else ''} had issues: {', '.join(parts)}. Examples: {examples}."


def decision_summary(
    *,
    source_supported: int,
    scoreable_total: int,
    exact_correct: int,
    oracle_skips: int,
    issue_records: list[RunRecord],
) -> str:
    if not scoreable_total:
        return "No tasks were scoreable because the oracle could not verify ground truth. Run audit-errors and fix the task bank before judging the target."
    issue_text = short_summary(issue_records)
    skip_text = (
        f" {oracle_skips} task{'s were' if oracle_skips != 1 else ' was'} skipped because ground truth was not safe to score."
        if oracle_skips
        else " No oracle skips were recorded."
    )
    return (
        f"{source_supported}/{scoreable_total} scoreable tasks were correct with source-backed citations; "
        f"{exact_correct}/{scoreable_total} matched the exact oracle value. {issue_text}{skip_text}"
    )


def render_fix_cards(records: list[RunRecord]) -> str:
    groups: dict[str, dict[str, object]] = {}
    for record in records:
        key = fix_for_record(record)
        if key == "No action needed.":
            continue
        if key not in groups:
            groups[key] = {
                "count": 0,
                "examples": [],
                "reason": fix_reason_for_record(record),
            }
        groups[key]["count"] = int(groups[key]["count"]) + 1
        examples = groups[key]["examples"]
        if isinstance(examples, list) and len(examples) < 2:
            examples.append(record.task_id)
    if not groups:
        return '<div class="fix-card"><div class="count">0</div><strong>No fixes needed</strong><p class="muted">All scoreable tasks passed exact and source-supported checks.</p></div>'
    ranked = sorted(groups.items(), key=lambda item: (-int(item[1]["count"]), item[0]))[:3]
    cards = []
    for action, data in ranked:
        examples = data["examples"] if isinstance(data["examples"], list) else []
        examples_text = ", ".join(str(item) for item in examples)
        cards.append(
            "<div class=\"fix-card\">"
            f"<div class=\"count\">{data['count']}</div>"
            f"<strong>{esc(action)}</strong>"
            f"<p class=\"muted\">{esc(data['reason'])}</p>"
            f"<p class=\"muted\" style=\"margin-top:6px;font-size:11px\">Examples: {esc(examples_text or 'n/a')}</p>"
            "</div>"
        )
    return "".join(cards)


def render_outcome_bar(counts: Counter, total: int) -> str:
    if not total:
        return ""
    colors = {
        "correct": "var(--good)",
        "wrong_value": "var(--bad)",
        "wrong_source": "#e11d48",
        "unsupported_citation": "var(--warn)",
        "correct_unsupported": "#f59e0b",
        "no_answer": "#7c2d12",
        "tool_failure": "#64748b",
        "oracle_failed": "#64748b",
        "selector_broken": "#a855f7",
        "source_unreachable": "#6b7280",
        "ground_truth_ambiguous": "#8b5cf6",
    }
    parts = []
    legend = []
    for name, count in counts.most_common():
        width = max(1, count / total * 100)
        color = colors.get(str(name), "#94a3b8")
        parts.append(f'<div class="bar-part" title="{esc(pretty_label(name))}: {count}" style="width:{width:.2f}%;background:{color}"></div>')
        legend.append(f'<span class="badge"><span class="status-dot {status_class(name)}"></span>{esc(pretty_label(name))}: {count}</span>')
    return f'<div class="bar">{"".join(parts)}</div><div class="badge-list">{"".join(legend)}</div>'


def render_quality_badges(record: RunRecord) -> str:
    badges = [
        quality_badge("Value", record.value_correct),
        quality_badge("Source", record.source_correct),
        quality_badge("Quote", record.citation_supports_claim),
    ]
    if record.scoreable:
        badges.append('<span class="badge good">Oracle verified</span>' if record.oracle_status == "verified" else '<span class="badge warn">Oracle unknown</span>')
    else:
        badges.append('<span class="badge warn">Not scored</span>')
    return f'<div class="badge-list">{"".join(badges)}</div>'


def quality_badge(label: str, value: bool) -> str:
    return f'<span class="badge {"good" if value else "bad"}">{esc(label)}: {"yes" if value else "no"}</span>'


def fix_for_record(record: RunRecord) -> str:
    if not record.scoreable:
        return fix_for_oracle_status(record.oracle_status or record.failure_mode or record.outcome)
    return fix_for_verdict(record_verdict(record))


def fix_reason_for_record(record: RunRecord) -> str:
    if not record.scoreable:
        return "The target was not scored because Agent Royale could not verify one supported ground-truth value."
    verdict = record_verdict(record)
    reasons = {
        "wrong_value": "The agent returned a value that did not match the oracle.",
        "wrong_source": "The answer came from outside the required source policy.",
        "unsupported_citation": "The citation did not contain quote evidence for the claim.",
        "correct_unsupported": "The value matched, but source/citation support was weak.",
        "no_answer": "The target returned no usable answer.",
        "tool_failure": "The target or tool failed before returning a usable answer.",
    }
    return reasons.get(verdict, "Inspect the row details and grading trace.")


def fix_for_verdict(value: object) -> str:
    actions = {
        "correct": "No action needed.",
        "source_supported_correct": "No action needed.",
        "wrong_value": "Improve extraction, freshness, or field selection.",
        "wrong_source": "Tighten source routing or allowed sources.",
        "unsupported_citation": "Require quote evidence that supports the claim.",
        "correct_unsupported": "Strengthen citation quote support.",
        "no_answer": "Add retries, fallback tools, or target error handling.",
        "tool_failure": "Inspect adapter/tool logs and retry behavior.",
        "oracle_failed": "Run audit-errors and fix the oracle path.",
        "selector_broken": "Update parser or add tighter context.",
        "source_unreachable": "Try structured, HTML, browser, or alternate oracle path.",
        "ground_truth_ambiguous": "Split the task or require narrower context.",
        "low_confidence": "Strengthen oracle evidence or policy checks.",
    }
    return actions.get(str(value), "Inspect row details.")


def fix_for_oracle_status(value: object) -> str:
    actions = {
        "verified": "Ground truth verified.",
        "unknown": "Older run; regenerate with oracle snapshots.",
        "low_confidence": "Strengthen evidence or policy checks.",
        "conflicting_values": "Split task or narrow parser context.",
        "source_unreachable": "Try structured, HTML, browser, or alternate oracle path.",
        "selector_broken": "Update parser or source-specific selector.",
        "ground_truth_ambiguous": "Require one candidate with tighter context.",
        "oracle_failed": "Inspect credentials, adapter config, or raw error.",
    }
    return actions.get(str(value), "Inspect oracle snapshot.")


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


def percentile(values: list[float], target: int) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * target / 100)
    return ordered[min(max(index, 0), len(ordered) - 1)]


def fmt_ms(value: float | None) -> str:
    if not value:
        return "n/a"
    if value >= 1000:
        return f"{value / 1000:.1f}s"
    return f"{value:.0f}ms"


def fmt_cost(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value == 0:
        return "$0"
    if value < 0.01:
        return f"${value:.4f}"
    return f"${value:.2f}"


def citation_domain(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    return parsed.netloc.lower().removeprefix("www.") or text.lower()


def compact_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"https://{text}")
    domain = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    if not domain:
        return truncate_text(text, 90)
    return truncate_text(domain + path, 90)


def pretty_label(value: object) -> str:
    labels = {
        "source_supported_correct": "correct with source support",
        "correct_unsupported": "correct value, weak citation",
        "unsupported_citation": "unsupported citation",
        "wrong_source": "wrong source",
        "wrong_value": "wrong value",
        "no_answer": "no answer returned",
        "tool_failure": "tool failure",
        "verified": "verified",
        "low_confidence": "low confidence",
        "conflicting_values": "conflicting values",
        "source_unreachable": "source unreachable",
        "selector_broken": "selector broken",
        "ground_truth_ambiguous": "ground truth ambiguous",
        "oracle_failed": "oracle failed",
        "correct": "correct",
    }
    text = str(value)
    return labels.get(text, text.replace("_", " "))


def record_verdict(record: RunRecord) -> str:
    if record.final_verdict:
        return record.final_verdict
    if not record.scoreable:
        return record.failure_mode or record.outcome or "oracle_failed"
    if record.passed and not record.failure_mode:
        return "correct"
    if record.passed and record.failure_mode:
        return "correct_unsupported"
    return record.failure_mode or record.outcome or "failed"


def record_source_supported(record: RunRecord) -> bool:
    if record.citation_supports_claim:
        return bool(record.passed)
    return bool(record.passed and not record.failure_mode and record.citation_supported)


def yes_no(value: object) -> str:
    return "yes" if value else "no"


def status_class(value: object) -> str:
    return str(value).replace("_", "-")


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""))


def compact_text(value: object) -> str:
    return " ".join(str(value if value is not None else "").split())


def truncate_text(value: object, limit: int) -> str:
    text = str(value if value is not None else "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def pct(count: int, total: int) -> str:
    return f"{(count / total):.0%}" if total else "0%"
