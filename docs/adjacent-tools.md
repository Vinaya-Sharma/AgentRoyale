# Adjacent Tools

Agent Royale is designed to work alongside web execution and web data APIs, not replace them.

## Tabstack

[Tabstack](https://www.producthunt.com/products/tabstack) is a web data and browser automation API. Its Product Hunt page describes a system that accepts a URL and schema, returns structured JSON, runs browser automations, and exposes a research endpoint for cited answers from the live web. The Tabstack site positions the product as "the web execution layer for AI" with endpoints for extraction, generation, browser automation, and research.

Agent Royale sits on the evaluation side of that workflow:

| Area | Tabstack | Agent Royale |
|---|---|---|
| Primary job | Execute web research, extraction, and browser automation | Test whether an agent or retrieval stack returns the exact source-specific value |
| User input | URL, schema, task, or research question | Task pack, target endpoint, grading rule, and independent ground-truth source |
| Output | Structured data, cited answers, or browser-automation results | Accuracy report, failure labels, citations check, latency, cost, and run logs |
| Infrastructure role | Production API used inside an app or agent | Local/CI eval harness used before and after deploying a stack |
| Success condition | The API completes the requested web task | The returned claim matches independently fetched ground truth |

The practical relationship is complementary: a team could use a tool like Tabstack as the target under test, then use Agent Royale to measure whether that target is reliable for the exact live-web values their product depends on.

## Useful Inspiration

Tabstack highlights a few product ideas that fit Agent Royale's public roadmap:

- Schema-first workflows: make it easy to validate structured answer shapes before grading the value.
- One-call research targets: support adapters for web research APIs where the target returns answer text, citations, and metadata in one response.
- Citation transparency: continue moving from URL overlap checks toward stronger evidence that the cited page actually supports the returned value.
- Cost predictability: report cost per run and cost per correct answer clearly enough for teams choosing between retrieval stacks.
- Production-oriented docs: document how to evaluate external web execution APIs without requiring users to rewrite their agent.

Agent Royale should keep its narrower scope. It should not become a browser automation platform or general web extraction API. Its job is to make those systems measurable.
