# Bright Data Target Example

This example exposes Bright Data as an Agent Royale target adapter.

Agent Royale sends a source-specific task prompt to this local FastAPI app. The app fetches the required source with Bright Data, applies deterministic extraction heuristics for ecommerce-style values, and returns answer text, a citation, and trace metadata. Agent Royale still grades the returned claim against the task pack's independent oracle.

This adapter is most useful for evaluating Bright Data as the retrieval layer behind a product-research or shopping assistant. It is intentionally simple: it tests source fetching plus deterministic extraction, not a general-purpose reasoning agent.

## Setup

```bash
cd examples/bright-data-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BRIGHT_DATA_API_KEY=...
export BRIGHT_DATA_MCP_URL=https://mcp.brightdata.com/mcp
```

Optional settings:

```bash
export BRIGHT_DATA_AGENT_TOOL=scrape_as_markdown
export BRIGHT_DATA_AGENT_TEXT_LIMIT=50000
```

If `BRIGHT_DATA_AGENT_TOOL` is unset, the adapter uses the task pack's Bright Data tool when one is present, then falls back to `scrape_as_markdown`.

## Start The Target

```bash
uvicorn app:app --host 127.0.0.1 --port 3001
```

The endpoint implements the Agent Royale target contract:

```text
POST /api/agent
GET /health
```

## Run Agent Royale

From the repo root:

```bash
python3 -m agent_royale doctor task-packs/bright-data/ecommerce-accuracy-v1.yaml \
  --target http://127.0.0.1:3001/api/agent

python3 -m agent_royale run task-packs/bright-data/ecommerce-accuracy-v1.yaml \
  --target http://127.0.0.1:3001/api/agent \
  --report reports/bright-data-ecommerce-agent.html
```

To run the existing smaller ecommerce pack:

```bash
python3 -m agent_royale run task-packs/bright-data/ecommerce-pricing.yaml \
  --target http://127.0.0.1:3001/api/agent \
  --report reports/bright-data-ecommerce-pricing-agent.html
```

## Notes

- This example uses Bright Data as the target under test.
- Bright Data-backed task packs may also use Bright Data for ground truth, so the report is best interpreted as an extraction and configuration check for this adapter rather than an independent vendor comparison.
- The adapter is tuned for ecommerce values: prices, ratings, review counts, and availability.
- For broader tasks, extend `extract_answer` with source-specific extraction logic or connect a separate extraction model.
