# Stagehand Target Example

This example exposes Stagehand browser extraction as an Agent Royale target.

Agent Royale sends a source-specific task prompt to this local FastAPI app. The app opens the required source with Stagehand, asks Stagehand to extract the single requested value, and returns answer text, citations, and trace metadata. Agent Royale still fetches ground truth independently through the task pack oracle.

## Setup

```bash
cd examples/stagehand-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BROWSERBASE_API_KEY=...
```

Optional settings:

```bash
export STAGEHAND_MODEL=google/gemini-3-flash-preview
```

## Start The Target

```bash
uvicorn app:app --host 127.0.0.1 --port 3004
```

## Run Agent Royale

From the repo root:

```bash
python -m agent_royale run task-packs/github/example.yaml \
  --target http://127.0.0.1:3004/api/agent \
  --report reports/stagehand-github.html
```

## Notes

- This example uses Stagehand as the browser automation layer under test.
- It is useful for tasks where a real browser session matters more than plain HTTP extraction.
- Agent Royale grades the returned claim against independent ground truth.
