# Realistic Dev-Agent Eval

The GitHub star-count tasks are useful smoke tests, but most teams should write task packs that mirror their own product workflows.

This example models a practical developer assistant: an agent that researches package upgrades, dependency metadata, and open-source project status before a developer changes dependencies.

## Scenario

You are deciding whether an AI assistant can answer dependency-research questions accurately enough to trust in a developer workflow.

The assistant needs to retrieve exact values such as:

- latest npm package versions
- package license metadata
- GitHub release tags
- exact fields from repository files
- npm download windows
- GitHub repository status fields

Those values are not high stakes by themselves. They are a small, public proxy for the same failure pattern that appears in pricing, compliance, recruiting, finance, ecommerce, and operations workflows: the source can be real while the returned value is stale, rounded, from the wrong field, or from the wrong source.

## Run The Example

```bash
python -m agent_royale validate task-packs/devtools/dependency-research.yaml

python -m agent_royale run task-packs/devtools/dependency-research.yaml \
  --target examples/dev_research_agent.py:answer \
  --report reports/dependency-research.html
```

The target in `examples/dev_research_agent.py` is intentionally realistic rather than perfect. It calls public GitHub and npm APIs, but it has a few plausible retrieval bugs:

- using npm package metadata when the task asks for GitHub Releases
- using last-month downloads when the task asks for last-week downloads
- using GitHub issue search when the task asks for the repository's displayed open count

## What The Result Means

The point is not whether a developer cares about a small difference in a public repository count.

The point is the eval loop:

```text
real workflow questions -> target retrieval stack -> answer -> independent ground truth -> exact report
```

For your own product, replace this task pack with questions that matter to your workflow:

- pricing fields from your required vendors
- compliance or security fields from official docs
- product availability or shipping promises
- package, model, or API compatibility metadata
- finance quote fields from a required source
- recruiting or company fields from a required source

Agent Royale is useful when the grading rule is yours. The example pack only shows how to turn a workflow into concrete source-specific checks.
