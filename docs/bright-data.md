# Bright Data Ground Truth

Agent Royale uses public APIs for GitHub and npm task packs. Bright Data powers reliable web extraction for docs pages, ecommerce, LinkedIn, app store, and dynamic pricing task packs.

Bright Data documents a free MCP tier with 5,000 requests per month. Rapid mode is enabled by default and supports search plus `scrape_as_markdown`; Pro mode adds structured data tools, browser automation, and domain-specific tool groups.

## Setup

Create `.env` or export variables in your shell:

```bash
BRIGHT_DATA_API_KEY=...
BRIGHT_DATA_MCP_URL=https://mcp.brightdata.com/mcp
```

Do not commit `.env`.

## Run A Rapid-Mode Pack

Rapid-mode packs use `scrape_as_markdown`, so they are the best Bright Data first run for developers using the MCP free tier.

```bash
python -m agent_royale doctor task-packs/bright-data/rapid-web.yaml --check-ground-truth
python -m agent_royale run task-packs/bright-data/rapid-web.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/bright-data-rapid.html
```

## Run A Pro/Structured Pack

Structured Bright Data tools such as `web_data_linkedin_company_profile` require Pro mode or explicit tool/group configuration:

```bash
BRIGHT_DATA_MCP_PRO_MODE=1
```

or:

```bash
BRIGHT_DATA_MCP_GROUPS=social,ecommerce
```

```bash
python -m agent_royale validate task-packs/bright-data
python -m agent_royale run task-packs/bright-data/linkedin-company.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/bright-data-linkedin.html
```

If `BRIGHT_DATA_API_KEY` is missing, Agent Royale will fail the run with a clear message and suggest using the public API packs instead.

## Task Shape

Structured Bright Data tool:

```yaml
ground_truth:
  method: bright_data
  tool: web_data_linkedin_company_profile
  url: "https://www.linkedin.com/company/openai/"
  field: "0.employees_in_linkedin"
```

Page extraction with regex:

```yaml
ground_truth:
  method: bright_data
  tool: scrape_as_markdown
  url: "https://example.com/pricing"
  regex: "Pro[\\s\\S]{0,800}?\\$\\s*([0-9]+(?:\\.[0-9]{2})?)"
```

This is the free-tier-friendly shape when used with `scrape_as_markdown`.

## What Gets Reused From The Experiment

The local runner reuses the Bright Data client built for the original experiment:

- MCP URL/token handling
- Bright Data tool arguments
- LinkedIn and Crunchbase dataset fallbacks
- scrape/direct HTTP fallback chain
- retry and timeout settings
- structured-content extraction

This keeps the runner aligned with the benchmark machinery that powered the original Agent Royale experiment.

## Product Positioning

Use public API packs for the lowest-friction first run.

Use Bright Data packs when the source is the messy live web.

That split is intentional:

```text
No key required: static smoke, GitHub, npm
Bright Data Rapid mode: docs pages, public pages, simple dynamic pages via scrape_as_markdown
Bright Data Pro/groups: ecommerce, LinkedIn, app stores, social, travel, browser automation, structured data
```
