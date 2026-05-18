from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from backend.config import get_settings


@dataclass
class BrightDataResult:
    endpoint: str
    parameters: dict[str, Any]
    retrieved_at: str
    content: list[dict[str, Any]]
    structured_content: dict[str, Any] | list[Any] | None
    raw: dict[str, Any]
    is_error: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _block_to_dict(block: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"type": getattr(block, "type", block.__class__.__name__)}
    for key in ("text", "data", "mimeType", "url", "title"):
        if hasattr(block, key):
            data[key] = getattr(block, key)
    return data


def args_for_tool(endpoint: str, url: str) -> dict[str, Any]:
    if endpoint == "web_data_amazon_product":
        return {"url": url}
    if endpoint == "web_data_linkedin_company_profile":
        return {"url": url}
    if endpoint == "web_data_amazon_product_search":
        return {"keyword": url, "url": "https://www.amazon.com/s?k="}
    return {"url": url}


def fallback_endpoints(primary: str) -> list[str]:
    chain = [primary]
    for endpoint in ("scrape_as_markdown", "scrape_as_html", "direct_http"):
        if endpoint not in chain:
            chain.append(endpoint)
    return chain


async def fetch_url_with_fallbacks(endpoint: str, url: str) -> BrightDataResult:
    failures: list[str] = []
    last_result: BrightDataResult | None = None
    for candidate in fallback_endpoints(endpoint):
        result = await fetch_url(candidate, url)
        last_result = result
        has_content = bool(result_text(result, limit=1))
        if not result.is_error and has_content:
            if candidate != endpoint:
                result.raw["fallback_from"] = endpoint
                result.raw["fallback_failures"] = failures
            return result
        failures.append(f"{candidate}: {result.error or 'empty response'}")
    assert last_result is not None
    last_result.error = "; ".join(failures)
    last_result.raw["fallback_failures"] = failures
    return last_result


async def fetch_url(endpoint: str, url: str) -> BrightDataResult:
    settings = get_settings()
    params = args_for_tool(endpoint, url)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    if endpoint == "direct_http":
        return await _fetch_direct_http(url, params, retrieved_at)

    attempts = max(settings.bright_data_retries, 0) + 1
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        try:
            async with asyncio.timeout(settings.bright_data_timeout_seconds):
                response = await _call_tool(
                    settings.bright_data_mcp_url_with_token,
                    endpoint,
                    params,
                )
            if response is None:
                raise RuntimeError(f"Bright Data endpoint {endpoint} returned no response")
            response_content = getattr(response, "content", None) or []
            content = [_block_to_dict(block) for block in response_content]
            return BrightDataResult(
                endpoint=endpoint,
                parameters=params,
                retrieved_at=retrieved_at,
                content=content,
                structured_content=getattr(response, "structuredContent", None),
                raw={
                    "content": content,
                    "structured_content": getattr(response, "structuredContent", None),
                    "is_error": bool(getattr(response, "isError", False)),
                    "attempt_count": attempt,
                },
                is_error=bool(getattr(response, "isError", False)),
            )
        except TimeoutError:
            last_error = f"Bright Data request timed out after {settings.bright_data_timeout_seconds:.0f}s"
        except Exception as exc:
            last_error = str(exc)
    return BrightDataResult(
        endpoint=endpoint,
        parameters=params,
        retrieved_at=retrieved_at,
        content=[],
        structured_content=None,
        raw={"error": last_error, "attempt_count": attempts},
        is_error=True,
        error=last_error,
    )


async def _fetch_direct_http(
    url: str, params: dict[str, Any], retrieved_at: str
) -> BrightDataResult:
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.bright_data_timeout_seconds,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        text = response.text
        content = [{"type": "text", "text": text[:50000]}]
        return BrightDataResult(
            endpoint="direct_http",
            parameters=params,
            retrieved_at=retrieved_at,
            content=content,
            structured_content=None,
            raw={
                "status_code": response.status_code,
                "final_url": str(response.url),
                "content_type": response.headers.get("content-type", ""),
            },
        )
    except Exception as exc:
        return BrightDataResult(
            endpoint="direct_http",
            parameters=params,
            retrieved_at=retrieved_at,
            content=[],
            structured_content=None,
            raw={"error": str(exc)},
            is_error=True,
            error=str(exc),
        )


async def _call_tool(mcp_url: str, endpoint: str, params: dict[str, Any]) -> Any:
    async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(endpoint, arguments=params)


def result_text(result: BrightDataResult, limit: int = 18000) -> str:
    chunks: list[str] = []
    if result.structured_content is not None:
        chunks.append(f"STRUCTURED_CONTENT:\n{result.structured_content}")
    for block in result.content:
        if "text" in block:
            chunks.append(str(block["text"]))
        elif "data" in block:
            chunks.append(str(block["data"]))
    text = "\n\n".join(chunks).strip()
    return text[:limit]
