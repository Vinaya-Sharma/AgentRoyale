# Adapter Contract

Agent Royale can test any stack that accepts a question and returns an answer with optional citations and trace metadata.

## Target Types

Endpoint:

```bash
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent
```

Python function:

```bash
python -m agent_royale run task-packs/static-smoke.yaml \
  --target examples/echo_agent.py:answer
```

Configured OpenRouter adapter:

```bash
python -m agent_royale run task-packs/npm/example.yaml \
  --target openrouter:provider/model
```

Treat the OpenRouter adapter as configured infrastructure. Do not assume every model/provider path supports live retrieval.

## Endpoint Request

Agent Royale sends a POST request:

```json
{
  "question": "Using GitHub, how many stars does the vercel/next.js repository currently have?",
  "task": {
    "id": "github_nextjs_stars",
    "question": "Using GitHub, how many stars does the vercel/next.js repository currently have?",
    "required_source": "github.com/vercel/next.js",
    "answer_type": "number",
    "tolerance": 0,
    "labels": ["github", "repository_metadata"],
    "ground_truth": {
      "method": "http_json"
    }
  }
}
```

## Expected Response

```json
{
  "answer": "129000",
  "citations": [
    {
      "url": "https://github.com/vercel/next.js",
      "quote": "129k stars"
    }
  ],
  "trace": {
    "search_queries": ["vercel next.js GitHub stars"],
    "tools_used": ["web.search"],
    "latency_ms": 4210,
    "cost_usd": 0.012
  }
}
```

Only `answer` is required. Citations and trace fields make reports more useful.

## Python Function Contract

```python
def answer(question: str, task: dict) -> dict:
    return {
        "answer": "$19.00",
        "citations": [
            {"url": "https://example.com/pricing", "quote": "Pro plan $19.00"}
        ],
        "trace": {"tools_used": ["example.search"], "cost_usd": 0.0},
    }
```

Async functions are supported.

## Citation Honesty

Agent Royale checks whether cited URLs overlap the required source and whether citation quotes support the extracted claim when a quote is provided.

If your stack cannot provide source support, return the answer anyway, but expect reports to label citation support separately from exact value accuracy.
