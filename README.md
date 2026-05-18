# Agent Royale

Agent Royale is an isolated live retrieval benchmark app inside this repo.

For the methodology and product decisions behind the MVP, see
[`docs/DECISIONS.md`](docs/DECISIONS.md).

It uses:

- Bright Data MCP to fetch canonical live sources for ground truth only
- OpenRouter models with `openrouter:web_search` to answer using model/provider search
- deterministic normalization/tolerance rules for grading
- JSONL storage for ground truth, model runs, and votes
- a static UI based on the Agent Royale prototype

## Current MVP Scope

The current runner evaluates OpenRouter models with OpenRouter's web search server tool:

```text
task canonical_url
  -> Bright Data fetches ground truth only
task question
  -> OpenRouter model answers with openrouter:web_search
  -> claim extraction
  -> exact / numeric / currency grading
  -> leaderboard
```

This is enough to test live exact accuracy, Verified Retrieval Rate, latency, estimated cost, and trace voting without giving the model Bright Data ground truth content.

OpenRouter documentation says `openrouter:web_search` uses native provider search for supported providers and falls back depending on model/provider support. The default here sets `AGENT_ARENA_SEARCH_ENGINE=native`.

## Files

```text
agent-arena/
  backend/
    main.py          FastAPI routes
    evaluator.py     ground truth + model run orchestration
    grader.py        prompts, normalization, grading logic
    bright_data.py   Bright Data MCP client
    llm.py           OpenRouter client
    store.py         JSONL persistence + leaderboard math
    task_bank.py     CSV loader
  data/tasks.csv     60-task benchmark bank
  frontend/index.html
  storage/           generated JSONL files
```

## Run

From the isolated project folder:

```bash
cd /Users/vinaya/Desktop/fetch/agent-arena
uvicorn backend.main:app --host 127.0.0.1 --port 8787
```

Then open:

```text
http://127.0.0.1:8787
```

The app reads `OPENROUTER_API_KEY`, `BRIGHT_DATA_API_KEY`, and `BRIGHT_DATA_MCP_URL` from the repo root `.env`, with optional overrides in `agent-arena/.env`.

## API

- `GET /api/config`
- `GET /api/tasks`
- `POST /api/tasks/{task_id}/ground-truth`
- `POST /api/evaluations`
- `POST /api/batch-runs`
- `GET /api/arena/pairs`
- `GET /api/runs`
- `GET /api/leaderboard`
- `POST /api/votes`

Example evaluation:

```bash
curl -X POST http://127.0.0.1:8787/api/evaluations \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"price_001","models":["anthropic/claude-sonnet-4.6","openai/gpt-4o","google/gemini-2.5-pro","perplexity/sonar-pro-search","meta-llama/llama-3.3-70b-instruct"]}'
```

## Default Model Set

- Claude: `anthropic/claude-sonnet-4.6`
- GPT-4o: `openai/gpt-4o`
- Gemini: `google/gemini-2.5-pro`
- Perplexity: `perplexity/sonar-pro-search`
- Llama: `meta-llama/llama-3.3-70b-instruct`

## Batch Runner

Run the full configured model set over the task bank:

```bash
cd /Users/vinaya/Desktop/fetch/agent-arena
python3 run_benchmark.py
```

Useful smoke test:

```bash
python3 run_benchmark.py --domain prices --limit 2 --models openai/gpt-4o,perplexity/sonar-pro-search
```

The runner writes to `storage/ground_truth.jsonl` and `storage/runs.jsonl`. The leaderboard and Arena voting view read from those generated logs.

By default, the batch runner uses three repetitions per task so the leaderboard can report consistency. Perplexity search models are called without `openrouter:web_search` because OpenRouter reports that those endpoints do not support tool use; they are search-native models.
