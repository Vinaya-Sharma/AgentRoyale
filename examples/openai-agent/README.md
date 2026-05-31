# OpenAI Agents SDK Example

This example exposes an OpenAI Agents SDK web agent as an Agent Royale target endpoint.

It is useful for testing the exact question Agent Royale is built around:

```text
Can my agent retrieve the exact current value from the required source?
```

## Setup

```bash
cd examples/openai-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=...
```

## Start The Agent Endpoint

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
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/openai-agent-github.html \
  --fail-under-exact 0.8
```

With Bright Data-backed task packs:

```bash
export BRIGHT_DATA_API_KEY=...
python -m agent_royale run task-packs/bright-data/linkedin-company.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/openai-agent-linkedin.html
```

## Notes

- The agent uses the OpenAI Agents SDK and `WebSearchTool`.
- Agent Royale still fetches ground truth independently through the task pack oracle.
- For GitHub and npm packs, ground truth uses public APIs.
- For Bright Data packs, ground truth uses the configured Bright Data extraction path.
