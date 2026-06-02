# Firecrawl Target Example

This example exposes Firecrawl `/v2/scrape` JSON-mode extraction as an Agent Royale target.

Agent Royale sends a source-specific task prompt to this local FastAPI app. The app calls Firecrawl with a JSON schema, converts the response into the Agent Royale target contract, and returns answer text, citations, and trace metadata. Agent Royale still fetches ground truth independently through the task pack oracle.

## Setup

```bash
cd examples/firecrawl-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FIRECRAWL_API_KEY=...
```

Optional settings:

```bash
export FIRECRAWL_STRATEGY=scrape_json
export FIRECRAWL_TIMEOUT_SECONDS=120
export FIRECRAWL_FETCH_TIMEOUT_MS=60000
export FIRECRAWL_MAX_AGE_MS=0
```

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
python -m agent_royale doctor task-packs/github/example.yaml \
  --target http://127.0.0.1:3001/api/agent

python -m agent_royale run task-packs/github/example.yaml \
  --target http://127.0.0.1:3001/api/agent \
  --report reports/firecrawl-github.html
```

For a broader public-API pack:

```bash
python -m agent_royale run task-packs/github/example.yaml task-packs/npm/example.yaml \
  --target http://127.0.0.1:3001/api/agent \
  --report reports/firecrawl-devtools.html
```

## Notes

- This example uses Firecrawl as the target under test.
- Agent Royale grades the returned claim against independent ground truth.
- The adapter uses Firecrawl `/v2/scrape` with a JSON format object and a small answer schema.
- Keep provider-specific costs in `trace.cost_usd` once usage or billing metadata is available in the response.
