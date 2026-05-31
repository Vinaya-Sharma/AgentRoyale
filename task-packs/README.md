# Agent Royale Task Packs

These packs are intentionally small, readable, and source-specific. They are examples of the V2 direction: developers should be able to inspect the task, understand the oracle, and decide whether the task is fair for their stack.

## Packs

- `static-smoke.yaml`: offline target-contract smoke tests.
- `github/example.yaml`: GitHub repository metadata backed by the GitHub REST API.
- `npm/example.yaml`: npm package metadata backed by npm registry and downloads APIs.
- `finance/yahoo-quotes.yaml`: Yahoo Finance quote fields backed by Yahoo's chart JSON endpoint.
- `mobile-apps/apple-app-store.yaml`: Apple App Store rating and version fields backed by Apple's lookup API.
- `subscription-pricing/example.yaml`: official pricing-page examples backed by regex page extractors.
- `bright-data/linkedin-company.yaml`: LinkedIn company metrics backed by Bright Data extraction.
- `bright-data/ecommerce-pricing.yaml`: ecommerce product pricing backed by Bright Data extraction.

The included packs now contain 32 tasks. GitHub, npm, finance, and Apple App Store packs use public APIs. Bright Data powers reliable web extraction for LinkedIn, ecommerce, and future dynamic web packs.

More packs are coming. Good contributions include cloud pricing, app stores, finance quotes, docs freshness, model pricing, travel, local business data, and social metrics.

## Run One

```bash
python -m agent_royale validate task-packs/github/example.yaml
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/github.html
```

## Notes On Subscription Pricing

Subscription pages are high-value and high-maintenance. Markup, regional defaults, A/B tests, and plan wording can change. The pack keeps that visible by using explicit source URLs, exact plan wording, and source-specific regexes. If one of those parsers stops matching, the right move is to update or quarantine the task, not loosen the scoring.
