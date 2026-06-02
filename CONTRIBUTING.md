# Contributing To Agent Royale

Agent Royale is built around a narrow idea: exact, source-specific live-web retrieval should be testable.

The easiest way to contribute is to add task packs, adapters, graders, and report improvements that make that idea more useful for real builders.

## Good First Contributions

- Add a task pack for a domain you know well.
- Improve a flaky subscription-pricing parser.
- Add a ground-truth adapter for a stable public API.
- Add a provider or endpoint adapter.
- Add a LangGraph, OpenAI Agents SDK, or Vercel AI SDK example.
- Improve the HTML report.
- Add a failure classifier for wrong field, stale value, wrong region, or wrong variant.
- Add docs for a real stack integration.

## Add A Task Pack

1. Create a YAML file under `task-packs/<domain>/example.yaml`.

```bash
python -m agent_royale init task-pack cloud-pricing
```

2. Keep each task source-specific and exact.
3. Include clear `notes` explaining the oracle and common failure modes.
4. Validate locally:

```bash
python -m agent_royale validate task-packs
```

5. If the pack can run without secrets, include a sample command in your PR.

See [TASK_PACK_IDEAS.md](TASK_PACK_IDEAS.md) for domains that would be useful to add.

## Good Tasks

Good Agent Royale tasks ask for one value from one required source.

Good:

```text
Using npm, what is the latest published version of the react package?
Using GitHub, how many stars does the vercel/next.js repository currently have?
Using Netflix's official US pricing help page, what is the monthly price of Standard with ads?
```

Avoid:

```text
What is the best AI search tool?
How many people work at OpenAI?
Summarize the latest React news.
```

Those are either subjective, multi-source, or too broad for deterministic grading.

## Ground Truth Rules

The oracle must be stricter than the model under test.

- Prefer stable public APIs when possible.
- Use page regexes only when the source is valuable enough to maintain.
- Store source URLs and task notes.
- If an oracle drifts, update or quarantine the task instead of loosening the grader silently.
- Do not use an LLM judge for exact retrieval tasks unless the task clearly labels that scoring mode.

## Task Pack Quality Checklist

- The question names the source the agent should use.
- The required source matches the oracle source.
- The ground-truth method fetches the value independently from the target agent.
- The task is not account-specific or dependent on a personalized page.
- The tolerance is as strict as the source allows.
- The `notes` field explains what values should be rejected.

## Pull Request Checklist

- [ ] Task packs validate with `python -m agent_royale validate task-packs`.
- [ ] Smoke run still passes.
- [ ] Docs mention any new command, adapter, or output.
- [ ] New task packs explain the ground-truth source in `notes`.
- [ ] No secrets, generated reports, or local run logs are committed.
