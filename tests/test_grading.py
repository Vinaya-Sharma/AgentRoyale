from agent_royale.grading import extract_claim, grade, grade_with_trace
from agent_royale.runner import check_citations, classify_failure, final_verdict_for
from agent_royale.schema import Citation
from agent_royale.schema import GroundTruthSpec, Task


def string_task(answer_type: str = "string") -> Task:
    return Task(
        id="claim_extract",
        question="What exact value is listed?",
        required_source="example.com/source",
        answer_type=answer_type,
        tolerance=0,
        ground_truth=GroundTruthSpec(method="static", value="pnpm@10.33.0"),
    )


def test_extracts_code_formatted_package_manager_value() -> None:
    answer = 'The current packageManager value is:\n\n`"packageManager": "pnpm@9.15.4"` [1]'

    assert extract_claim(answer, "string", "pnpm@10.33.0") == "pnpm@9.15.4"


def test_extracts_version_without_citation_marker() -> None:
    assert extract_claim("v1.58.0 [1]", "string", "v1.60.0") == "v1.58.0"


def test_unwraps_json_answer_null_as_empty_claim() -> None:
    answer = '{"query":"latest release","answer":null,"results":[]}'

    assert extract_claim(answer, "string", "v1.60.0") == ""


def test_prefers_value_after_answer_phrase_before_context_tokens() -> None:
    answer = "The packageManager value in the canary Next.js package.json is npm."

    assert extract_claim(answer, "string", "pnpm@10.33.0") == "npm"


def test_grade_uses_oracle_match_as_display_claim_for_string_answer() -> None:
    task = string_task()
    passed, claim, normalized_claim, normalized_truth = grade(
        task,
        "pnpm@10.33.0",
        'The packageManager value is "pnpm@10.33.0".',
    )

    assert passed
    assert claim == "pnpm@10.33.0"
    assert normalized_claim == normalized_truth


def test_grade_with_trace_explains_numeric_tolerance() -> None:
    task = string_task("currency")
    result = grade_with_trace(task, "$19.00", "The price is $19.")

    assert result["passed"]
    assert result["trace"]["comparison"] == "numeric_abs_tolerance"
    assert result["trace"]["normalized_claim"] == 19.0
    assert result["trace"]["normalized_truth"] == 19.0
    assert result["trace"]["tolerance"] == 0.0


def test_citation_check_requires_source_and_quote_support() -> None:
    task = string_task()
    result = check_citations(
        [
            Citation(url="https://example.com/source?utm=1", quote="The listed value is pnpm@10.33.0."),
            Citation(url="https://other.example/source", quote="pnpm@10.33.0"),
        ],
        task=task,
        claim="pnpm@10.33.0",
    )

    assert result["source_correct"]
    assert result["citation_supports_claim"]
    assert result["checks"][0]["source_matches"]
    assert result["checks"][0]["quote_supports_claim"]
    assert not result["checks"][1]["source_matches"]


def test_correct_value_without_support_gets_explicit_verdict() -> None:
    failure_mode = classify_failure(
        passed=True,
        answer="pnpm@10.33.0",
        claim="pnpm@10.33.0",
        source_correct=False,
        citation_supported=False,
        required_source="example.com/source",
        citations=[],
    )

    assert failure_mode == "unsupported_citation"
    assert final_verdict_for(passed=True, failure_mode=failure_mode, scoreable=True) == "correct_unsupported"
