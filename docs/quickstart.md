# Agent Royale Quickstart

Agent Royale is a local runner for testing whether an AI search, RAG, browser, or agent stack returns exact source-specific values.

## Validate A Task Pack

```bash
python -m agent_royale validate task-packs/static-smoke.yaml
python -m agent_royale validate task-packs/github/example.yaml
```

## Run The Offline Smoke Pack

Install locally:

```bash
pip install -e .
agent-royale --version
```

```bash
python -m agent_royale run task-packs/static-smoke.yaml \
  --target examples/echo_agent.py:answer \
  --report reports/smoke.html
```

Run a preflight check before a full eval:

```bash
python -m agent_royale doctor task-packs/static-smoke.yaml \
  --target examples/echo_agent.py:answer
```

Run an intentionally failing demo:

```bash
python -m agent_royale run task-packs/static-smoke.yaml \
  --target examples/flaky_agent.py:answer \
  --report reports/failure-demo.html
```

Or run the same smoke pack against a local HTTP endpoint:

```bash
uvicorn examples.local_agent:app --host 127.0.0.1 --port 3000
python -m agent_royale run task-packs/static-smoke.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/local-agent.html
```

The target can be:

- `http://localhost:3000/api/agent` for a local/prod endpoint.
- `openrouter:provider/model` for an OpenRouter model adapter, if configured.
- `examples/echo_agent.py:answer` for a local Python function.

## Endpoint Contract

Agent Royale sends:

```json
{
  "question": "Using GitHub, how many stars does the vercel/next.js repository currently have?",
  "task": {
    "id": "github_nextjs_stars",
    "required_source": "github.com/vercel/next.js",
    "answer_type": "number"
  }
}
```

Your stack should return:

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

## Minimal Task Schema

```yaml
name: my-task-pack
tasks:
  - id: github_nextjs_stars
    question: "Using GitHub, how many stars does the vercel/next.js repository currently have?"
    required_source: "github.com/vercel/next.js"
    answer_type: number
    tolerance: 0
    labels: [github, devtools]
    ground_truth:
      method: http_json
      url: "https://api.github.com/repos/vercel/next.js"
      field: "stargazers_count"
      source_url: "github.com/vercel/next.js"
```

Supported ground-truth methods:

- `static`: fixed value for smoke tests or manual snapshots.
- `http_json`: fetch JSON and read a dotted field path.
- `http_regex`: fetch text/HTML and capture a value with a regex.
- `bright_data`: optional Bright Data oracle for messy live-web sources.

Supported answer types:

- `string`
- `number`
- `currency`
- `percentage`
- `date`
- `enum`

Create a starter task pack:

```bash
python -m agent_royale init task-pack cloud-pricing
```

## Preflight Checks

`doctor` validates task packs, summarizes ground-truth methods and answer types, checks whether optional integration keys are present, and can probe a target with the first loaded task.

```bash
python -m agent_royale doctor task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent
```

By default, `doctor` does not fetch live oracles. Add `--check-ground-truth` when you want to verify the source parser or API calls before a benchmark run:

```bash
python -m agent_royale doctor task-packs/github/example.yaml --check-ground-truth
```

## CI Thresholds

```bash
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --fail-under-exact 0.8
```

The command exits with status `2` when exact accuracy is below the threshold.

## Example Packs

- `task-packs/github/example.yaml`: repository counts, releases, raw file fields, default branches, and licenses.
- `task-packs/npm/example.yaml`: package versions, license metadata, downloads, repository URLs, package size, and engine constraints.
- `task-packs/finance/yahoo-quotes.yaml`: Yahoo Finance regular-market quote fields.
- `task-packs/mobile-apps/apple-app-store.yaml`: Apple App Store rating and version fields.
- `task-packs/subscription-pricing/example.yaml`: official pricing-page examples with explicit parser notes.

## Realistic Dev-Agent Demo

`examples/dev_research_agent.py` calls public GitHub and npm APIs. It intentionally has a few realistic retrieval bugs, such as using npm package metadata when the task asks for a GitHub release.

```bash
python -m agent_royale run task-packs/github/example.yaml task-packs/npm/example.yaml \
  --target examples/dev_research_agent.py:answer \
  --report reports/dev-agent.html
```

The README report preview is generated from this kind of real run.

## More Docs

- [Task spec](task-spec.md)
- [Adapter contract](adapter-contract.md)
- [Bright Data ground truth](bright-data.md)
- [GitHub Actions](github-actions.md)
- [Task pack ideas](../TASK_PACK_IDEAS.md)
