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

Rapid-mode packs use `search_engine` and `scrape_as_markdown`, so they are the best Bright Data first run for developers using the MCP free tier.

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

## Run The Ecommerce Accuracy Pack

The ecommerce accuracy pack is the most complete Bright Data domain example in the repo. It keeps the first public ecommerce example focused on one dynamic Samsung product page and tests page-title, variant, and price extraction that the current markdown oracle can verify. Product pages that return empty content or hide the needed value behind heavier rendering should move into the oracle salvage backlog until a rendered Browser API or structured workflow can verify them:

```bash
python -m agent_royale validate task-packs/bright-data/ecommerce-accuracy-v1.yaml
python -m agent_royale run task-packs/bright-data/ecommerce-accuracy-v1.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/bright-data-ecommerce-accuracy.html
```

You can also run it against the Bright Data target adapter:

```bash
cd examples/bright-data-agent
pip install -r requirements.txt
export BRIGHT_DATA_API_KEY=...
uvicorn app:app --host 127.0.0.1 --port 3001

cd ../..
python -m agent_royale run task-packs/bright-data/ecommerce-accuracy-v1.yaml \
  --target http://127.0.0.1:3001/api/agent \
  --report reports/bright-data-ecommerce-agent.html
```

## Task Shape

Use `agent-royale init` when you want a starter pack with the Bright Data shape already wired:

```bash
python -m agent_royale init task-pack product-pricing --ground-truth bright-data-rapid
python -m agent_royale validate task-packs/product-pricing/example.yaml
```

Then replace the example URL and regex with the exact source and field your agent depends on.

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

This is the free-tier-friendly shape when used with `search_engine` or `scrape_as_markdown`.

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
Bright Data Rapid mode: search results, docs pages, public pages, simple dynamic pages via search_engine and scrape_as_markdown
Bright Data Pro/groups: ecommerce, LinkedIn, app stores, social, travel, browser automation, structured data
```

## Choosing A Bright Data Path

| Source type | Recommended oracle | Why |
|---|---|---|
| Search-result ordering or source discovery | `search_engine` | Keeps the task close to what a search-backed agent sees. |
| Public docs, release pages, pricing pages | `scrape_as_markdown` with a narrow regex | Works in Rapid mode and keeps the parser auditable. |
| Pages where markdown misses the needed field | `scrape_as_html` fallback | Preserves more page structure for source-specific regexes. |
| LinkedIn company fields | `web_data_linkedin_company_profile` or the dataset fallback | Avoids confusing followers, employee ranges, and rendered page noise. |
| Ecommerce product pages | Structured `web_data_*` tools when available; otherwise markdown plus a conservative regex | Product pages often mix sale price, list price, installments, and trade-in values. |
| Public APIs with exact fields | `http_json` instead of Bright Data | Cheaper, faster, and easier to reproduce. |

Good Bright Data tasks should name the exact source, exact field, expected region or variant, and common wrong nearby values. If the parser stops matching, update or quarantine the task instead of widening the regex until unrelated values pass.

## Oracle Salvage Log

Live-web task packs should improve by making the oracle stronger, not by hiding hard cases. When an oracle cannot fetch the page, finds multiple plausible values, or needs a rendered/browser workflow, keep the case in a backlog with the failure mode and next tool to try.

Current examples:

| Task | Status | Why it is not scoreable yet | Next step |
|---|---|---|---|
| `bd_bestbuy_airpods_pro_price` | quarantined | Best Buy returned empty content through the current Bright Data markdown/html/direct fallback path. | Rebuild with a rendered Browser API workflow or a structured ecommerce endpoint before scoring. |
| `bd_ecom_v1_samsung_s25_ultra_storage_options` | retired after audit | The markdown page interleaved prices between storage labels, making a broad storage-options answer brittle. | Keep narrower Samsung variant/price tasks that the oracle can verify deterministically. |
