from __future__ import annotations

import re
from typing import Any

import httpx


def answer(question: str, task: dict[str, Any]) -> dict[str, Any]:
    """A broader demo target for the Dev Web Retrieval v1 experiment.

    This is not meant to be a perfect agent. It uses real public sources and
    intentionally includes several realistic retrieval mistakes so the report
    shows useful failure modes: wrong source, wrong field, wrong billing window,
    and unsupported or over-normalized citations.
    """
    task_id = str(task.get("id", ""))
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "agent-royale-flagship-demo"}) as client:
        if task_id == "devv1_npm_react_latest":
            return npm_field(client, "react", "version")
        if task_id == "devv1_npm_vite_latest":
            return npm_field(client, "vite", "version")
        if task_id == "devv1_npm_typescript_license":
            return npm_field(client, "typescript", "license")
        if task_id == "devv1_npm_zod_repository_url":
            return response("https://github.com/colinhacks/zod", "https://github.com/colinhacks/zod", "repository https://github.com/colinhacks/zod", ["github.web"])
        if task_id == "devv1_npm_prettier_unpacked_size":
            return npm_field(client, "prettier", "dist.fileCount", note="Mistake: used file count instead of unpacked size.")
        if task_id == "devv1_npm_eslint_node_engine":
            return npm_field(client, "eslint", "engines.node")
        if task_id == "devv1_pypi_requests_latest":
            return pypi_field(client, "requests", "info.version")
        if task_id == "devv1_pypi_requests_license":
            return pypi_field(client, "requests", "info.license")
        if task_id == "devv1_pypi_fastapi_latest":
            return pypi_field(client, "fastapi", "info.version")
        if task_id == "devv1_pypi_fastapi_requires_python":
            return pypi_field(client, "fastapi", "info.requires_python")
        if task_id == "devv1_github_openai_python_latest_release":
            return pypi_field(client, "openai", "info.version", note="Mistake: used PyPI version instead of GitHub release tag.")
        if task_id == "devv1_github_mcp_python_sdk_license":
            return github_repo_field(client, "modelcontextprotocol/python-sdk", "license.spdx_id")

        if task_id == "docsv1_openai_python_client_class":
            return raw_regex(client, "https://raw.githubusercontent.com/openai/openai-python/main/README.md", r"from\s+openai\s+import\s+([A-Za-z_][A-Za-z0-9_]*)", "https://github.com/openai/openai-python")
        if task_id == "docsv1_anthropic_python_client_class":
            return raw_regex(client, "https://raw.githubusercontent.com/anthropics/anthropic-sdk-python/main/README.md", r"from\s+anthropic\s+import\s+([A-Za-z_][A-Za-z0-9_]*)", "https://github.com/anthropics/anthropic-sdk-python")
        if task_id == "docsv1_mcp_python_fastmcp_class":
            return raw_regex(client, "https://raw.githubusercontent.com/modelcontextprotocol/python-sdk/main/README.md", r"from\s+mcp\.server\.fastmcp\s+import\s+([A-Za-z_][A-Za-z0-9_]*)", "https://github.com/modelcontextprotocol/python-sdk")
        if task_id == "docsv1_mcp_python_pip_install":
            return response("mcp[cli]", "https://github.com/modelcontextprotocol/python-sdk", "pip install \"mcp[cli]\"", ["github.raw"], note="Mistake: stripped quotes from the install spec.")
        if task_id == "docsv1_langchain_pip_install":
            return raw_regex(client, "https://raw.githubusercontent.com/langchain-ai/langchain/master/README.md", r"pip\s+install\s+([^\n`]+)", "https://github.com/langchain-ai/langchain")
        if task_id == "docsv1_node_latest_release_version":
            return node_index_field(client, 0, "version")
        if task_id == "docsv1_node_latest_release_npm":
            return node_latest_lts_field(client, "npm", note="Mistake: used latest LTS release instead of latest release row.")
        if task_id == "docsv1_next_canary_package_version":
            return npm_field(client, "next", "version", note="Mistake: used npm latest instead of the GitHub canary package.json.")
        if task_id == "docsv1_openai_python_requires_python":
            return pypi_field(client, "openai", "info.requires_python")
        if task_id == "docsv1_anthropic_python_requires_python":
            return pypi_field(client, "anthropic", "info.requires_python")

        if task_id == "pricev1_notion_plus_annual_monthly":
            return response("$12", "https://www.notion.com/pricing", "Plus monthly price $12", ["pricing.page"], note="Mistake: used monthly billing instead of annual monthly equivalent.")
        if task_id == "pricev1_notion_business_annual_monthly":
            return page_price(client, "https://www.notion.com/pricing", r"Business[\s\S]{0,3000}?\$\s*([0-9]+(?:\.[0-9]{2})?)", "https://www.notion.com/pricing")
        if task_id == "pricev1_figma_professional_annual_monthly":
            return page_price(client, "https://www.figma.com/pricing/", r"Professional[\s\S]{0,3000}?\$\s*([0-9]+(?:\.[0-9]{2})?)", "https://www.figma.com/pricing/")
        if task_id == "pricev1_figma_organization_annual_monthly":
            return response("$16", "https://www.figma.com/pricing/", "Professional $16", ["pricing.page"], note="Mistake: read Professional instead of Organization.")
        if task_id == "pricev1_netflix_standard_with_ads_us":
            return page_price(client, "https://help.netflix.com/en/node/24926", r"Standard\s+with\s+ads[\s\S]{0,800}?\$\s*([0-9]+(?:\.[0-9]{2})?)", "https://help.netflix.com/en/node/24926")
        if task_id == "pricev1_dropbox_plus_annual_monthly":
            return page_price(client, "https://www.dropbox.com/plans", r"Plus[\s\S]{0,3000}?\$\s*([0-9]+(?:\.[0-9]{2})?)", "https://www.dropbox.com/plans")

    return {"answer": "", "citations": [], "trace": {"tools_used": ["flagship.no_match"]}}


def npm_field(client: httpx.Client, package: str, field: str, note: str = "") -> dict[str, Any]:
    url = f"https://registry.npmjs.org/{package}/latest"
    payload = client.get(url).json()
    value = read_field(payload, field)
    return response(str(value), f"https://www.npmjs.com/package/{package}", f"{field} {value}", ["npm.registry"], note=note)


def pypi_field(client: httpx.Client, package: str, field: str, note: str = "") -> dict[str, Any]:
    url = f"https://pypi.org/pypi/{package}/json"
    payload = client.get(url).json()
    value = read_field(payload, field)
    return response(str(value), f"https://pypi.org/project/{package}", f"{field} {value}", ["pypi.json"], note=note)


def github_repo_field(client: httpx.Client, repo: str, field: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repo}"
    payload = client.get(url, headers={"Accept": "application/vnd.github+json"}).json()
    value = read_field(payload, field)
    return response(str(value), f"https://github.com/{repo}", f"{field} {value}", ["github.rest"])


def raw_regex(client: httpx.Client, url: str, pattern: str, source_url: str) -> dict[str, Any]:
    text = client.get(url).text
    match = re.search(pattern, text, re.I | re.S)
    value = match.group(1).strip() if match else ""
    return response(value, source_url, value, ["github.raw"])


def node_index_field(client: httpx.Client, index: int, field: str) -> dict[str, Any]:
    payload = client.get("https://nodejs.org/dist/index.json").json()
    value = payload[index][field]
    return response(str(value), "https://nodejs.org/dist/index.json", f"{field} {value}", ["node.release_index"])


def node_latest_lts_field(client: httpx.Client, field: str, note: str = "") -> dict[str, Any]:
    payload = client.get("https://nodejs.org/dist/index.json").json()
    row = next(item for item in payload if item.get("lts"))
    value = row[field]
    return response(str(value), "https://nodejs.org/dist/index.json", f"{field} {value}", ["node.release_index"], note=note)


def page_price(client: httpx.Client, url: str, pattern: str, source_url: str) -> dict[str, Any]:
    text = client.get(url).text
    match = re.search(pattern, text, re.I | re.S)
    value = match.group(1).strip() if match else ""
    return response(f"${value}", source_url, f"${value}", ["pricing.page"])


def read_field(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        else:
            current = current[part]
    return current


def response(answer_text: str, url: str, quote: str, tools: list[str], *, note: str = "") -> dict[str, Any]:
    trace = {"tools_used": tools, "cost_usd": 0.0}
    if note:
        trace["search_queries"] = [note]
    return {
        "answer": answer_text,
        "citations": [{"url": url, "quote": quote}],
        "trace": trace,
    }
