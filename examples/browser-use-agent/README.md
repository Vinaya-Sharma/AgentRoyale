# Browser Use Target Example

This example exposes a Browser Use cloud agent as an Agent Royale target.

Agent Royale sends a source-specific task prompt to this local FastAPI app. The app runs Browser Use against the required source and returns answer text, citations, and trace metadata. Agent Royale still fetches ground truth independently through the task pack oracle.

## Setup

```bash
cd examples/browser-use-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BROWSER_USE_API_KEY=...
```

## Start The Target

```bash
uvicorn app:app --host 127.0.0.1 --port 3005
```

## Run Agent Royale

From the repo root:

```bash
python -m agent_royale run task-packs/github/example.yaml \
  --target http://127.0.0.1:3005/api/agent \
  --report reports/browser-use-github.html
```

## Notes

- This example uses Browser Use as the browser-agent layer under test.
- It is useful for comparing full browser agents with search APIs and extraction APIs.
- Agent Royale grades the returned claim against independent ground truth.
