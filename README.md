# Agent Royale

Unit tests for AI agents and retrieval layers that browse the web.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Task packs welcome](https://img.shields.io/badge/task%20packs-welcome-0f766e)](CONTRIBUTING.md)
[![Good first issues](https://img.shields.io/badge/good%20first%20issues-open-a16207)](CONTRIBUTING.md)

**Live site:** https://agentroyale.onrender.com/

AI agents now browse, search, scrape, and cite the web. Agent Royale tests whether they return the exact value your workflow asked for, from the source you required.

It is built for questions where there should be one current answer:

- the latest package version on npm
- the release tag on GitHub
- the price on an official pricing page
- the app rating from an app-store listing
- the quote field from a finance source
- the company metric from a required public profile

If the source is real but the returned value is stale, from the wrong field, from the wrong page, or unsupported by the citation, Agent Royale turns that into a repeatable test failure.

## Product Loop

```text
task pack -> oracle audit -> target run -> report -> compare before/after
```

1. Define source-specific questions in YAML.
2. Fetch independent ground truth from a public API, page parser, or Bright Data.
3. Call the target agent or retrieval layer.
4. Grade exact values deterministically.
5. Store provenance, evidence snippets, oracle status, latency, and cost.
6. Compare runs after prompt, model, parser, or retrieval changes.

No LLM judge is used for the core exact-value grade.

## Quickstart

```bash
pip install -e .
agent-royale --version
```

Run the offline smoke test:

```bash
python -m agent_royale lint task-packs/static-smoke.yaml
python -m agent_royale audit task-packs/static-smoke.yaml
python -m agent_royale run task-packs/static-smoke.yaml \
  --target examples/echo_agent.py:answer \
  --report reports/smoke.html
```

Watch the runner catch a wrong answer:

```bash
python -m agent_royale run task-packs/static-smoke.yaml \
  --target examples/flaky_agent.py:answer \
  --report reports/failure-demo.html
```

Targets can be:

- a local or staging HTTP endpoint, such as `http://localhost:3000/api/agent`
- an OpenRouter model adapter, such as `openrouter:provider/model`
- a local Python function, such as `examples/echo_agent.py:answer`

## Golden Path

The dependency-research example is the best first demo because it is useful, public, and reproducible without API keys. It models a developer assistant that answers npm and GitHub metadata questions.

```bash
python -m agent_royale lint task-packs/devtools/dependency-research.yaml
python -m agent_royale audit task-packs/devtools/dependency-research.yaml

python -m agent_royale run task-packs/devtools/dependency-research.yaml \
  --target examples/dev_research_agent.py:answer \
  --output runs/dependency-research-before.jsonl \
  --report reports/dependency-research-before.html

python -m agent_royale run task-packs/devtools/dependency-research.yaml \
  --target examples/dev_research_agent_fixed.py:answer \
  --output runs/dependency-research-after.jsonl \
  --report reports/dependency-research-after.html

python -m agent_royale compare \
  runs/dependency-research-before.jsonl \
  runs/dependency-research-after.jsonl \
  --markdown reports/dependency-research-comparison.md
```

On the current public sources, the intentionally imperfect target scores 57.1% and the fixed target scores 100.0%. The comparison identifies three concrete improvements:

- `github_playwright_latest_release`: wrong source fixed
- `github_vscode_open_issues`: wrong field semantics fixed
- `npm_next_weekly_downloads`: wrong time window fixed

See [docs/golden-path.md](docs/golden-path.md) for the full walkthrough.

## What You Get

- **Task packs:** YAML files for exact, source-specific retrieval tests
- **Oracle audit:** preflight checks that verify ground truth before testing a target
- **Ground-truth snapshots:** source URL, fetch time, parser metadata, evidence text, oracle status, and ambiguity flags
- **Target adapters:** HTTP endpoint, Python function, OpenRouter, and examples for web data, search, browser, and scraping stacks
- **Deterministic graders:** string, number, currency, percentage, date, and enum matching
- **Failure labels:** wrong value, wrong source, unsupported citation, no answer, tool failure, oracle ambiguity
- **Reports:** terminal summary, JSONL run log, and shareable HTML report
- **Run comparison:** before/after accuracy, source-supported accuracy, oracle skips, latency, cost, regressions, and Markdown output
- **Task-pack linting:** static checks for fragile oracles, volatile CI gates, broad regexes, missing provenance, and weak search-result ground truth
- **CI gates:** nonzero exit when accuracy drops below a threshold

## Why Ground Truth Is Treated Carefully

Ground truth is the product. Agent Royale does not assume a live page is stable just because it was fetched.

Every scored run stores an oracle snapshot. If the oracle cannot verify a value, returns conflicting candidates, misses required context, or looks ambiguous, the task is skipped instead of counted against the target. Task packs can mark sources as `stable`, `semi_stable`, or `volatile`, and volatile tasks can be excluded from CI with `ci_safe: false`.

For build-blocking checks, use stable packs backed by public APIs or slow-moving source fields. For fast-changing pages such as ecommerce prices, social counts, and dynamic public profiles, use scheduled or on-demand reports.

## Task Packs

The repo includes 79 reusable tasks:

```text
task-packs/static-smoke.yaml                     offline smoke tests
task-packs/devtools/dependency-research.yaml     reproducible golden-path demo
task-packs/devtools/dependency-research-v1.yaml  flagship dependency metadata eval
task-packs/devtools/docs-freshness-v1.yaml       docs and release freshness eval
task-packs/business/saas-pricing-v1.yaml         SaaS pricing accuracy eval
task-packs/github/example.yaml                   GitHub counts, releases, files, branches, licenses
task-packs/npm/example.yaml                      npm versions, licenses, downloads, repository URLs, package size, engines
task-packs/finance/yahoo-quotes.yaml             Yahoo Finance quote fields
task-packs/mobile-apps/apple-app-store.yaml      Apple App Store rating and version fields
task-packs/subscription-pricing/example.yaml     official pricing-page examples
task-packs/bright-data/rapid-web.yaml            Bright Data Rapid-mode docs/search checks
task-packs/bright-data/ecommerce-accuracy-v1.yaml Samsung ecommerce variant and title accuracy
task-packs/bright-data/linkedin-company.yaml     LinkedIn company metrics
task-packs/bright-data/ecommerce-pricing.yaml    ecommerce product pricing
```

Create a starter pack:

```bash
python -m agent_royale init task-pack cloud-pricing
```

Create a Bright Data Rapid-mode starter pack:

```bash
python -m agent_royale init task-pack product-pricing --ground-truth bright-data-rapid
```

Validate and lint all public packs:

```bash
python -m agent_royale validate task-packs
python -m agent_royale lint task-packs
```

The best first contribution is a task pack for a source your own agent depends on. See [TASK_PACK_IDEAS.md](TASK_PACK_IDEAS.md) and [docs/task-spec.md](docs/task-spec.md).

## Bright Data Ground Truth

Bright Data is useful when the required source is a messy public web page instead of a clean API. Agent Royale supports Bright Data as:

- an independent ground-truth oracle for task packs
- a target retrieval layer through the local Bright Data adapter example

Rapid-mode setup:

```bash
export BRIGHT_DATA_API_KEY=...
export BRIGHT_DATA_MCP_URL=https://mcp.brightdata.com/mcp
python -m agent_royale doctor task-packs/bright-data/rapid-web.yaml --check-ground-truth
```

Run the ecommerce accuracy pack against the Bright Data target adapter:

```bash
cd examples/bright-data-agent
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 3001

cd ../..
python -m agent_royale run task-packs/bright-data/ecommerce-accuracy-v1.yaml \
  --target http://127.0.0.1:3001/api/agent \
  --report reports/bright-data-ecommerce-agent.html
```

See [docs/bright-data.md](docs/bright-data.md) for tool selection, Rapid mode, structured tools, and oracle design.

## Original Experiment

Agent Royale started as an experiment with 32 live-web tasks and 12 model/retrieval stacks. The tested stacks averaged 54% exact accuracy, and the best stack reached 78%.

Treat that result as motivation, not a universal benchmark. The important finding was qualitative: agents often cited plausible sources while returning stale values, wrong fields, or values from nearby pages.

See [docs/experiments/dev-web-retrieval-v1.md](docs/experiments/dev-web-retrieval-v1.md) for a larger reproducible eval and methodology notes.

## Stack Fit Eval

Agent Royale can also be used as a fit test for web retrieval infrastructure. The Stack Fit eval groups tasks by workflow so teams can test URL readers, scrape/extract APIs, search APIs, dynamic-web extractors, and model-search stacks without treating unlike tools as a single leaderboard.

The current public evidence includes:

- Jina Reader on known-source reading: 3/3 exact
- Firecrawl on known-source reading: 3/3 exact
- Tavily extract on known-source extraction: 3/3 exact
- Bright Data on focused dynamic ecommerce extraction: 3/3 exact
- OpenRouter GPT-4o Mini on search/discovery: 2/3 exact
- OpenRouter GPT-4o Mini on Dev Web Retrieval Eval v1: 20/28 exact

See [docs/experiments/web-retrieval-stack-fit-v1.md](docs/experiments/web-retrieval-stack-fit-v1.md) for the lane design, reports, and reproduction commands.

## CI

Use CI for stable task packs:

```yaml
name: Agent Royale

on:
  pull_request:
  push:
    branches: [main]

jobs:
  retrieval-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m agent_royale validate task-packs
      - run: python -m agent_royale lint task-packs/static-smoke.yaml
      - run: |
          python -m agent_royale run task-packs/static-smoke.yaml \
            --target examples/echo_agent.py:answer \
            --ci \
            --report reports/agent-royale.html \
            --fail-under-exact 1.0
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: agent-royale-report
          path: reports/agent-royale.html
```

See [docs/github-actions.md](docs/github-actions.md) for endpoint, OpenRouter, Bright Data, and comparison examples.

## Docs

- [Golden path](docs/golden-path.md)
- [Quickstart](docs/quickstart.md)
- [Task spec](docs/task-spec.md)
- [Adapter contract](docs/adapter-contract.md)
- [GitHub Actions](docs/github-actions.md)
- [Integrations](docs/integrations.md)
- [Bright Data ground truth](docs/bright-data.md)
- [OpenRouter eval](docs/openrouter.md)
- [Realistic dev-agent eval](docs/realistic-dev-eval.md)
- [Web Retrieval Stack Fit Eval v1](docs/experiments/web-retrieval-stack-fit-v1.md)

## Repo Structure

```text
agent_royale/         core runner, grader, lint, compare, report generation
backend/              FastAPI app and live-site API
frontend/             static frontend
task-packs/           public task packs
examples/             local target adapters
docs/                 usage and methodology docs
data/                 original task bank data
storage/              local JSONL storage
```

## Contributing

The best first PR is a task pack for a source your own agent depends on.

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [TASK_PACK_IDEAS.md](TASK_PACK_IDEAS.md)
- [ROADMAP.md](ROADMAP.md)

## Contact

vinayasharma00@gmail.com
