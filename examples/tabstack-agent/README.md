# Tabstack Target Example

This example exposes Tabstack-powered web research or schema-first extraction as an Agent Royale target.

Agent Royale sends a source-specific task prompt to this local FastAPI app. The app calls Tabstack `/v1/research` or `/v1/extract/json`, converts the response into the Agent Royale target contract, and returns answer text, citations, and trace metadata. Agent Royale still fetches ground truth independently through the task pack oracle.

## Setup

```bash
cd examples/tabstack-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TABSTACK_API_KEY=...
```

Optional settings:

```bash
export TABSTACK_STRATEGY=research
export TABSTACK_RESEARCH_MODE=fast
export TABSTACK_FETCH_TIMEOUT=30
export TABSTACK_TIMEOUT_SECONDS=120
```

Schema-first extraction mode:

```bash
export TABSTACK_STRATEGY=extract_json
export TABSTACK_EXTRACT_EFFORT=standard
```

## Start The Target

```bash
uvicorn app:app --host 127.0.0.1 --port 3000
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
  --target http://localhost:3000/api/agent

python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/tabstack-github.html
```

For a broader public-API pack:

```bash
python -m agent_royale run task-packs/github/example.yaml task-packs/npm/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/tabstack-devtools.html
```

## Notes

- This example uses Tabstack as the target under test.
- Agent Royale grades the returned claim against independent ground truth.
- `/v1/research` maps naturally to question-answer tasks.
- `/v1/extract/json` is useful for schema-first extraction from a required source URL.
- Keep provider-specific costs in `trace.cost_usd` once Tabstack exposes usage or billing metadata in the response.
