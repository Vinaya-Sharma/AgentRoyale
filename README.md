# Agent Royale

Agent Royale is a live retrieval benchmark for AI agents.

Static agent benchmarks can become lookup tables: answers leak, tasks get memorized, and evaluators can be gamed. Agent Royale asks a narrower production question:

> Can an AI agent retrieve an exact current fact from the public web, cite the right source, and do it consistently?

The benchmark runs agents against source-specific questions whose answers can change over time, fetches ground truth independently, and scores exact answer quality, citation support, latency, cost, and consistency.

## Why This Exists

AI agents are increasingly used for workflows that depend on current public-web facts: prices, product ratings, app-store metadata, package versions, social metrics, travel listings, company data, finance pages, and documentation.

Traditional static evals are not enough for this kind of system. A model can know an old answer, cite a page that does not support the claim, or perform well on a public benchmark without demonstrating live retrieval ability.

Agent Royale is designed to make that failure visible.

## What It Measures

- **Live exact accuracy**: did the agent return the current correct value?
- **Verified retrieval rate**: did the cited source support the answer?
- **Source quality**: did the agent use the canonical or expected source?
- **Consistency**: does it get the answer across repeated runs?
- **Latency**: how long did the run take?
- **Cost**: what did the model call cost?
- **Trace quality**: which retrieval path was more trustworthy?

## Current MVP

The current implementation evaluates OpenRouter models using provider-native search or OpenRouter web search. Ground truth is fetched separately through Bright Data MCP so the model never receives the evaluator's answer.

```text
task canonical_url
  -> Bright Data MCP fetches live ground truth only

task question
  -> OpenRouter model answers with its own search stack
  -> Agent Royale extracts the claimed value
  -> deterministic grader compares claim vs. live ground truth
  -> leaderboard + arena trace comparison
```

## Tech Stack

- **Backend**: Python, FastAPI, Uvicorn, Pydantic
- **HTTP / clients**: HTTPX, OpenAI SDK-compatible OpenRouter calls
- **Ground truth**: Bright Data MCP
- **Frontend**: vanilla HTML, CSS, and JavaScript in a single static file
- **Storage**: CSV task bank plus JSONL logs
- **Evaluation**: deterministic exact, numeric, and currency graders

No database or frontend build step is required for the MVP.

## Repo Structure

```text
agent-arena/
  backend/
    main.py          FastAPI routes and static frontend serving
    evaluator.py     ground truth + model run orchestration
    grader.py        extraction, normalization, and grading logic
    bright_data.py   Bright Data MCP client
    llm.py           OpenRouter client
    store.py         JSONL persistence + leaderboard math
    task_bank.py     CSV loader
  data/
    tasks.csv        benchmark task bank
    excluded_tasks.json
  frontend/
    index.html       single-page UI
  storage/           generated JSONL logs, ignored by git
  run_benchmark.py   batch runner
  audit_ground_truth.py
```

## Setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create environment variables in `.env` or `agent-arena/.env`:

```bash
OPENROUTER_API_KEY=...
BRIGHT_DATA_API_KEY=...
BRIGHT_DATA_MCP_URL=...
```

Optional settings:

```bash
AGENT_ARENA_SEARCH_ENGINE=native
AGENT_ARENA_DEFAULT_MODELS=anthropic/claude-sonnet-4.6,openai/gpt-4o,google/gemini-2.5-pro,perplexity/sonar-pro-search,meta-llama/llama-3.3-70b-instruct
```

## Run Locally

From the repo root:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8787
```

Then open:

```text
http://127.0.0.1:8787
```

## Run A Batch Benchmark

Run the configured model set over the task bank:

```bash
python3 run_benchmark.py
```

Useful smoke test:

```bash
python3 run_benchmark.py --domain prices --limit 2 --models openai/gpt-4o,perplexity/sonar-pro-search
```

The runner writes generated logs to:

```text
storage/ground_truth.jsonl
storage/runs.jsonl
```

The leaderboard and Arena views read from those logs.

## API

- `GET /api/health`
- `GET /api/config`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/ground-truth`
- `POST /api/evaluations`
- `POST /api/live-checks`
- `GET /api/live-checks`
- `POST /api/batch-runs`
- `GET /api/runs`
- `GET /api/ground-truth`
- `GET /api/leaderboard`
- `GET /api/arena/pairs`
- `GET /api/votes`
- `POST /api/votes`

Example evaluation:

```bash
curl -X POST http://127.0.0.1:8787/api/evaluations \
  -H 'Content-Type: application/json' \
  -d '{
    "task_id": "price_001",
    "models": [
      "anthropic/claude-sonnet-4.6",
      "openai/gpt-4o",
      "google/gemini-2.5-pro",
      "perplexity/sonar-pro-search",
      "meta-llama/llama-3.3-70b-instruct"
    ]
  }'
```

## Task Bank Format

Tasks live in `data/tasks.csv`. The benchmark works best when each task has a source-specific answer that can be fetched and graded reliably.

Good task candidates:

- product prices and availability
- app-store ratings and review counts
- GitHub package versions or repository metadata
- public company profile fields
- hotel or travel listing fields
- docs values, release versions, and changelog facts
- public social or video metrics

Avoid tasks where ground truth is subjective, unstable across sources, hidden behind login, or hard to extract deterministically.

The next product step is custom task-bank upload:

> Upload the questions your product actually depends on. Agent Royale tells you which agent stack is best for your use case.

## Default Model Set

- Claude: `anthropic/claude-sonnet-4.6`
- GPT-4o: `openai/gpt-4o`
- Gemini: `google/gemini-2.5-pro`
- Perplexity: `perplexity/sonar-pro-search`
- Llama: `meta-llama/llama-3.3-70b-instruct`

Perplexity search models are called without `openrouter:web_search` because they are search-native models.

## Roadmap

- Upload custom task banks for team-specific evals
- Validate whether uploaded tasks have reliable ground truth
- Compare model/search/browser/MCP stacks on the same task bank
- Add scheduled regression monitoring for live retrieval quality
- Export eval reports for model selection and vendor comparisons
- Expand hardening checks against answer-key leakage and unsupported citations

## Launch Positioning

If your AI product depends on the live web, static benchmarks are not enough.

Agent Royale helps answer:

> Which agent stack actually retrieves the truth for my use case?
