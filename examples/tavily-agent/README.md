# Tavily Target Example

This example exposes Tavily search or extraction as an Agent Royale target.

Agent Royale sends a source-specific task prompt to this local FastAPI app. The app calls Tavily, converts the response into the Agent Royale target contract, and returns answer text, citations, and trace metadata. Agent Royale still fetches ground truth independently through the task pack oracle.

## Setup

```bash
cd examples/tavily-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export TAVILY_API_KEY=...
```

Source-specific extraction mode:

```bash
export TAVILY_STRATEGY=extract
```

Search mode:

```bash
export TAVILY_STRATEGY=search
export TAVILY_SEARCH_DEPTH=basic
export TAVILY_MAX_RESULTS=5
```

## Start The Target

```bash
uvicorn app:app --host 127.0.0.1 --port 3003
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
  --target http://127.0.0.1:3003/api/agent

python -m agent_royale run task-packs/github/example.yaml \
  --target http://127.0.0.1:3003/api/agent \
  --report reports/tavily-github.html
```

## Notes

- This example uses Tavily as the target under test.
- `extract` is usually the better fit for tasks with a required source URL.
- `search` is useful for broader discovery tasks where the target must find candidate sources.
- Agent Royale grades the returned claim against independent ground truth.
