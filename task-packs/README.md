# Agent Royale Task Packs

These packs are intentionally small, readable, and source-specific. Developers should be able to inspect the task, understand the oracle, and decide whether the task is fair for their stack.

## Packs

- `static-smoke.yaml`: offline target-contract smoke tests.
- `devtools/dependency-research-v1.yaml`: flagship dependency metadata tasks for npm, PyPI, and GitHub.
- `devtools/docs-freshness-v1.yaml`: flagship docs and release freshness tasks for SDK READMEs, release indexes, and repository files.
- `business/saas-pricing-v1.yaml`: flagship pricing-page tasks for exact plan prices and billing intervals.
- `devtools/dependency-research.yaml`: realistic dependency-research assistant eval.
- `github/example.yaml`: GitHub counts, releases, raw file fields, branches, and licenses backed by public GitHub endpoints.
- `npm/example.yaml`: npm versions, licenses, downloads, repository URLs, package size, and engine constraints backed by npm APIs.
- `finance/yahoo-quotes.yaml`: Yahoo Finance quote fields backed by Yahoo's chart JSON endpoint.
- `mobile-apps/apple-app-store.yaml`: Apple App Store rating and version fields backed by Apple's lookup API.
- `subscription-pricing/example.yaml`: official pricing-page examples backed by regex page extractors.
- `bright-data/rapid-web.yaml`: Bright Data Rapid-mode search, docs, and release checks backed by `search_engine` and `scrape_as_markdown`.
- `bright-data/ecommerce-accuracy-v1.yaml`: focused Samsung ecommerce tasks for page-title, variant, and price extraction.
- `bright-data/linkedin-company.yaml`: LinkedIn company metrics backed by Bright Data structured extraction.
- `bright-data/ecommerce-pricing.yaml`: ecommerce product pricing backed by Bright Data page extraction.

The included packs now contain 79 tasks. The flagship Dev Web Retrieval Eval v1 packs contain 28 tasks with public HTTP JSON and HTTP regex oracles. GitHub, npm, finance, and Apple App Store packs use public APIs. Bright Data Rapid mode powers free-tier-friendly search and page extraction, while the ecommerce accuracy pack demonstrates where Bright Data helps with dynamic product pages and variant-sensitive fields. Bright Data Pro/groups support structured LinkedIn, ecommerce, and future dynamic web packs. Cases that need stronger extraction are tracked in `data/excluded_tasks.json` instead of being silently loosened or counted as agent failures.

More packs are coming. Good contributions include cloud pricing, app stores, finance quotes, docs freshness, model pricing, travel, local business data, and social metrics.

## V3 Final Domains

The V3 external-user task-bank set focuses on three domains:

- Developer dependency and docs research: npm, PyPI, GitHub, release indexes, and official READMEs.
- Ecommerce product and pricing accuracy: exact product, SKU, variant, and price fields from dynamic public pages.
- Company intelligence and public profile metrics: employee and follower fields from required company profiles.

See [../docs/v3-task-banks.md](../docs/v3-task-banks.md) for the final domain rationale, ground-truth strategy, and quarantine/salvage policy.

Create a starter pack:

```bash
python -m agent_royale init task-pack cloud-pricing
```

Create a Bright Data Rapid-mode starter pack:

```bash
python -m agent_royale init task-pack product-pricing --ground-truth bright-data-rapid
```

See [../TASK_PACK_IDEAS.md](../TASK_PACK_IDEAS.md) for task-pack ideas and quality guidance.

## Run One

```bash
python -m agent_royale validate task-packs/github/example.yaml
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/github.html
```

## Notes On Subscription Pricing

Subscription pages are high-value and high-maintenance. Markup, regional defaults, A/B tests, and plan wording can change. The pack keeps that visible by using explicit source URLs, exact plan wording, and source-specific regexes. If one of those parsers stops matching, the right move is to update or quarantine the task, not loosen the scoring.
