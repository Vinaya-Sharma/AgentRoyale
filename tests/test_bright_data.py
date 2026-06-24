from backend.bright_data import BrightDataResult
from backend.bright_data import fallback_endpoints
from backend.bright_data import result_error_content
from backend.bright_data import structured_ecommerce_endpoint


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
