# Agent Arena Decision Log

This document records the product, methodology, and implementation decisions made while building the Agent Arena MVP. It is meant to be useful later when writing a paper, explaining the benchmark, or revisiting why the system is shaped this way.

## Core Benchmark Definition

Agent Arena evaluates live web retrieval, not broad reasoning or summarization.

The central question is:

```text
Can an AI agent retrieve a specific current value from the live web and return it correctly?
```

We intentionally narrowed the scope to exact retrieval because it makes the benchmark more objective. The model is not rewarded for a fluent summary, a plausible explanation, or a partially useful answer. It must find the current value requested by the task.

This supports four research questions:

- Do search-augmented AI agents still hallucinate on live web tasks?
- Can agents reliably find and extract specific values from the live web?
- Do agents take efficient, source-appropriate paths?
- Which model is best for production retrieval when accuracy, cost, latency, and path quality are considered together?

## Task Design Decisions

Tasks must satisfy four criteria:

- **Live:** the answer changes frequently enough that memorization is unreliable.
- **Verifiable:** the answer exists as a specific value on a public canonical URL.
- **Retrieval-dependent:** the model should need live access, not training memory.
- **Differentiating:** the task should produce spread across models, not all-pass or all-fail.

Task wording should be humane and source-specific at the same time. The model should see a normal question, but the question must still identify the source or field tightly enough that the evaluator can grade one deterministic answer. For example, "How many people work at OpenAI?" is too broad because LinkedIn, Crunchbase, and news sources may disagree. "Using OpenAI's Crunchbase company profile, what employee-count or company-size value does Crunchbase currently list?" is fair because the source and expected field are explicit.

We added verticals because users care about different retrieval domains:

- Recruiting / LinkedIn
- E-commerce
- Business Intelligence
- Social Media
- Research / Dev
- Mobile Apps
- Finance / Investing

Why this matters: an overall leaderboard is useful, but production users will eventually care more about model performance in their vertical.

## Ground Truth Decision

Bright Data is used only for evaluation ground truth.

Models do not receive Bright Data output. They answer using their own search capability through OpenRouter or a search-native model endpoint.

Reason:

If the model used Bright Data content directly, the benchmark would test whether it can read supplied data, not whether it can retrieve the data itself. The key product and research claim is about the model/provider retrieval stack.

The intended flow is:

```text
Bright Data fetches canonical source -> ground truth value
Model uses its own search stack -> answer + citations
Claim extraction -> exact comparison against ground truth
```

## Model Search Decision

Most models are called through OpenRouter with `openrouter:web_search`.

Perplexity is treated differently because OpenRouter reported that `perplexity/sonar-pro-search` does not support the web-search tool interface. It is search-native, so it is called directly without attaching `openrouter:web_search`.

Default model set:

- `anthropic/claude-sonnet-4.6`
- `openai/gpt-4o`
- `google/gemini-2.5-pro`
- `perplexity/sonar-pro-search`
- `meta-llama/llama-3.3-70b-instruct`
- `perplexity/sonar-pro`
- `openai/gpt-4o-mini`

We avoided broken aliases such as `anthropic/claude-sonnet-latest` after OpenRouter returned errors for them.

## Accuracy Grading Decision

Accuracy is automated.

The system extracts the model's key claim from its natural-language answer, normalizes it, and compares it against the ground truth.

Grading modes include:

- exact string match
- numeric range
- currency exact
- currency range
- structured match

We use tolerance for values where tiny differences or rounding are acceptable. For example, price or count tasks may allow small numeric tolerance, while version strings or exact fee tasks require exact matching.

Why not use an LLM judge:

LLM judges introduce subjective ambiguity. This benchmark is designed around exact retrieval, so pass/fail should be grounded in deterministic comparison wherever possible.

## Claim Extraction Decision

Models answer naturally instead of being forced into structured output.

A lightweight extraction step pulls the specific value from the answer.

Reason:

This makes the benchmark closer to how users interact with these systems in real products while still allowing automatic grading.

Risk:

Claim extraction can create false negatives if the extractor includes harmless text such as `Version 26.17.76` instead of `26.17.76`. We fixed this for common cases by improving normalization, but extraction quality remains part of the benchmark infrastructure risk.

## Verified Retrieval Rate

We renamed the retrieval-source metric to **Verified Retrieval Rate**.

Definition:

```text
Among correct answers, what percentage cited or fetched a source matching the canonical source?
```

Reason:

Accuracy alone cannot distinguish a genuinely retrieved answer from a lucky or memorized one. Verified Retrieval Rate gives a source-backed confidence signal.

Important caveat:

The current matching is URL-based and strict-ish. It may undercount cases where a model uses an equivalent official page that differs from the configured canonical URL.

## Consistency Decision

The official benchmark runs each task three times per model.

Reason:

Live retrieval agents can be flaky. A single pass/fail hides whether the model is reliable or just got lucky once.

The three-run design enables:

- `3/3`, `2/3`, `1/3`, `0/3` task consistency
- per-model consistency summaries
- identification of flaky tasks and models

This is important for production use. A model that is occasionally correct is different from a model that reliably retrieves the same live value.

## Path Efficiency Decision

Path quality is separate from accuracy.

Only runs that pass accuracy should be considered for path voting. A model should not be rewarded for taking an efficient path to a wrong answer.

Automated path signals:

- search calls
- cited URLs
- latency
- cost
- whether canonical source appears

Human path voting:

Humans compare two correct anonymous traces and vote on which route was more direct, reliable, and source-appropriate.

Reason:

Automated metrics cannot fully judge whether a retrieval route was sensible. Five cited URLs may be fine if they are authoritative and needed. Two URLs may be bad if they are the wrong source. Pairwise human preference captures this nuance better than a numeric rubric.

## Cited URLs vs Search Calls

We clarified the UI distinction:

- **Search calls:** provider/tool usage count, when OpenRouter reports it.
- **Cited URLs:** URLs attached to the model's answer.

Important:

One search call can produce many cited URLs. The trace display currently shows cited URLs, not necessarily individual tool calls.

Why this matters:

Users were confused by cases where `Search calls = 1` but the trace showed 5-10 URLs. This is expected behavior when a provider returns multiple citations from one search-backed answer.

## Arena Decision

Arena is for human path optimality voting only.

It does not run new evaluations. It samples from stored benchmark runs where both paths are correct.

Arena UI decisions:

- models are hidden before voting as `Path A` and `Path B`
- model identities are revealed only after the vote
- users can mark whether either path was ideal
- arrows navigate between pairs
- no reload button, because the pair bank is not expected to change often during a session

Reason:

Blind voting reduces brand bias. Revealing models after voting makes the experience satisfying and transparent without contaminating the vote.

## Ideal Route Signal

We added optional checkboxes:

- `Path A is ideal`
- `Path B is ideal`

Definition:

An ideal route is the route a careful human would naturally take for the task.

Reason:

Pairwise votes answer "which path was better?" The ideal-route signal answers a different question: "was either path actually human-quality?"

This can later support metrics such as:

- percentage of correct runs judged human-like
- model ideal-route rate
- cases where a model wins pairwise but still is not ideal

We avoided framing this as "can AI replace humans" in the UI because that wording is loaded. The operational version is more useful: did the model take the route a careful human would take?

## Live Check Decision

Live Check is separate from Arena and Leaderboard.

Purpose:

Let users run individual tasks on demand to verify that the framework can retrieve fresh live data.

Live Check is explicitly a demo / spot-check page.

Logging:

- official benchmark runs go to `storage/runs.jsonl`
- ad hoc live checks go to `storage/live_checks.jsonl`

Reason:

Ad hoc user runs should not affect leaderboard ratios. Users may rerun unusually hard, interesting, or viral tasks, which would bias official scores.

The UI now explains that Live Check runs are logged separately and never affect leaderboard rankings.

## Leaderboard Logging Decision

Leaderboard reads from official benchmark runs only.

It filters to configured default models and uses the latest three runs per task/model. This prevents earlier debug runs, duplicate manual runs, or obsolete model IDs from polluting the official leaderboard.

After the Netflix pricing issue, we added a second filter: only tasks whose canonical ground truth can be freshly verified are counted in the official leaderboard. Tasks that fail strict ground-truth validation are quarantined in `data/excluded_tasks.json`. They remain visible for inspection, but they do not affect rankings.

Reason:

During development, we produced extra rows while debugging. The leaderboard must reflect the benchmark design, not the history of local experimentation.

Current official model-run shape:

```text
79 official tasks x 7 models x 3 repetitions = 1,659 intended benchmark runs
```

The storage file may contain more rows because it preserves debug history, retries, and older runs. Leaderboard computation is responsible for selecting the official slice.

Current strict-validation slice after audit:

```text
79 verified official tasks x 7 models x 3 repetitions = 1,659 official scored runs after a complete full sweep
```

Not every topic necessarily has full results at all times during development. For example, business intelligence was promoted after the first major run and then evaluated separately. The UI now tells users when a topic has official audited tasks but no model runs yet.

## JSONL Storage Decision

We use append-only JSONL files:

- `storage/ground_truth.jsonl`
- `storage/runs.jsonl`
- `storage/live_checks.jsonl`
- `storage/votes.jsonl`

Reason:

JSONL is simple, inspectable, and durable for an MVP. It makes it easy to audit individual rows, reproduce leaderboard calculations, and debug failures.

Implementation notes:

- JSON is written with `ensure_ascii=True` to keep each JSONL record physically one line even when scraped pages include Unicode line separators.
- The reader skips malformed historical rows so one interrupted scrape cannot poison the entire benchmark cache.

Future:

A database would make sense once there are many benchmark runs, users, vote sessions, and model versions.

## Bright Data Fallback Decision

Ground truth fetches attempt:

```text
preferred Bright Data tool -> scrape_as_markdown -> scraping_browser -> direct_http fallback
```

Reason:

Some Bright Data endpoints returned empty content, no response, or TaskGroup errors. A fallback chain keeps the benchmark from failing on one brittle fetch mode.

Caveat:

Direct HTTP fallback is less robust than Bright Data for blocked or dynamic pages. When fallback is used, it should be treated as an evaluator reliability compromise, not the ideal final architecture.

Observed cases:

- Product Hunt homepage blocked fresh evaluator access after an earlier successful scrape.
- DOL required a simpler user-agent to avoid a 403.
- A USCIS canonical URL had gone stale and was updated to a working official page.
- Crunchbase generic fetches failed, but the managed Crunchbase dataset returned a deterministic `num_employees` value. Successful managed-dataset audits take priority over older failed generic scrape attempts.

## Product Hunt / Social Task Decision

`social_004` was difficult because Product Hunt blocked fresh homepage retrieval.

We eventually used cached ground truth from the earlier successful Product Hunt fetch to complete the two missing consistency runs.

Reason:

This preserved the original task semantics without changing the source mid-benchmark.

Caveat:

For future benchmark rigor, `social_004` should probably be replaced or redesigned around an official accessible feed or API-like source. Product Hunt's RSS feed was reachable, but switching to it changes the task from "top product on the homepage" to "feed-derived product."

## UI Information Architecture

Current pages:

- **Live Check:** ad hoc demo runs on individual tasks
- **Leaderboard:** official model rankings
- **Methodology:** explanation of benchmark mechanics
- **Tasks:** per-task drilldown with model results, ground truth, accuracy filters, and run history
- **Models:** model report cards with vertical breakdowns, flaky tasks, and recent failures
- **Ground Truth Audit:** public methodology surface showing scored/quarantined decisions, evidence, source, and saved answer

Hidden / deferred:

- **Arena:** blind path voting over correct stored traces. It still exists in code/API but is hidden from the main navigation for v1 because the leaderboard, task bank, model scorecards, and ground-truth audit are more central.

Reason:

Users first want the leaderboard, then they want proof. Per-task and per-model drilldowns will answer "why did this model win or fail?"

## Arena Voting Guidance

We added guidance because users may otherwise interpret path quality as "fewest URLs wins."

Voting guidance:

- vote for the path that is more direct, reliable, and source-appropriate
- do not simply vote for fewer citations
- use human intuition when the guidelines are not enough
- mark ideal if the route resembles what a careful human would naturally do

Example:

For an Apple price task, a path that uses Apple's official buy page is better than one that mixes Apple pages with Walmart, blogs, old newsroom posts, or education pricing.

Important nuance:

More sources are not inherently bad. More sources are bad when they indicate wandering, stale information, irrelevant sources, wrong region, or wrong product variant.

## Cost and Latency Decision

Cost and latency are logged per run, but current cost is an estimate.

Reason:

OpenRouter pricing varies by model and provider. The MVP uses transparent rough estimates until provider billing ingestion is added.

Future:

Use actual API usage and billing metadata if available.

## Limitations

Current limitations to mention in any paper or public writeup:

- Ground truth extraction still uses an LLM after fetching canonical content.
- Some canonical pages are difficult to scrape reliably.
- URL-based Verified Retrieval Rate can undercount equivalent official sources.
- OpenRouter citation behavior varies by model/provider.
- Search-call count is not always a full step-by-step browser trace.
- Costs are estimates, not billing-grade values.
- The task bank is broad but not exhaustive.
- Results are snapshots tied to model versions and evaluation dates.
- Live values can change between ground truth fetch and model answer.

## Future Work

High-value next steps:

- Add failure-mode labels: stale value, wrong page, wrong region, wrong SKU, no canonical citation, extraction mismatch.
- Add deterministic ground-truth extractors for high-value task types.
- Store model version/date metadata more explicitly.
- Add actual OpenRouter cost ingestion.
- Replace fragile sources with stable public canonical sources where possible.
- Add vertical leaderboards.
- Add custom task-bank upload and automatic ground-truth audit before scoring.
- Add downloadable/public launch reports from `export_launch_snapshot.py` outputs.
