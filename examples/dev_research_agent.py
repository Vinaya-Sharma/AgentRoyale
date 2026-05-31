from __future__ import annotations

from typing import Any

import httpx


def answer(question: str, task: dict[str, Any]) -> dict[str, Any]:
    """A tiny realistic dev-research agent with a few intentional retrieval bugs.

    It calls public GitHub and npm APIs. Some task handlers use the wrong but
    plausible source/field so the Agent Royale report demonstrates the value of
    exact source-specific grading.
    """
    task_id = str(task.get("id", ""))
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        if task_id == "github_nextjs_stars":
            return github_repo_field(client, "vercel/next.js", "stargazers_count")
        if task_id == "github_vscode_open_issues":
            return github_vscode_issues_only(client)
        if task_id == "github_fastapi_forks":
            return github_repo_field(client, "fastapi/fastapi", "forks_count")
        if task_id == "github_playwright_latest_release":
            return npm_latest_version(client, "playwright", note="Mistake: used npm package version instead of GitHub release tag.")
        if task_id == "npm_react_latest":
            return npm_latest_version(client, "react")
        if task_id == "npm_vite_latest":
            return npm_latest_version(client, "vite")
        if task_id == "npm_typescript_license":
            payload = get_json(client, "https://registry.npmjs.org/typescript/latest")
            value = str(payload.get("license", ""))
            return response(
                value,
                "https://www.npmjs.com/package/typescript",
                f"license {value}",
                ["npm.registry"],
            )
        if task_id == "npm_next_weekly_downloads":
            return npm_next_monthly_downloads(client)
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


def github_vscode_issues_only(client: httpx.Client) -> dict[str, Any]:
    url = "https://api.github.com/search/issues?q=repo:microsoft/vscode+type:issue+state:open"
    payload = get_json(client, url)
    value = payload["total_count"]
    return response(
        str(value),
        "https://github.com/microsoft/vscode/issues",
        f"open issues only {value}",
        ["github.search"],
        note="Mistake: counted open issues only, not GitHub open_issues_count including PRs.",
    )


def npm_latest_version(client: httpx.Client, package: str, note: str = "") -> dict[str, Any]:
    url = f"https://registry.npmjs.org/{package}/latest"
    payload = get_json(client, url)
    value = str(payload.get("version", ""))
    return response(
        value,
        f"https://www.npmjs.com/package/{package}",
        f"version {value}",
        ["npm.registry"],
        note=note,
    )


def npm_next_monthly_downloads(client: httpx.Client) -> dict[str, Any]:
    url = "https://api.npmjs.org/downloads/point/last-month/next"
    payload = get_json(client, url)
    value = payload["downloads"]
    return response(
        str(value),
        url,
        f"last-month downloads {value}",
        ["npm.downloads"],
        note="Mistake: used last-month downloads instead of last-week downloads.",
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


def response(
    answer_text: str,
    url: str,
    quote: str,
    tools: list[str],
    *,
    note: str = "",
) -> dict[str, Any]:
    trace = {"tools_used": tools, "cost_usd": 0.0}
    if note:
        trace["search_queries"] = [note]
    return {
        "answer": answer_text,
        "citations": [{"url": url, "quote": quote}],
        "trace": trace,
    }
