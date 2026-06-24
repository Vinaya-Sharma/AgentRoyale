# V3 Task Banks

V3 focuses on making Agent Royale usable by external teams who want to bring their own product questions. The final task-bank set should cover three kinds of live-web retrieval work: stable developer metadata, messy ecommerce pages, and dynamic company intelligence.

For the scoring and quarantine mechanics behind these task banks, see the [Reliability model](reliability.md).

## 1. Developer Dependency And Docs Research

Use this domain for agents that help developers choose packages, read SDK docs, or answer release/version questions.

Task packs:

- `task-packs/devtools/dependency-research-v1.yaml`
- `task-packs/devtools/docs-freshness-v1.yaml`

Representative questions:

- Latest npm or PyPI package version
- Package license, repository URL, unpacked size, or runtime requirement
- Latest GitHub release tag
- Current install command or imported client class from an official README
- Latest Node.js release metadata from the official release index

Ground-truth strategy:

- Prefer `http_json` for npm, PyPI, GitHub, and release-index fields.
- Use `http_regex` only for exact README/source-file snippets.
- Keep these tasks CI-friendly when the source is stable enough.

Why this is a final domain:

Developer agents often fail by returning stale versions, wrong fields, or package-manager memory. These tasks are cheap, reproducible, and easy for new users to understand.

## 2. Ecommerce Product And Pricing Accuracy

Use this domain for shopping, product research, pricing, catalog, and competitive-intelligence agents.

Task packs:

- `task-packs/bright-data/ecommerce-accuracy-v1.yaml`
- `task-packs/bright-data/ecommerce-pricing.yaml`

Representative questions:

- Current listed price for a specific product SKU
- Variant-specific price such as a storage option
- Product title and color from the exact source page

Ground-truth strategy:

- Use Bright Data for public product pages that do not expose clean public APIs.
- Route ecommerce oracles through a source-aware fallback ladder:

```text
structured ecommerce tool -> scrape_as_markdown -> scrape_as_html -> direct_http -> quarantine/browser workflow
```

- Require exact source URLs, SKU/variant wording, nearby context, and conservative regexes.
- Mark volatile product tasks as `ci_safe: false` and use them for scheduled or on-demand reports.

Why this is a final domain:

Ecommerce is where generic model search often looks plausible but returns the wrong product, region, variant, or stale price. It also shows why Bright Data and browser-style extraction matter.

## 3. Company Intelligence And Public Profile Metrics

Use this domain for sales, recruiting, investor research, CRM enrichment, and market-intelligence agents.

Task pack:

- `task-packs/bright-data/linkedin-company.yaml`

Representative questions:

- LinkedIn employee count for a required company profile
- LinkedIn follower count for a required company profile
- Company-profile metrics across OpenAI, Anthropic, Databricks, and NVIDIA

Ground-truth strategy:

- Use Bright Data structured company-profile extraction when available.
- Read exact fields such as `employees_in_linkedin` and `followers`.
- Use tolerances for volatile public metrics while still rejecting wrong fields such as company-size ranges or follower/employee swaps.

Why this is a final domain:

Company-intelligence agents frequently confuse nearby public metrics. This domain tests whether the stack can retrieve the exact metric from the exact profile instead of returning a plausible estimate.

## Quarantine And Salvage Policy

The goal is not to avoid hard questions. The goal is to avoid scoring a target against unverified ground truth.

When a task cannot retrieve a reliable oracle value, Agent Royale should:

1. Identify the failure mode: unreachable source, broken selector, ambiguous candidates, low-confidence evidence, tool error, or rendered-page gap.
2. Try a stronger oracle path before giving up.
3. Export the issue with `audit-errors`.
4. Move the task into the salvage backlog if it still cannot be verified.
5. Keep the task out of scoreable reports until the oracle can fetch one supported value.

This keeps user questions from being silently discarded while protecting benchmark credibility.

## V3 Demo Flow

```bash
python -m agent_royale validate task-packs
python -m agent_royale audit task-packs/bright-data
python -m agent_royale audit-errors task-packs/bright-data \
  --output reports/bright-data-error-audit.md
python -m agent_royale sweep task-packs/devtools/dependency-research.yaml \
  --models openai/gpt-4o,google/gemini-3-1-flash-lite
```

The story to show externally: define your task bank, audit the oracle, run your agent or model stack, inspect the report, then use salvage output to strengthen any task that could not retrieve ground truth.
