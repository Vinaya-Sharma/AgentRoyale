from agent_royale.grading import extract_claim, grade
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
