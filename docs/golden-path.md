# Golden Path

This walkthrough shows the repeatable Agent Royale loop with no paid API keys:

```text
lint task pack -> audit oracle -> run target -> fix target -> compare runs
```

The example models a developer assistant that answers npm and GitHub metadata questions. The first target has realistic retrieval bugs. The fixed target uses the required source and field for every task.

## 1. Check The Task Pack

```bash
python -m agent_royale lint task-packs/devtools/dependency-research.yaml
python -m agent_royale audit task-packs/devtools/dependency-research.yaml
```

Expected result:

```text
OK task-pack lint found no issues.
verified: 7
Scoreable: 7/7
```

This verifies the test itself before evaluating an agent.

## 2. Run The Imperfect Target

```bash
python -m agent_royale run task-packs/devtools/dependency-research.yaml \
  --target examples/dev_research_agent.py:answer \
  --output runs/dependency-research-before.jsonl \
  --report reports/dependency-research-before.html
```

Current result:

```text
Exact accuracy: 57.1% (4/7 scoreable)
```

The target gets several values right, but it also makes realistic retrieval mistakes:

- uses npm package metadata when the task asks for the latest GitHub release tag
- uses last-month npm downloads when the task asks for last-week downloads
- uses GitHub issue search when the task asks for the repository `open_issues_count` field

## 3. Run The Fixed Target

```bash
python -m agent_royale run task-packs/devtools/dependency-research.yaml \
  --target examples/dev_research_agent_fixed.py:answer \
  --output runs/dependency-research-after.jsonl \
  --report reports/dependency-research-after.html
```

Current result:

```text
Exact accuracy: 100.0% (7/7 scoreable)
```

The fixed target does not become more verbose or more persuasive. It uses the right source and field.

## 4. Compare Before And After

```bash
python -m agent_royale compare \
  runs/dependency-research-before.jsonl \
  runs/dependency-research-after.jsonl \
  --markdown reports/dependency-research-comparison.md
```

Current comparison:

```text
Exact accuracy: 57.1% -> 100.0% (+42.9%)
Source-supported: 57.1% -> 100.0% (+42.9%)
Oracle skips: 0 -> 0
Regressions: 0
Improvements: 3
```

The improved tasks are:

- `github_playwright_latest_release`: wrong source fixed
- `github_vscode_open_issues`: wrong value/field semantics fixed
- `npm_next_weekly_downloads`: wrong source/window fixed

## Why This Matters

This is the core product behavior. Agent Royale is not only a one-time benchmark. It gives teams a way to ask:

- Did a retrieval change improve exact answers?
- Did it create regressions?
- Did the oracle stay healthy?
- Are failures wrong values, wrong sources, unsupported citations, or target errors?
- Should this task be a CI gate or an on-demand live-web report?

For your own agent, replace the example task pack with questions your users actually ask and sources your product actually depends on.
