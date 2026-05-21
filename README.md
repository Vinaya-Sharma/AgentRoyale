# Agent Royale

Agent Royale is a live-web retrieval benchmark for AI agents.

I built it to answer one practical question:

> When an AI system claims it can search the web, can it actually retrieve the exact current value from the right public source?

The v1 launch site is a frozen snapshot of one experiment: 12 model/retrieval stacks, 43 audited live-web tasks, and 1,548 scored attempts.

The tested stacks were right only 50% of the time. They returned a wrong usable value 38% of the time, and returned no usable answer 13% of the time. The uncomfortable part is that many wrong answers still looked polished and cited legitimate sources.

## Why I Built This

I use AI more and more to find real data quickly: prices, counts, ratings, package versions, finance fields, employee counts, and other public-web facts.

That made me want to know which AI stack I should trust for retrieval-heavy work. The answer from v1 was: none of them without verification.

Most real agent failures are not dramatic. They are boring and expensive: stale prices, wrong source fields, wrong product variants, old cached data, regional mismatches, and citations that do not support the returned value.

Agent Royale makes those failures visible.

## V1 Snapshot

The public v1 site intentionally shows only tasks with complete model coverage.

| Item | V1 value |
| --- | ---: |
| Tasks | 43 |
| Model stacks | 12 |
| Runs per model per task | 3 |
| Scored runs | 1,548 |
| Overall exact accuracy | 50% |
| Wrong usable answer | 38% |
| No usable answer | 13% |
| Best stack in this slice | Grok 4, 73% |

The visible model runs in this snapshot were produced on May 20, 2026 from about 1:48 AM to 3:59 AM Pacific time. Ground-truth records were fetched separately and span May 17-19 Pacific time for the visible slice, which is one reason v2 will refresh ground truth immediately before each task batch.

Topic mix:

| Topic | Tasks |
| --- | ---: |
| Mobile apps | 12 |
| Recruiting / LinkedIn | 9 |
| Finance | 6 |
| Research / developer tools | 6 |
| Social media | 5 |
| Subscriptions | 3 |
| Ecommerce | 2 |

This is a v1 slice, not a universal ranking of every model forever. The task bank is small, the topic mix is uneven, and provider behavior can change.

## What The Site Shows

The launch site is the main deliverable.

- **Home**: the story of the experiment and example failures.
- **Leaderboard**: model ranking by exact accuracy, wrong-answer rate, no-response rate, source matching, latency, and cost.
- **Results**: my interpretation of what the run showed, with topic and repeatability breakdowns.
- **Tasks**: task-level performance and model consistency.
- **Models**: model report cards.
- **Task Bank**: the 43 public v1 tasks and their saved ground-truth evidence.
- **Methodology**: how I built the benchmark, how scoring works, and what I want to improve next.

Some backend files and API endpoints still expose broader development data from benchmark construction. For the v1 launch, the frontend filters the public experience down to the frozen 43-task complete-coverage slice.

## How The Benchmark Works

Each task is a normal source-specific question a person might ask:

```text
Using Yahoo Finance, what is NVDA's current regular-market quote price in USD?
Using Netflix's official US pricing help page, what is the current monthly price of the Standard with ads plan in USD?
Using Stripe's LinkedIn company profile, how many people does LinkedIn currently show as employees?
```

Each task has:

- a required public source
- an expected field
- a ground-truth fetch method
- a grading rule
- a saved evidence snippet or structured field

The model does not see the answer. Separately, Agent Royale fetches ground truth from the required source using Bright Data or a stable public API, then compares the model's extracted claim against that saved value.

There is no LLM judge deciding if an answer "seems right." I avoided an LLM judge because this benchmark is about exact retrieval, not persuasive writing. A judge model might forgive an approximate value, reward a plausible explanation, or miss that the answer used the wrong field. Here, the extracted claim either matches the independently fetched value under the task rule, or it does not.

```text
task question
  -> model retrieves and answers
  -> raw answer is saved
  -> claim is extracted
  -> deterministic grader compares claim to ground truth
  -> result is marked correct, wrong value, or no usable answer
```

## Metrics

- **Live Exact Accuracy**: correct scored runs divided by all scored runs.
- **Wrong Answer Rate**: runs where the model returned a usable value, but it did not match ground truth.
- **No Usable Answer Rate**: refusals, empty responses, or answers that clearly say the model could not find the value.
- **Canonical Source**: among correct answers, whether the model cited a URL matching or overlapping the task's required source.
- **Consistency**: whether a model gets the same task right across repeated attempts.
- **Latency**: elapsed time for the model run.
- **Estimated Cost**: estimated model-call cost when available.

Current citation scoring is intentionally simple. A run gets canonical-source credit when the answer is correct and at least one cited URL matches or overlaps the required source URL. V1 does not yet prove that the exact cited passage supports the exact value.

## Models In V1

I chose a mix of search-native systems, consumer flagships, efficient models, open-weight-style stacks, and reasoning-heavy models.

| Bucket | Models |
| --- | --- |
| Search specialists | Sonar Deep Research, Sonar Pro Search, Grok 4 |
| Consumer flagships | GPT-4o, Claude Sonnet, Gemini Pro |
| Efficient/value models | DeepSeek V4 Flash, Gemini Flash Lite, GPT-4o Mini |
| Open-weight-style stacks | GPT-OSS 120B, Nemotron 3 Super |
| Advanced reasoning | Claude Opus |

Configured model IDs:

```text
anthropic/claude-sonnet-4.6
openai/gpt-4o
google/gemini-2.5-pro
perplexity/sonar-pro-search
perplexity/sonar-deep-research
x-ai/grok-4.3
openai/gpt-4o-mini
openai/gpt-oss-120b
deepseek/deepseek-v4-flash
nvidia/nemotron-3-super-120b-a12b
google/gemini-3.1-flash-lite
anthropic/claude-opus-4.7
```

Perplexity search models are called as search-native endpoints. Other models use the configured OpenRouter search mode.

## What To Keep In Mind

V1 is useful, but it is not final.

- The public task bank has 43 questions.
- The topic split is uneven.
- Ground truth and model runs were timestamped separately in v1.
- Citation scoring checks URL overlap, not passage-level support.
- Provider redirects and citation wrappers are not fully resolved.
- Failure labels are still coarse: correct, wrong value, or no usable answer.

The next run should refresh ground truth per task immediately before model calls, run all models for that task in parallel, store the exact ground-truth snapshot on every model run, and show the ground-truth age next to each result.

## Roadmap

The goal of v2 is to make Agent Royale a decision tool for teams choosing an AI retrieval stack.

Near-term improvements:

- expand the task bank to at least 75 questions
- use a smaller contestant set for cleaner comparison
- refresh ground truth immediately before each model batch
- separate wrong-source, wrong-field, stale-value, unit-mismatch, no-answer, and provider-error failures
- improve citation scoring from URL overlap to evidence-level support
- add confidence intervals and balanced-domain scores
- support custom task-bank upload for team-specific evals
- compare AI-first search systems like Exa and Parallel.ai against traditional search APIs

Planned next contestant set:

```text
Grok 4
Sonar Pro Search
Gemini Pro
Nemotron 3 Super
DeepSeek V4 Flash
GPT-4o
Claude Sonnet
Gemini Flash Lite
```

## Tech Stack

- **Backend**: Python, FastAPI, Uvicorn, Pydantic
- **Model calls**: OpenRouter-compatible OpenAI SDK calls
- **Ground truth**: Bright Data MCP and stable public APIs
- **Frontend**: vanilla HTML, CSS, and JavaScript in one static file
- **Storage**: CSV task bank plus JSONL logs
- **Evaluation**: deterministic exact, numeric, and currency graders

No database or frontend build step is required.

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
    tasks.csv        development task bank
    excluded_tasks.json
  frontend/
    index.html       launch site UI
  storage/           generated JSONL logs and snapshots
  run_benchmark.py   batch runner
  export_launch_snapshot.py
  audit_ground_truth.py
  seed_ground_truth_from_audit.py
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
AGENT_ARENA_MODELS=anthropic/claude-sonnet-4.6,openai/gpt-4o,google/gemini-2.5-pro,perplexity/sonar-pro-search,perplexity/sonar-deep-research,x-ai/grok-4.3,openai/gpt-4o-mini,openai/gpt-oss-120b,deepseek/deepseek-v4-flash,nvidia/nemotron-3-super-120b-a12b,google/gemini-3.1-flash-lite,anthropic/claude-opus-4.7
```

## Run Locally

From the repo root:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8790
```

Then open:

```text
http://127.0.0.1:8790
```

The default app URL in code is still `8787`; using `8790` locally avoids collisions with earlier dev servers.

## Run A Benchmark

Run the configured model set over the task bank:

```bash
python3 run_benchmark.py
```

Useful smoke test:

```bash
python3 run_benchmark.py --domain finance --limit 2 --models openai/gpt-4o,perplexity/sonar-pro-search
```

Generated logs are written to:

```text
storage/ground_truth.jsonl
storage/runs.jsonl
```

Export a launch snapshot after a benchmark run:

```bash
python3 export_launch_snapshot.py
```

## API

Common local endpoints:

```text
GET  /api/health
GET  /api/config
GET  /api/tasks
GET  /api/runs
GET  /api/ground-truth
GET  /api/ground-truth-audit
GET  /api/leaderboard
POST /api/evaluations
POST /api/live-checks
POST /api/batch-runs
```

Example evaluation:

```bash
curl -X POST http://127.0.0.1:8790/api/evaluations \
  -H 'Content-Type: application/json' \
  -d '{
    "task_id": "v1_fin_001",
    "models": [
      "openai/gpt-4o",
      "perplexity/sonar-pro-search"
    ],
    "refresh_ground_truth": true
  }'
```

## License

No license has been added yet. Treat this repository as all rights reserved unless a license file is added.
