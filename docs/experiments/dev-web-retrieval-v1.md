# Dev Web Retrieval Eval v1

Dev Web Retrieval Eval v1 is Agent Royale's first flagship task set for evaluating agents and retrieval layers on practical developer and business research workflows.

The eval asks source-specific questions with exact current answers: package versions, license fields, SDK README examples, release-index metadata, repository-file values, and pricing-page values. Agent Royale fetches independent ground truth from the required source, calls the target under test, and grades the extracted answer.

## Why This Eval Exists

Agents often browse, search, scrape, and cite real pages while still returning the wrong value for the workflow. This eval focuses on that gap.

The tasks are intentionally strict. A nearby package version, a monthly price from the wrong billing interval, a GitHub URL that differs from npm registry metadata, or a value from the wrong source is marked wrong.

## Task Packs

| Pack | Tasks | Focus | Oracle types |
|---|---:|---|---|
| [`dependency-research-v1.yaml`](../../task-packs/devtools/dependency-research-v1.yaml) | 12 | npm, PyPI, GitHub package and repository metadata | HTTP JSON |
| [`docs-freshness-v1.yaml`](../../task-packs/devtools/docs-freshness-v1.yaml) | 10 | SDK README examples, release indexes, repository files | HTTP JSON, HTTP regex |
| [`saas-pricing-v1.yaml`](../../task-packs/business/saas-pricing-v1.yaml) | 6 | official pricing pages and billing intervals | HTTP regex |

Total: 28 tasks.

Before running the experiment, all 28 oracle checks passed locally.

```bash
python -m agent_royale doctor \
  task-packs/devtools/dependency-research-v1.yaml \
  task-packs/devtools/docs-freshness-v1.yaml \
  task-packs/business/saas-pricing-v1.yaml \
  --check-ground-truth
```

## Targets Run

| Target | Type | Report | Exact accuracy | Notes |
|---|---|---|---:|---|
| `examples/flagship_dev_web_agent.py:answer` | local demo target | [`flagship-demo.html`](../../reports/dev-web-retrieval-v1/flagship-demo.html) | 75.0% | Uses real public APIs/pages with intentional realistic retrieval mistakes. |
| `openrouter:openai/gpt-4o-mini` | model web-search stack | [`openrouter-gpt4o-mini.html`](../../reports/dev-web-retrieval-v1/openrouter-gpt4o-mini.html) | 67.9% | Real external model run through the OpenRouter target adapter. |

![OpenRouter GPT-4o Mini report screenshot](../assets/experiments/dev-web-retrieval-v1/openrouter-gpt4o-mini-report.png)

## What The Runs Caught

The controlled demo target failed on source and field confusion:

- returned the PyPI package version when the task asked for the GitHub release tag
- returned npm `dist.fileCount` when the task asked for `dist.unpackedSize`
- returned the npm latest version when the task required the GitHub canary package file
- returned the monthly billing price when the task asked for annual monthly-equivalent pricing
- returned the Figma Professional price for an Organization-plan task

The OpenRouter model-stack run showed similar real-world failure patterns:

- stale npm package versions for React and Vite
- wrong Figma plan prices
- stale Next.js canary package version
- package metadata formatting mismatch for npm repository URLs
- install-command extraction failure for the MCP Python SDK README
- citation support issues even when the extracted value matched the oracle

## Result Summary

| Target | Tasks | Exact correct | Exact accuracy | Wrong value | Wrong source | Citation issue |
|---|---:|---:|---:|---:|---:|---:|
| Flagship demo target | 28 | 21 | 75.0% | 4 | 3 | 0 |
| OpenRouter GPT-4o Mini | 28 | 19 | 67.9% | 7 | 0 | 4 |

Citation issues are tracked separately from exact value matching. A target can extract the right value but still fail source support if its citation does not support the claim from the required source.

![Flagship demo report screenshot](../assets/experiments/dev-web-retrieval-v1/flagship-demo-report.png)

## How To Reproduce

Run the controlled demo target:

```bash
python -m agent_royale run \
  task-packs/devtools/dependency-research-v1.yaml \
  task-packs/devtools/docs-freshness-v1.yaml \
  task-packs/business/saas-pricing-v1.yaml \
  --target examples/flagship_dev_web_agent.py:answer \
  --output runs/dev-web-retrieval-v1/flagship-demo.jsonl \
  --report reports/dev-web-retrieval-v1/flagship-demo.html
```

Run a model/search stack through OpenRouter:

```bash
OPENROUTER_API_KEY=...
python -m agent_royale run \
  task-packs/devtools/dependency-research-v1.yaml \
  task-packs/devtools/docs-freshness-v1.yaml \
  task-packs/business/saas-pricing-v1.yaml \
  --target openrouter:openai/gpt-4o-mini \
  --output runs/dev-web-retrieval-v1/openrouter-gpt4o-mini.jsonl \
  --report reports/dev-web-retrieval-v1/openrouter-gpt4o-mini.html
```

## Interpretation

This is not a universal model ranking. It is a workflow eval.

The useful signal is that common web-agent tasks fail in specific, inspectable ways: stale values, wrong fields, wrong billing windows, source mismatch, and unsupported citations. Teams can adapt these packs or write their own to test the exact sources their product depends on.
