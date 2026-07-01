# Final Launch Checklist

Use this before publishing the final Agent Royale launch post and Medium article.

## Core Story

Agent Royale helps teams test which model, tool, or agent stack is actually reliable for their live-web tasks. It fetches independent ground truth, checks exact values and sources, skips unsafe oracle tasks, and generates reports that show accuracy, citation support, latency, cost, and regressions.

## Launch Assets

- Medium article draft: `docs/medium-launch-article.md`
- README hero screenshot: `docs/assets/launch/v3-report-decision-dashboard.png`
- Task bank screenshot: `docs/assets/launch/tasks.png`
- Stack-fit report screenshot: `docs/assets/experiments/stack-fit-v1/openrouter-dev-web-retrieval-report.png`
- Bright Data ecommerce report screenshot: `docs/assets/experiments/stack-fit-v1/bright-data-dynamic-ecommerce-report.png`
- General report preview: `docs/assets/report-preview.png`
- Optional leaderboard screenshot: `docs/assets/launch/leaderboard.png`

## Medium Image Order

1. After the intro: `docs/assets/launch/v3-report-decision-dashboard.png`
2. After "You define task packs": `docs/assets/launch/tasks.png`
3. After the three retrieval layers: `docs/assets/experiments/stack-fit-v1/openrouter-dev-web-retrieval-report.png`
4. After the Samsung/Bright Data example: `docs/assets/experiments/stack-fit-v1/bright-data-dynamic-ecommerce-report.png`
5. At the start of "What The Reports Show": `docs/assets/report-preview.png`

## Final LinkedIn Post

```text
Agent Royale is now open source.

AI products are starting to depend on live web data, but choosing the right retrieval stack is still hard.

OpenRouter makes it easy to try models. Tavily and Jina AI are fast for search and retrieval. Firecrawl, Browserbase, and Bright Data help with structured extraction, scraping, and browser workflows.

Agent Royale works with these stacks to test which one is actually reliable for your product's tasks.

You define task packs for the questions your product cares about: pricing pages, GitHub releases, npm versions, product data, docs freshness, company metrics.

Agent Royale fetches independent ground truth, grades exact values deterministically, checks whether the source and citation support the answer, and generates reports showing wrong values, wrong sources, unsupported citations, latency, cost, oracle skips, and regressions.

The goal is to help teams stop guessing which model/tool/agent stack to trust and start choosing based on real task-level evidence.

Built with support from Bright Data for live-web ground truth.

Repo: https://github.com/Vinaya-Sharma/AgentRoyale

Would love task packs, issues, integrations, and weird agent failures.
```

## Final Verification Commands

Run these from the repo root:

```bash
git status --short
python3 -m compileall agent_royale backend
python3 -m agent_royale validate task-packs
python3 -m agent_royale lint task-packs/bright-data
python3 -m agent_royale demo
```

Expected notes:

- Bright Data lint has one expected warning for `bd_rapid_docs_search_top_result` because search-result ordering is a weaker oracle than a required-source page scrape.
- Best Buy remains quarantined because direct HTTP, markdown, HTML, structured Best Buy extraction, and browser attempts were not reliable enough for a public scoreable task.
- Samsung 512GB price is now verified through the canonical SKU page and Product JSON-LD/schema.org HTML fallback.

## Do Not Launch With

- Internal mentor notes.
- Unverified Best Buy scoreable tasks.
- Claims that every website can be scraped reliably.
- A broad leaderboard claim without explaining task-bank context.

## Final Repo Message

Agent Royale is strongest when it emphasizes reliability:

- oracle verified before grading
- deterministic exact-value grading
- source and citation checks
- transparent skips/quarantine for unsafe ground truth
- reports that help developers choose the best stack for their actual tasks
