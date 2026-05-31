# GitHub Actions

Agent Royale can run in CI as a retrieval reliability gate.

The most common pattern is:

1. validate task packs
2. start or point at the stack under test
3. run Agent Royale with `--fail-under-exact`
4. upload the HTML report as a build artifact

## Offline Smoke Check

Use this first to confirm the runner, schema, and report generation work in CI without network access or API keys.

```yaml
name: Agent Royale Smoke

on:
  pull_request:
  push:
    branches: [main]

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Validate task packs
        run: python -m agent_royale validate task-packs

      - name: Run smoke eval
        run: |
          python -m agent_royale run task-packs/static-smoke.yaml \
            --target examples/echo_agent.py:answer \
            --report reports/agent-royale-smoke.html \
            --fail-under-exact 1.0

      - name: Upload report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: agent-royale-smoke-report
          path: reports/agent-royale-smoke.html
```

## Test A Local Endpoint

If your agent runs as a local service in CI, start it before the Agent Royale step.

```yaml
name: Agent Royale Endpoint Eval

on:
  pull_request:

jobs:
  endpoint-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - uses: actions/setup-node@v4
        with:
          node-version: "22"

      - name: Install Agent Royale dependencies
        run: pip install -r requirements.txt

      - name: Install app dependencies
        run: npm ci

      - name: Start local agent
        run: npm run dev &

      - name: Wait for local agent
        run: |
          for i in {1..30}; do
            curl -fsS http://localhost:3000/health && exit 0
            sleep 2
          done
          exit 1

      - name: Run GitHub metadata eval
        run: |
          python -m agent_royale run task-packs/github/example.yaml \
            --target http://localhost:3000/api/agent \
            --report reports/github-metadata.html \
            --fail-under-exact 0.8

      - name: Upload report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: agent-royale-github-report
          path: reports/github-metadata.html
```

## Test A Configured OpenRouter Adapter

Use this only when your OpenRouter model/provider setup is intentionally part of the stack being tested. The adapter should be treated as configured infrastructure, not as a promise that every model supports live search.

```yaml
name: Agent Royale OpenRouter Eval

on:
  workflow_dispatch:

jobs:
  openrouter-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run npm package eval
        env:
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
        run: |
          python -m agent_royale run task-packs/npm/example.yaml \
            --target openrouter:provider/model \
            --report reports/npm-openrouter.html \
            --fail-under-exact 0.7

      - name: Upload report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: agent-royale-openrouter-report
          path: reports/npm-openrouter.html
```

## Thresholds

`--fail-under-exact` exits with status `2` when exact accuracy is below the threshold.

Good starting points:

- `1.0` for offline smoke packs
- `0.8` for mature internal task packs
- `0.6` for new exploratory live-web packs

Keep thresholds honest. If a source gets flaky, update or quarantine the task instead of lowering the standard silently.
