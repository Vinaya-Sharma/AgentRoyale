from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

from agent_royale.report import load_records
from agent_royale.schema import RunRecord


@dataclass(frozen=True)
class TaskComparison:
    task_id: str
    before_exact_rate: float
    after_exact_rate: float
    before_supported_rate: float
    after_supported_rate: float
    before_scoreable: int
    after_scoreable: int
    before_outcomes: tuple[str, ...]
    after_outcomes: tuple[str, ...]
    latency_delta_ms: float | None

    @property
    def exact_delta(self) -> float:
        return self.after_exact_rate - self.before_exact_rate

    @property
    def supported_delta(self) -> float:
        return self.after_supported_rate - self.before_supported_rate

    @property
    def regressed(self) -> bool:
        return self.after_supported_rate < self.before_supported_rate

    @property
    def improved(self) -> bool:
        return self.after_supported_rate > self.before_supported_rate


@dataclass(frozen=True)
class RunComparison:
    before_path: Path
    after_path: Path
    before_records: int
    after_records: int
    before_scoreable: int
    after_scoreable: int
    before_exact_rate: float
    after_exact_rate: float
    before_supported_rate: float
    after_supported_rate: float
    before_oracle_skips: int
    after_oracle_skips: int
    before_median_latency_ms: float | None
    after_median_latency_ms: float | None
    before_cost_usd: float | None
    after_cost_usd: float | None
    added_tasks: tuple[str, ...]
    removed_tasks: tuple[str, ...]
    task_comparisons: tuple[TaskComparison, ...]

    @property
    def exact_delta(self) -> float:
        return self.after_exact_rate - self.before_exact_rate

    @property
    def supported_delta(self) -> float:
        return self.after_supported_rate - self.before_supported_rate

    @property
    def regressions(self) -> tuple[TaskComparison, ...]:
        return tuple(item for item in self.task_comparisons if item.regressed)

    @property
    def improvements(self) -> tuple[TaskComparison, ...]:
        return tuple(item for item in self.task_comparisons if item.improved)


def compare_run_files(before_path: Path, after_path: Path) -> RunComparison:
    before = load_records(before_path)
    after = load_records(after_path)
    before_by_task = group_by_task(before)
    after_by_task = group_by_task(after)
    before_ids = set(before_by_task)
    after_ids = set(after_by_task)
    common_ids = sorted(before_ids & after_ids)
    task_comparisons = tuple(
        compare_task(task_id, before_by_task[task_id], after_by_task[task_id]) for task_id in common_ids
    )
    return RunComparison(
        before_path=before_path,
        after_path=after_path,
        before_records=len(before),
        after_records=len(after),
        before_scoreable=count_scoreable(before),
        after_scoreable=count_scoreable(after),
        before_exact_rate=exact_rate(before),
        after_exact_rate=exact_rate(after),
        before_supported_rate=supported_rate(before),
        after_supported_rate=supported_rate(after),
        before_oracle_skips=count_oracle_skips(before),
        after_oracle_skips=count_oracle_skips(after),
        before_median_latency_ms=median_latency(before),
        after_median_latency_ms=median_latency(after),
        before_cost_usd=total_cost(before),
        after_cost_usd=total_cost(after),
        added_tasks=tuple(sorted(after_ids - before_ids)),
        removed_tasks=tuple(sorted(before_ids - after_ids)),
        task_comparisons=task_comparisons,
    )


def group_by_task(records: list[RunRecord]) -> dict[str, list[RunRecord]]:
    grouped: dict[str, list[RunRecord]] = {}
    for record in records:
        grouped.setdefault(record.task_id, []).append(record)
    return grouped


def compare_task(task_id: str, before: list[RunRecord], after: list[RunRecord]) -> TaskComparison:
    return TaskComparison(
        task_id=task_id,
        before_exact_rate=exact_rate(before),
        after_exact_rate=exact_rate(after),
        before_supported_rate=supported_rate(before),
        after_supported_rate=supported_rate(after),
        before_scoreable=count_scoreable(before),
        after_scoreable=count_scoreable(after),
        before_outcomes=outcomes(before),
        after_outcomes=outcomes(after),
        latency_delta_ms=latency_delta(before, after),
    )


def exact_rate(records: list[RunRecord]) -> float:
    scoreable = [record for record in records if record.scoreable]
    if not scoreable:
        return 0
    return sum(1 for record in scoreable if record.passed) / len(scoreable)


def supported_rate(records: list[RunRecord]) -> float:
    scoreable = [record for record in records if record.scoreable]
    if not scoreable:
        return 0
    return sum(1 for record in scoreable if source_supported(record)) / len(scoreable)


def count_scoreable(records: list[RunRecord]) -> int:
    return sum(1 for record in records if record.scoreable)


def count_oracle_skips(records: list[RunRecord]) -> int:
    return sum(1 for record in records if not record.scoreable)


def median_latency(records: list[RunRecord]) -> float | None:
    latencies = [record.latency_ms for record in records if record.latency_ms]
    return median(latencies) if latencies else None


def latency_delta(before: list[RunRecord], after: list[RunRecord]) -> float | None:
    before_median = median_latency(before)
    after_median = median_latency(after)
    if before_median is None or after_median is None:
        return None
    return after_median - before_median


def total_cost(records: list[RunRecord]) -> float | None:
    costs = [record.cost_usd for record in records if record.cost_usd is not None]
    return sum(costs) if costs else None


def outcomes(records: list[RunRecord]) -> tuple[str, ...]:
    names = {record_verdict(record) for record in records}
    return tuple(sorted(names))


def source_supported(record: RunRecord) -> bool:
    if record.citation_supports_claim:
        return bool(record.passed)
    return bool(record.passed and not record.failure_mode and record.citation_supported)


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


def render_terminal_summary(comparison: RunComparison) -> str:
    lines = [
        "Agent Royale comparison",
        f"Before: {comparison.before_path}",
        f"After:  {comparison.after_path}",
        "",
        f"Exact accuracy: {pct(comparison.before_exact_rate)} -> {pct(comparison.after_exact_rate)} ({signed_pct(comparison.exact_delta)})",
        f"Source-supported: {pct(comparison.before_supported_rate)} -> {pct(comparison.after_supported_rate)} ({signed_pct(comparison.supported_delta)})",
        f"Scoreable runs: {comparison.before_scoreable} -> {comparison.after_scoreable}",
        f"Oracle skips: {comparison.before_oracle_skips} -> {comparison.after_oracle_skips}",
    ]
    if comparison.before_median_latency_ms is not None and comparison.after_median_latency_ms is not None:
        delta = comparison.after_median_latency_ms - comparison.before_median_latency_ms
        lines.append(
            f"Median latency: {comparison.before_median_latency_ms:.0f} ms -> {comparison.after_median_latency_ms:.0f} ms ({signed_ms(delta)})"
        )
    if comparison.before_cost_usd is not None or comparison.after_cost_usd is not None:
        lines.append(f"Total cost: {money(comparison.before_cost_usd)} -> {money(comparison.after_cost_usd)}")
    lines.extend(["", f"Regressions: {len(comparison.regressions)}"])
    for item in comparison.regressions[:8]:
        lines.append(
            f"- {item.task_id}: {pct(item.before_supported_rate)} -> {pct(item.after_supported_rate)} "
            f"({', '.join(item.before_outcomes)} -> {', '.join(item.after_outcomes)})"
        )
    lines.append(f"Improvements: {len(comparison.improvements)}")
    for item in comparison.improvements[:8]:
        lines.append(
            f"- {item.task_id}: {pct(item.before_supported_rate)} -> {pct(item.after_supported_rate)} "
            f"({', '.join(item.before_outcomes)} -> {', '.join(item.after_outcomes)})"
        )
    if comparison.added_tasks:
        lines.extend(["", "Added tasks:", *[f"- {task_id}" for task_id in comparison.added_tasks]])
    if comparison.removed_tasks:
        lines.extend(["", "Removed tasks:", *[f"- {task_id}" for task_id in comparison.removed_tasks]])
    return "\n".join(lines)


def render_markdown_report(comparison: RunComparison) -> str:
    rows = [
        "| Task | Source-supported before | Source-supported after | Exact before | Exact after | Outcomes |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for item in comparison.task_comparisons:
        rows.append(
            "| "
            + " | ".join(
                [
                    f"`{item.task_id}`",
                    pct(item.before_supported_rate),
                    pct(item.after_supported_rate),
                    pct(item.before_exact_rate),
                    pct(item.after_exact_rate),
                    f"{', '.join(item.before_outcomes)} -> {', '.join(item.after_outcomes)}",
                ]
            )
            + " |"
        )
    return "\n".join(
        [
            "# Agent Royale Comparison",
            "",
            f"- Before: `{comparison.before_path}`",
            f"- After: `{comparison.after_path}`",
            f"- Exact accuracy: {pct(comparison.before_exact_rate)} -> {pct(comparison.after_exact_rate)} ({signed_pct(comparison.exact_delta)})",
            f"- Source-supported accuracy: {pct(comparison.before_supported_rate)} -> {pct(comparison.after_supported_rate)} ({signed_pct(comparison.supported_delta)})",
            f"- Scoreable runs: {comparison.before_scoreable} -> {comparison.after_scoreable}",
            f"- Oracle skips: {comparison.before_oracle_skips} -> {comparison.after_oracle_skips}",
            f"- Regressions: {len(comparison.regressions)}",
            f"- Improvements: {len(comparison.improvements)}",
            "",
            "## Task Changes",
            "",
            *rows,
            "",
        ]
    )


def pct(value: float) -> str:
    return f"{value:.1%}"


def signed_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1%}"


def signed_ms(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.0f} ms"


def money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"${value:.4f}"
