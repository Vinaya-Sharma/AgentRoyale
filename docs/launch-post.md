# Launch Post Draft

AI agents can cite the right-looking source and still return the wrong live value.

I found this while testing 12 AI search/retrieval stacks across 1,152 scored attempts. Average exact accuracy was only 54%.

So I built Agent Royale:

> Unit tests for AI agents that browse the web.

Agent Royale runs exact, source-specific retrieval tasks against your own AI search, RAG, browser, or agent stack. It refreshes or verifies ground truth separately, extracts the stack's claimed answer, grades deterministically, and produces a report showing:

- exact accuracy
- wrong answers
- no-answer failures
- unsupported citations
- wrong source failures
- latency
- cost
- task-level traces

Example:

```bash
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/github.html \
  --fail-under-exact 0.8
```

The repo includes starter task packs for GitHub metadata, npm packages, subscription pricing, and offline smoke tests.

The goal is not to build another generic eval framework. The goal is narrower:

Can your agent retrieve the exact current value from the required source before users trust it?

Repo: https://github.com/Vinaya-Sharma/AgentRoyale

Contributions welcome:

- task packs
- provider adapters
- report improvements
- failure classifiers
- ground-truth adapters

## X / Twitter

I built unit tests for AI agents that browse the web.

Why? I tested 12 AI search/retrieval stacks across 1,152 attempts. Average exact accuracy was 54%.

The scary part: many wrong answers still cited real-looking sources.

Agent Royale lets you run exact live-web retrieval tests against your own stack:

```bash
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/github.html
```

GitHub/npm/subscription-pricing task packs included. Contributors welcome.

## Hacker News

Title:

```text
Show HN: Agent Royale - unit tests for AI agents that browse the web
```

Body:

```text
I built Agent Royale after testing 12 AI search/retrieval stacks on 1,152 exact live-web retrieval attempts. Average exact accuracy was 54%, and many wrong answers still looked polished and cited legitimate sources.

Agent Royale is a local runner for testing your own AI search/RAG/browser/agent stack against exact, source-specific live-web ground truth. It supports YAML task packs, endpoint/function targets, deterministic grading, JSONL logs, HTML reports, and CI thresholds.

It is not trying to be a generic eval framework. The narrow wedge is: can your agent retrieve the exact current value from the required source?

Feedback and task-pack contributions welcome.
```

## LinkedIn

AI agents can cite the right-looking source and still return the wrong live value.

I saw this directly while testing 12 AI search/retrieval stacks across 1,152 scored attempts. Average exact accuracy was only 54%.

So I built Agent Royale: unit tests for AI agents that browse the web.

It lets builders connect their own AI search, RAG, browser, or agent stack; run exact source-specific live-web tasks; and get a report showing accuracy, wrong answers, unsupported citations, latency, cost, and failure modes.

The goal is not another generic eval framework. The goal is a practical reliability check before users trust your agent with live facts.

The repo includes starter task packs for GitHub metadata, npm packages, subscription pricing, and CI smoke tests. Contributions welcome.
