# Bright Data Ground Truth

Agent Royale runs out of the box without Bright Data using static, GitHub, and npm task packs.

Bright Data is optional. Add it when you want independent ground truth for messier public-web sources such as ecommerce pages, LinkedIn/company profiles, app stores, social pages, travel, local business data, and dynamic pricing pages.

## Setup

Create `.env` or export variables in your shell:

```bash
BRIGHT_DATA_API_KEY=...
BRIGHT_DATA_MCP_URL=https://mcp.brightdata.com/mcp
```

Do not commit `.env`.

## Run A Bright Data Pack

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

## What Gets Reused From V1

The V2 CLI reuses the existing V1 Bright Data client:

- MCP URL/token handling
- Bright Data tool arguments
- LinkedIn and Crunchbase dataset fallbacks
- scrape/direct HTTP fallback chain
- retry and timeout settings
- structured-content extraction

This keeps the V2 runner aligned with the benchmark machinery that powered the original Agent Royale experiment.

## Product Positioning

Use public API packs for the lowest-friction first run.

Use Bright Data packs when the source is the messy live web.

That split is intentional:

```text
No key required: static smoke, GitHub, npm
Bright Data optional: ecommerce, LinkedIn, app stores, social, travel, dynamic pages
```
