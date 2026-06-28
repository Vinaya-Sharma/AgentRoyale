from backend.bright_data import BrightDataResult
from backend.bright_data import fallback_endpoints
from backend.bright_data import result_error_content
from backend.bright_data import structured_ecommerce_endpoint
import asyncio
from types import SimpleNamespace

from agent_royale.ground_truth import fetch_bright_data_regex_snapshot
from agent_royale.schema import GroundTruthSpec, Task


def bright_data_result(*, content=None, structured_content=None, is_error=False, error=None):
    return BrightDataResult(
        endpoint="web_data_bestbuy_products",
        parameters={},
        retrieved_at="2026-06-23T12:00:00+00:00",
        content=content or [],
        structured_content=structured_content,
        raw={},
        is_error=is_error,
        error=error,
    )


def test_bestbuy_url_prefers_structured_tool_before_scrape_fallbacks() -> None:
    url = "https://www.bestbuy.com/site/example-product/12345.p"

    assert structured_ecommerce_endpoint(url) == "web_data_bestbuy_products"
    assert fallback_endpoints("scrape_as_markdown", url) == [
        "web_data_bestbuy_products",
        "scrape_as_markdown",
        "scrape_as_html",
        "direct_http",
    ]


def test_structured_error_payload_is_not_usable_content() -> None:
    result = bright_data_result(
        content=[
            {
                "type": "text",
                "text": '[{"error":"Crawler error: Navigation failed","error_code":"net_err_http2_protocol_error"}]',
            }
        ],
    )

    assert result_error_content(result) == "Crawler error: Navigation failed"


def test_structured_content_error_is_not_usable_content() -> None:
    result = bright_data_result(
        structured_content=[{"error": "Crawler error", "error_code": "net_err"}],
    )

    assert result_error_content(result) == "Crawler error"


def test_non_error_text_remains_usable() -> None:
    result = bright_data_result(content=[{"type": "text", "text": "<html>Price: $19.99</html>"}])

    assert result_error_content(result) == ""


def test_regex_oracle_continues_to_fallback_after_selector_miss(monkeypatch) -> None:
    task = Task(
        id="samsung_512gb_price",
        question="What is the Samsung price?",
        required_source="https://www.samsung.com/example",
        answer_type="currency",
        tolerance=0,
        ground_truth=GroundTruthSpec(
            method="bright_data",
            tool="scrape_as_markdown",
            url="https://www.samsung.com/example",
            regex=r'"sku"\s*:\s*"SM-S938UZKEXAA"[\s\S]{0,120}?"price"\s*:\s*"([0-9,]+(?:\.[0-9]{2})?)"',
            require_near_text=["SM-S938UZKEXAA"],
            source_url="https://www.samsung.com/example",
        ),
    )
    responses = {
        "scrape_as_markdown": BrightDataResult(
            endpoint="scrape_as_markdown",
            parameters={},
            retrieved_at="2026-06-28T12:00:00+00:00",
            content=[{"type": "text", "text": "Storage Storage 256GB 512GB 1TB"}],
            structured_content=None,
            raw={},
        ),
        "scrape_as_html": BrightDataResult(
            endpoint="scrape_as_html",
            parameters={},
            retrieved_at="2026-06-28T12:00:00+00:00",
            content=[
                {
                    "type": "text",
                    "text": '{"sku":"SM-S938UZKEXAA","offers":{"price":"1419.99"}}',
                }
            ],
            structured_content=None,
            raw={"final_url": "https://www.samsung.com/example"},
        ),
    }

    async def fake_fetch_url(endpoint, url):
        return responses[endpoint]

    monkeypatch.setattr("backend.config.get_settings", lambda: SimpleNamespace(bright_data_api_key="token"))
    monkeypatch.setattr("backend.bright_data.fetch_url", fake_fetch_url)

    snapshot = asyncio.run(fetch_bright_data_regex_snapshot(task, fetched_at="2026-06-28T12:00:00+00:00"))

    assert snapshot.status == "verified"
    assert snapshot.value == "1419.99"
    assert snapshot.tool == "scrape_as_html"
    assert snapshot.validation_checks["fallback_after_failed_attempts"] is True
