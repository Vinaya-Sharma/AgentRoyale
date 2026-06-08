import json
import tempfile
from pathlib import Path

from agent_royale.ground_truth import verified_snapshot
from agent_royale.report import write_junit_report, write_summary_json
from agent_royale.runner import check_citations
from agent_royale.schema import Citation, GroundTruthSpec, RunRecord, Task


def task(**extra) -> Task:
    payload = {
        "id": "reliability_task",
        "question": "Using Example, what is the value?",
        "required_source": "example.com/source",
        "answer_type": "string",
        "tolerance": 0,
        "ground_truth": GroundTruthSpec(method="static", value="alpha"),
    }
    payload.update(extra)
    return Task(**payload)


def test_oracle_policy_rejects_evidence_without_value() -> None:
    item = task()
    snapshot = verified_snapshot(
        item,
        value="alpha",
        source_url="example.com/source",
        fetched_at="2026-06-08T12:00:00+00:00",
        parser="static",
        evidence_text="beta",
        raw_excerpt="beta",
    )

    assert snapshot.status == "low_confidence"
    assert snapshot.validation_checks["policy_evidence_contains_value"] is False


def test_oracle_policy_rejects_multiple_regex_candidates() -> None:
    item = task()
    snapshot = verified_snapshot(
        item,
        value="alpha",
        source_url="example.com/source",
        fetched_at="2026-06-08T12:00:00+00:00",
        parser="regex",
        evidence_text="alpha",
        raw_excerpt="alpha",
        validation_checks={"single_candidate": False},
    )

    assert snapshot.status == "ground_truth_ambiguous"
    assert "policy_single_candidate_failed" in snapshot.ambiguity_flags


def test_source_policy_can_require_same_path() -> None:
    item = task(source_policy={"match": "same_path"})
    good = check_citations(
        [Citation(url="https://example.com/source?utm=1", quote="alpha")],
        task=item,
        claim="alpha",
    )
    bad = check_citations(
        [Citation(url="https://example.com/other", quote="alpha")],
        task=item,
        claim="alpha",
    )

    assert good["source_correct"]
    assert not bad["source_correct"]


def test_task_hash_ignores_pack_metadata() -> None:
    left = task(task_pack_name="a", task_pack_version="1")
    right = task(task_pack_name="b", task_pack_version="2")

    assert left.stable_hash() == right.stable_hash()


def test_summary_and_junit_exports() -> None:
    record = RunRecord(
        run_id="run",
        task_id="reliability_task",
        task_question="Question?",
        target="target",
        answer="alpha",
        extracted_claim="alpha",
        ground_truth="alpha",
        oracle_status="verified",
        scoreable=True,
        value_correct=True,
        source_correct=True,
        citation_supports_claim=True,
        final_verdict="correct",
        normalized_claim="alpha",
        normalized_truth="alpha",
        grading_trace={"comparison": "normalized_exact"},
        citation_checks=[{"source_matches": True, "quote_supports_claim": True}],
        passed=True,
        outcome="correct",
        required_source="example.com/source",
        latency_ms=12.3,
        created_at="2026-06-08T12:00:00+00:00",
    )
    tmp_path = Path(tempfile.mkdtemp())
    summary = tmp_path / "summary.json"
    junit = tmp_path / "junit.xml"

    write_summary_json([record], summary)
    write_junit_report([record], junit)

    payload = json.loads(summary.read_text())
    assert payload["exact_accuracy"] == 1
    assert payload["source_supported_accuracy"] == 1
    assert "tests=\"1\"" in junit.read_text()
