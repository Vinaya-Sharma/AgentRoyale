# Jina Reader Target Example

This example exposes Jina Reader as an Agent Royale target.

Agent Royale sends a source-specific task prompt to this local FastAPI app. The app fetches the required source through `https://r.jina.ai`, extracts a candidate value from the returned markdown, and returns answer text, citations, and trace metadata. Agent Royale still fetches ground truth independently through the task pack oracle.

## Setup

```bash
cd examples/jina-reader-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Jina Reader can be used without an API key at lower rate limits. Optionally set a key for higher limits:

```bash
export JINA_API_KEY=...
export JINA_READER_TIMEOUT_SECONDS=60
```

## Start The Target

```bash
uvicorn app:app --host 127.0.0.1 --port 3002
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
  --target http://127.0.0.1:3002/api/agent

python -m agent_royale run task-packs/github/example.yaml \
  --target http://127.0.0.1:3002/api/agent \
  --report reports/jina-reader-github.html
```

## Notes

- This example is a free URL-to-markdown baseline.
- It is intentionally simple: Jina Reader retrieves markdown, and the local adapter extracts common exact values with deterministic patterns.
- Agent Royale grades the returned claim against independent ground truth.
