from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from backend.config import get_settings


LINKEDIN_COMPANY_DATASET_ID = "gd_l1vikfnt1wgvvqz95w"
CRUNCHBASE_COMPANY_DATASET_ID = "gd_l1vijqt9jfj7olije"


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
    if endpoint == "search_engine":
        return {"query": url, "engine": "google"}
    if endpoint == "bright_data_linkedin_company_dataset":
        return {"url": url}
    if endpoint == "bright_data_crunchbase_company_dataset":
        return {"url": url}
    if endpoint == "web_data_amazon_product":
        return {"url": url}
    if endpoint == "web_data_linkedin_company_profile":
        return {"url": url}
    if endpoint == "web_data_amazon_product_search":
        return {"keyword": url, "url": "https://www.amazon.com/s?k="}
    if endpoint == "web_data_npm_package":
        package = url.rstrip("/").split("/")[-1]
        if "/package/" in url:
            package = url.split("/package/", 1)[1].strip("/")
        return {"package_name": unquote(package)}
    if endpoint == "web_data_pypi_package":
        package = url.rstrip("/").split("/")[-1]
        if "/project/" in url:
            package = url.split("/project/", 1)[1].strip("/")
        return {"package_name": unquote(package)}
    if endpoint == "web_data_youtube_comments":
        return {"url": url, "num_of_comments": 10}
    if endpoint == "web_data_google_maps_reviews":
        return {"url": url, "days_limit": 7}
    if endpoint == "web_data_facebook_company_reviews":
        return {"url": url, "num_of_reviews": 20}
    if endpoint == "web_data_x_profile_posts":
        parsed = urlparse(url)
        return {"url": f"{parsed.scheme}://{parsed.netloc}{parsed.path}"}
    if "finance.yahoo.com/quote/" in url and endpoint in {"scrape_as_markdown", "scrape_as_html"}:
        return {
            "url": url,
            "wait_for": "fin-streamer[data-field='regularMarketPrice']",
            "max_wait_ms": 8000,
        }
    return {"url": url}


def yahoo_chart_url(url: str) -> str | None:
    if "finance.yahoo.com/quote/" not in url:
        return None
    symbol = url.rstrip("/").split("/quote/", 1)[-1].split("/", 1)[0]
    if not symbol:
        return None
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1m"


def fallback_endpoints(primary: str) -> list[str]:
    if primary == "web_data_linkedin_company_profile":
        chain = ["bright_data_linkedin_company_dataset", primary]
    elif primary == "web_data_crunchbase_company":
        chain = ["bright_data_crunchbase_company_dataset", primary]
    elif primary == "scrape_as_markdown":
        chain = [primary, "scrape_as_html", "direct_http"]
    else:
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
    if endpoint in {"scrape_as_markdown", "scrape_as_html", "direct_http"}:
        chart_url = yahoo_chart_url(url)
        if chart_url:
            url = chart_url
    params = args_for_tool(endpoint, url)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    if endpoint == "direct_http":
        return await _fetch_direct_http(url, params, retrieved_at)
    if endpoint == "bright_data_linkedin_company_dataset":
        return await _fetch_linkedin_company_dataset(url, params, retrieved_at)
    if endpoint == "bright_data_crunchbase_company_dataset":
        return await _fetch_crunchbase_company_dataset(url, params, retrieved_at)

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


async def _fetch_linkedin_company_dataset(
    url: str, params: dict[str, Any], retrieved_at: str
) -> BrightDataResult:
    settings = get_settings()
    if not settings.bright_data_api_key:
        return BrightDataResult(
            endpoint="bright_data_linkedin_company_dataset",
            parameters=params,
            retrieved_at=retrieved_at,
            content=[],
            structured_content=None,
            raw={"error": "BRIGHT_DATA_API_KEY is required for the LinkedIn Dataset API fallback"},
            is_error=True,
            error="BRIGHT_DATA_API_KEY is required for the LinkedIn Dataset API fallback",
        )
    request_url = (
        "https://api.brightdata.com/datasets/v3/scrape"
        f"?dataset_id={LINKEDIN_COMPANY_DATASET_ID}&include_errors=true"
    )
    try:
        async with httpx.AsyncClient(timeout=max(settings.bright_data_timeout_seconds, 120)) as client:
            response = await client.post(
                request_url,
                headers={
                    "Authorization": f"Bearer {settings.bright_data_api_key}",
                    "Content-Type": "application/json",
                },
                json={"input": [{"url": url}]},
            )
            response.raise_for_status()
        data = compact_linkedin_company_data(response.json())
        text = json_dumps(data)
        return BrightDataResult(
            endpoint="bright_data_linkedin_company_dataset",
            parameters=params,
            retrieved_at=retrieved_at,
            content=[{"type": "text", "text": text[:50000]}],
            structured_content=data,
            raw={
                "dataset_id": LINKEDIN_COMPANY_DATASET_ID,
                "status_code": response.status_code,
                "structured_content": data,
            },
            is_error=False,
        )
    except Exception as exc:
        return BrightDataResult(
            endpoint="bright_data_linkedin_company_dataset",
            parameters=params,
            retrieved_at=retrieved_at,
            content=[],
            structured_content=None,
            raw={"error": str(exc), "dataset_id": LINKEDIN_COMPANY_DATASET_ID},
            is_error=True,
            error=str(exc),
        )


async def _fetch_crunchbase_company_dataset(
    url: str, params: dict[str, Any], retrieved_at: str
) -> BrightDataResult:
    settings = get_settings()
    if not settings.bright_data_api_key:
        return BrightDataResult(
            endpoint="bright_data_crunchbase_company_dataset",
            parameters=params,
            retrieved_at=retrieved_at,
            content=[],
            structured_content=None,
            raw={"error": "BRIGHT_DATA_API_KEY is required for the Crunchbase Dataset API fallback"},
            is_error=True,
            error="BRIGHT_DATA_API_KEY is required for the Crunchbase Dataset API fallback",
        )
    request_url = (
        "https://api.brightdata.com/datasets/v3/scrape"
        f"?dataset_id={CRUNCHBASE_COMPANY_DATASET_ID}&include_errors=true"
    )
    try:
        async with httpx.AsyncClient(timeout=max(settings.bright_data_timeout_seconds, 120)) as client:
            response = await client.post(
                request_url,
                headers={
                    "Authorization": f"Bearer {settings.bright_data_api_key}",
                    "Content-Type": "application/json",
                },
                json={"input": [{"url": url}]},
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and data.get("snapshot_id"):
                data = await _wait_for_snapshot(client, data["snapshot_id"])
        data = compact_crunchbase_company_data(data)
        text = json_dumps(data)
        return BrightDataResult(
            endpoint="bright_data_crunchbase_company_dataset",
            parameters=params,
            retrieved_at=retrieved_at,
            content=[{"type": "text", "text": text[:50000]}],
            structured_content=data,
            raw={
                "dataset_id": CRUNCHBASE_COMPANY_DATASET_ID,
                "status_code": response.status_code,
                "structured_content": data,
            },
            is_error=False,
        )
    except Exception as exc:
        error = f"{exc.__class__.__name__}: {exc}"
        return BrightDataResult(
            endpoint="bright_data_crunchbase_company_dataset",
            parameters=params,
            retrieved_at=retrieved_at,
            content=[],
            structured_content=None,
            raw={"error": error, "dataset_id": CRUNCHBASE_COMPANY_DATASET_ID},
            is_error=True,
            error=error,
        )


async def _wait_for_snapshot(client: httpx.AsyncClient, snapshot_id: str) -> Any:
    headers = {"Authorization": f"Bearer {get_settings().bright_data_api_key}"}
    for _ in range(60):
        progress = await client.get(
            f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}",
            headers=headers,
        )
        progress.raise_for_status()
        status = progress.json().get("status")
        if status == "ready":
            snapshot = await client.get(
                f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json",
                headers=headers,
            )
            snapshot.raise_for_status()
            return snapshot.json()
        if status == "failed":
            raise RuntimeError(f"Bright Data snapshot {snapshot_id} failed")
        await asyncio.sleep(3)
    raise TimeoutError(f"Bright Data snapshot {snapshot_id} was not ready in time")


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def compact_linkedin_company_data(data: Any) -> Any:
    keep = {
        "id",
        "name",
        "country_code",
        "followers",
        "employees_in_linkedin",
        "company_size",
        "organization_type",
        "industries",
        "website",
        "founded",
        "company_id",
    }

    def compact_record(record: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in record.items() if key in keep}

    if isinstance(data, dict):
        return compact_record(data)
    if isinstance(data, list):
        return [compact_record(item) if isinstance(item, dict) else item for item in data]
    return data


def compact_crunchbase_company_data(data: Any) -> Any:
    keep = {
        "id",
        "name",
        "url",
        "website",
        "homepage_url",
        "description",
        "short_description",
        "about",
        "company_type",
        "organization_type",
        "industries",
        "industry",
        "categories",
        "founded",
        "founded_date",
        "founded_year",
        "headquarters",
        "location",
        "country_code",
        "num_employees",
        "employees",
        "employee_count",
        "employees_count",
        "company_size",
        "size",
        "number_of_employee_profiles",
        "total_funding",
        "funding_total",
        "funding",
        "investors",
        "crunchbase_rank",
        "rank",
    }

    def compact_record(record: dict[str, Any]) -> dict[str, Any]:
        compact = {
            key: value
            for key, value in record.items()
            if key in keep and value not in (None, "", [], {})
        }
        return compact or {
            key: value for key, value in record.items() if value not in (None, "", [], {})
        }

    if isinstance(data, dict):
        return compact_record(data)
    if isinstance(data, list):
        return [compact_record(item) if isinstance(item, dict) else item for item in data]
    return data


async def _call_tool(mcp_url: str, endpoint: str, params: dict[str, Any]) -> Any:
    async with streamable_http_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            return await session.call_tool(endpoint, arguments=params)


def result_text(result: BrightDataResult, limit: int = 18000) -> str:
    chunks: list[str] = []
    if result.structured_content is not None:
        chunks.append(f"STRUCTURED_CONTENT:\n{json_dumps(result.structured_content)}")
    for block in result.content:
        if result.structured_content is not None and block.get("type") == "text":
            continue
        if "text" in block:
            chunks.append(str(block["text"]))
        elif "data" in block:
            chunks.append(str(block["data"]))
    text = "\n\n".join(chunks).strip()
    return text[:limit]
