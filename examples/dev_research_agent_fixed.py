from __future__ import annotations

from typing import Any

import httpx


def answer(question: str, task: dict[str, Any]) -> dict[str, Any]:
    """Corrected version of the dependency-research demo target.

    This file pairs with `examples/dev_research_agent.py` for the README golden
    path. The first target has realistic retrieval bugs; this target fixes the
    source and field choices so `agent-royale compare` can show the improvement.
    """
    task_id = str(task.get("id", ""))
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        if task_id == "github_nextjs_stars":
            return github_repo_field(client, "vercel/next.js", "stargazers_count")
        if task_id == "github_vscode_open_issues":
            return github_repo_field(client, "microsoft/vscode", "open_issues_count")
        if task_id == "github_fastapi_forks":
            return github_repo_field(client, "fastapi/fastapi", "forks_count")
        if task_id == "github_playwright_latest_release":
            return github_latest_release(client, "microsoft/playwright")
        if task_id == "github_vue_package_version":
            return github_vue_package_version(client)
        if task_id == "npm_react_latest":
            return npm_latest_version(client, "react")
        if task_id == "npm_vite_latest":
            return npm_latest_version(client, "vite")
        if task_id == "npm_typescript_license":
            return npm_latest_field(client, "typescript", "license")
        if task_id == "npm_next_weekly_downloads":
            return npm_weekly_downloads(client, "next")
        if task_id == "npm_lodash_weekly_downloads":
            return npm_weekly_downloads(client, "lodash")
        if task_id == "npm_react_weekly_downloads":
            return npm_weekly_downloads(client, "react")
    return {"answer": "", "citations": [], "trace": {"tools_used": ["example.no_match"]}}


def github_repo_field(client: httpx.Client, repo: str, field: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repo}"
    payload = get_json(client, url)
    value = payload[field]
    return response(
        str(value),
        f"https://github.com/{repo}",
        f"{field} {value}",
        ["github.rest"],
    )


def github_latest_release(client: httpx.Client, repo: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    payload = get_json(client, url)
    value = str(payload.get("tag_name", ""))
    return response(
        value,
        f"https://github.com/{repo}/releases/latest",
        f"tag_name {value}",
        ["github.rest"],
    )


def npm_latest_version(client: httpx.Client, package: str) -> dict[str, Any]:
    return npm_latest_field(client, package, "version")


def npm_latest_field(client: httpx.Client, package: str, field: str) -> dict[str, Any]:
    url = f"https://registry.npmjs.org/{package}/latest"
    payload = get_json(client, url)
    value = str(payload.get(field, ""))
    return response(
        value,
        f"https://www.npmjs.com/package/{package}",
        f"{field} {value}",
        ["npm.registry"],
    )


def github_vue_package_version(client: httpx.Client) -> dict[str, Any]:
    url = "https://raw.githubusercontent.com/vuejs/core/main/packages/vue/package.json"
    payload = get_json(client, url)
    value = str(payload.get("version", ""))
    return response(
        value,
        "https://github.com/vuejs/core/blob/main/packages/vue/package.json",
        f"version {value}",
        ["github.raw"],
    )


def npm_weekly_downloads(client: httpx.Client, package: str) -> dict[str, Any]:
    url = f"https://api.npmjs.org/downloads/point/last-week/{package}"
    payload = get_json(client, url)
    value = payload["downloads"]
    return response(
        str(value),
        url,
        f"last-week downloads {value}",
        ["npm.downloads"],
    )


def get_json(client: httpx.Client, url: str) -> dict[str, Any]:
    res = client.get(
        url,
        headers={
            "Accept": "application/vnd.github+json, application/json",
            "User-Agent": "agent-royale-example-dev-agent",
        },
    )
    res.raise_for_status()
    return res.json()


def response(answer_text: str, url: str, quote: str, tools: list[str]) -> dict[str, Any]:
    return {
        "answer": answer_text,
        "citations": [{"url": url, "quote": quote}],
        "trace": {"tools_used": tools, "cost_usd": 0.0},
    }
