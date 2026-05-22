# Agent Royale

**Evaluating AI stacks in live-web environments.**

Agent Royale is a live-web retrieval benchmark for AI search systems. I built it to test one narrow question:

> Can AI search stacks retrieve exact, current values from the public web when the answer has to match a specific source?

In the public v1 run, I tested 12 model/retrieval stacks on 32 source-specific live-web tasks. Each model answered each task 3 times, producing 1,152 scored attempts.

The tested stacks returned the exact right value 54% of the time. They returned a wrong usable value 33% of the time, and returned no usable answer 13% of the time. The most uncomfortable part is that many wrong answers still looked polished and cited legitimate sources.

## Why This Exists

I have started relying on AI more and more to find real data quickly: prices, counts, ratings, versions, finance fields, company metrics, and sources I do not want to manually dig through.

The answers often look confident. They cite links. They sound useful.

But citation is not the same as correctness.

Most real retrieval failures are boring but expensive: stale prices, wrong quote fields, company-size ranges instead of employee counts, wrong regions, wrong product variants, and citations that look right but do not support the answer. Agent Royale is my attempt to measure that failure directly.

## V1 Results

| Metric | Value |
| --- | ---: |
| Public task bank | 32 tasks |
| Model stacks | 12 |
| Runs per model per task | 3 |
| Scored attempts | 1,152 |
| Correct exact values | 619 |
| Wrong usable values | 385 |
| No-answer responses | 148 |
| Average exact accuracy | 54% |
| Top stack accuracy | 78% |

The best stack in this run was Grok 4 at 78% exact accuracy. Even that means it missed roughly 1 in 5 exact values.

### Results By Model

| Model stack | Accuracy | Wrong | No answer | Canonical source |
| --- | ---: | ---: | ---: | ---: |
| Grok 4 | 78% | 21% | 1% | 85% |
| Gemini Pro | 64% | 30% | 6% | 82% |
| Nemotron 3 Super | 61% | 31% | 7% | 83% |
| Sonar Pro Search | 59% | 29% | 11% | 79% |
| DeepSeek V4 Flash | 57% | 29% | 14% | 95% |
| GPT-4o Mini | 56% | 42% | 2% | 78% |
| Gemini Flash Lite | 54% | 46% | 0% | 0% |
| Claude Sonnet | 53% | 46% | 1% | 76% |
| GPT-4o | 52% | 48% | 0% | 82% |
| Claude Opus | 46% | 50% | 4% | 34% |
| GPT-OSS 120B | 35% | 18% | 47% | 97% |
| Sonar Deep Research | 28% | 11% | 60% | 96% |

### Results By Topic

| Topic | Tasks | Accuracy | What broke most often |
| --- | ---: | ---: | --- |
| Subscriptions | 3 | 80% | Plans and prices were comparatively easier when pages exposed clean values. |
| Mobile apps | 7 | 71% | Ratings and counts were easier, but source and freshness still varied. |
| Finance | 6 | 70% | Models confused live quote fields, stale values, close prices, and alternate sources. |
| Ecommerce | 2 | 63% | Product pages were workable, but price extraction still failed under page noise. |
| Research / dev | 3 | 38% | Package, repository, and metadata tasks exposed stale search results and wrong fields. |
| Social media | 5 | 37% | Counts changed often, sources were inconsistent, and models leaned on stale snippets. |
| Recruiting / LinkedIn | 6 | 23% | Models mixed up followers, employee ranges, and structured employee fields. |

## What The Site Shows

The launch site is the main deliverable.

- **Home**: the experiment narrative, headline stats, and examples where models cited real sources but returned wrong values.
- **Leaderboard**: exact accuracy, wrong-answer rate, no-response rate, source checks, latency, and estimated cost across the 32-task public v1 snapshot.
- **Live Check**: a demo loop where you can pick one task and selected models, refresh live ground truth, run the models, extract their claims, and grade them on demand.
- **Tasks**: task-level performance, model consistency, saved ground truth, citations, and failure patterns.
- **Models**: report cards for each model stack.
- **Methodology**: the complete explanation of why I built the benchmark, how task design works, how ground truth is fetched, how scoring works, what v1 found, and what changes next.

The Task Bank and Results views still exist in the frontend code as analysis/evidence pages, but they are hidden from the public navigation for this launch.

## Methodology

I made the task rubric fixed, but the answer live.

Each task has a:

- required public source
- target field
- tolerance or normalization rule
- deterministic grading rule
- saved ground-truth value
- source URL, timestamp, and evidence

The model gets a normal source-specific question, but it does not get the saved answer.

Separately, Agent Royale fetches ground truth from the required source using Bright Data or a stable public API. The grader then compares the model's extracted claim against that independently fetched value.

```text
question
  -> model stack with web retrieval
  -> raw answer and citations
  -> extracted value
  -> compare to saved ground truth
  -> stored result
```

There is no LLM judge deciding whether an answer "seems right." I avoided LLM judging because this benchmark is about exact retrieval, not persuasive writing. A judge model might reward a plausible explanation, forgive an approximate value, or miss that the answer used the wrong field. Here, the extracted claim either matches the independently fetched source value or it does not.

## Task Design

Each task is written like a real user question, but constrained enough to have one answer I can verify.

For example:

```text
Using Yahoo Finance, what is NVDA's current regular-market quote price in USD?
Using Netflix's official US pricing help page, what is the current monthly price of the Standard with ads plan in USD?
Using Stripe's LinkedIn company profile, how many people does LinkedIn currently show as employees?
```

I chose dynamic web facts so the model has to engage in retrieval instead of relying on memorized static answer keys. The candidate pool included finance, ecommerce, app stores, LinkedIn/company metrics, social metrics, developer tools, subscriptions, real estate, travel, and business intelligence.

For the public v1 launch, I only show tasks where every model had complete coverage: 3 clean runs for each of the 12 model stacks. After trimming overweighted app, LinkedIn, and developer tasks, that left 32 tasks in the frozen public benchmark.

## Model Selection

I tested practical stacks people might actually choose: consumer flagships, search-first systems, efficient/value models, open-weight-style stacks, and advanced reasoning models.

| Bucket | Models in v1 | Why I included them |
| --- | --- | --- |
| Consumer flagships | GPT-4o, Claude Sonnet, Gemini Pro | The models many people reach for first. |
| Search specialists | Sonar Deep Research, Sonar Pro Search, Grok 4 | Stacks that explicitly position around live information or search. |
| Efficient/value | DeepSeek V4 Flash, Gemini Flash Lite, GPT-4o Mini | Cheaper or faster options that teams might use at scale. |
| Open-weight style | GPT-OSS 120B, Nemotron 3 Super | Infrastructure-style stacks where strict extraction and formatting matter. |
| Advanced reasoning | Claude Opus | A test of whether more reasoning helps with contradictory or stale web data. |

Configured model IDs:

```text
anthropic/claude-sonnet-4.6
anthropic/claude-opus-4.7
openai/gpt-4o
openai/gpt-4o-mini
openai/gpt-oss-120b
google/gemini-2.5-pro
google/gemini-3.1-flash-lite
perplexity/sonar-pro-search
perplexity/sonar-deep-research
x-ai/grok-4.3
deepseek/deepseek-v4-flash
nvidia/nemotron-3-super-120b-a12b
```

By model stack, I mean the model plus the retrieval path used in this runner. That matters because builders do not deploy a base model alone; they deploy a model connected to search, citations, routing, provider behavior, and tool configuration.

## Metrics

- **Live Exact Accuracy**: correct scored runs divided by all scored runs.
- **Wrong Answer Rate**: runs where the model returned a usable value, but it did not match ground truth.
- **No Answer Rate**: refusals, empty responses, or answers that clearly said the model could not find the value.
- **Canonical Source**: among correct answers, whether a cited URL matched or overlapped the required source URL.
- **Latency**: measured runtime for the model run.
- **Estimated Cost**: directional cost estimate based on model pricing; cost was not a controlled factor in v1.
- **Consistency**: whether a model got the same task right across repeated attempts.

Canonical Source is intentionally limited in v1. It is a reference signal, not proof that the cited passage fully supports the answer. It is rare but possible that the ideal source URL is imperfect, and it is also possible that the correct answer appears on other legitimate sites.

## What To Keep In Mind

This is one v1 run, not a universal ranking of every model forever.

- The public task bank has 32 questions.
- The domain mix is uneven.
- The leaderboard is a frozen snapshot from one experiment.
- Ground truth and model runs were timestamped separately in v1.
- Citation scoring checks URL overlap, not passage-level support.
- Estimated cost is directional, not actual provider billing.
- Provider behavior, model routing, search tools, and web pages can all change.

The most important limitation is timing: the model calls ran in about 2 hours and 11 minutes, but many saved ground-truth values were fetched earlier. In v2, I will refresh ground truth immediately before each task's model calls.

## What Comes Next

V2 will be stricter, cleaner, and more useful for decisions.

Planned improvements:

- larger and more balanced task bank
- new ground-truth pipeline
- ground truth refreshed immediately before each task's model calls
- exact ground-truth snapshot stored on every model run
- accurate cost logging from provider usage data
- stronger citation verification beyond URL overlap
- clearer failure labels: wrong source, wrong field, stale value, unit mismatch, unsupported claim, no answer, and provider/API failure
- smaller model set tested more rigorously
- decision views for cheapest acceptable, fastest accurate, safest, and most reliable retrieval stacks by domain
- custom task-bank upload so teams can evaluate stacks against their own workflows

The goal is to turn Agent Royale from a one-off experiment into a decision tool for teams choosing AI search and retrieval stacks.

## Contact

I built Agent Royale as a starting point for testing AI retrieval stacks against the task banks that actually matter to a team.

If you want to test your own source-specific questions, reach out:

```text
Vinaya Sharma
vinayasharma00@gmail.com
```

## Tech Stack

- **Backend**: Python, FastAPI, Uvicorn, Pydantic
- **Model calls**: OpenRouter-compatible API calls
- **Ground truth**: Bright Data and stable public APIs
- **Frontend**: vanilla HTML, CSS, and JavaScript in one static file
- **Storage**: CSV task bank plus JSONL logs
- **Evaluation**: deterministic exact, numeric, and currency graders

No database or frontend build step is required.

## Repo Structure

```text
agent-arena/
  backend/
    main.py          FastAPI routes and frontend serving
    evaluator.py     ground-truth refresh and model-run orchestration
    grader.py        extraction, normalization, and grading helpers
    extractors.py    source-specific ground-truth extractors
    bright_data.py   Bright Data client
    llm.py           OpenRouter client
    store.py         JSONL persistence and leaderboard math
    task_bank.py     CSV task-bank loader
  data/
    tasks.csv        development task bank
    excluded_tasks.json
  frontend/
    index.html       launch site UI
  storage/
    ground_truth.jsonl
    runs.jsonl
    v1_ground_truth_audit.csv
    launch-snapshots/
  run_benchmark.py
  audit_ground_truth.py
  export_launch_snapshot.py
  seed_ground_truth_from_audit.py
```

Some historical audit files and development probes remain in the repository because they document how the task bank was constructed. The public v1 site filters the visible benchmark down to the frozen 32-task launch set.

## Setup

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create environment variables in `.env` or copy from `.env.example`:

```bash
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
BRIGHT_DATA_API_KEY=...
BRIGHT_DATA_MCP_URL=https://mcp.brightdata.com/mcp
AGENT_ARENA_SEARCH_ENGINE=native
```

Optional model override:

```bash
AGENT_ARENA_MODELS=anthropic/claude-sonnet-4.6,openai/gpt-4o,google/gemini-2.5-pro
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

You can also open the static frontend directly at `frontend/index.html`, but the live backend features need the FastAPI server.

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
