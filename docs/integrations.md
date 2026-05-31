# Integrations

Agent Royale is a target-agnostic runner. If a stack can accept a question and return an answer, Agent Royale can grade it against task-pack ground truth.

## GitHub Actions

Use Agent Royale as a CI gate for web-browsing agents:

```bash
python -m agent_royale run task-packs/static-smoke.yaml \
  --target examples/echo_agent.py:answer \
  --report reports/agent-royale.html \
  --fail-under-exact 1.0
```

See [GitHub Actions](github-actions.md).

## OpenAI Agents SDK

The OpenAI Agents SDK example exposes an agent endpoint at `POST /api/agent`.

```bash
cd examples/openai-agent
pip install -r requirements.txt
export OPENAI_API_KEY=...
uvicorn app:app --host 127.0.0.1 --port 3000
```

Then run Agent Royale from the repo root:

```bash
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/openai-agent-github.html
```

The example uses the OpenAI Agents SDK runtime plus `WebSearchTool`. Agent Royale still fetches ground truth independently from the task-pack oracle.

## Bright Data

Agent Royale uses public APIs for GitHub and npm task packs. Bright Data powers reliable web extraction for LinkedIn, ecommerce, app store, and dynamic pricing task packs.

```bash
BRIGHT_DATA_API_KEY=...
python -m agent_royale run task-packs/bright-data/linkedin-company.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/bright-data-linkedin.html
```

See [Bright Data ground truth](bright-data.md).

## Coming Next

These are good contribution areas:

- LangGraph example
- Vercel AI SDK example
- Promptfoo import/export
- Supabase run storage
- JUnit XML output
- Markdown PR summaries
