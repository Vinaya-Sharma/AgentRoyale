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

Agent Royale uses public APIs for GitHub and npm task packs. Bright Data Rapid mode powers free-tier-friendly `scrape_as_markdown` task packs, while Bright Data Pro/groups support structured LinkedIn, ecommerce, app store, and dynamic pricing task packs.

```bash
BRIGHT_DATA_API_KEY=...
python -m agent_royale run task-packs/bright-data/linkedin-company.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/bright-data-linkedin.html
```

See [Bright Data ground truth](bright-data.md).

## OpenRouter

Use OpenRouter as the model/search stack under test:

```bash
OPENROUTER_API_KEY=...
python -m agent_royale run task-packs/github/example.yaml task-packs/npm/example.yaml \
  --target openrouter:openai/gpt-4o-mini \
  --report reports/openrouter-gpt4o-mini-devtools.html
```

Agent Royale still grades against independent task-pack ground truth.

See [OpenRouter model stack eval](openrouter.md).

## Web Data And Browser Automation APIs

Production agents may rely on web data, browser automation, or research APIs rather than owning the whole browsing stack. Agent Royale can still evaluate those systems as long as they expose a target endpoint that accepts a task prompt and returns an answer with optional citations.

For example, a target endpoint can wrap a web research API, forward the Agent Royale question, and return the API's answer text, citations, latency, and cost metadata. Agent Royale then grades the claimed value against independent task-pack ground truth.

See the [Tabstack target example](../examples/tabstack-agent/README.md) for a local adapter that can evaluate Tabstack research or schema-first extraction as an Agent Royale target.

See the [Firecrawl target example](../examples/firecrawl-agent/README.md) for a local adapter that can evaluate Firecrawl `/v2/scrape` JSON-mode extraction as an Agent Royale target.

See the [Jina Reader target example](../examples/jina-reader-agent/README.md) for a free URL-to-markdown baseline adapter.

## Coming Next

These are good contribution areas:

- LangGraph example
- Vercel AI SDK example
- Promptfoo import/export
- Supabase run storage
- JUnit XML output
- Markdown PR summaries
