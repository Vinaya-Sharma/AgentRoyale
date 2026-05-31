# OpenRouter Model Stack Eval

OpenRouter can be used as the stack under test.

Agent Royale still fetches ground truth independently from the task pack oracle.

```text
OpenRouter model/search stack -> answer + citations
Agent Royale task pack oracle -> ground truth
Agent Royale grader -> exact pass/fail report
```

## Setup

```bash
OPENROUTER_API_KEY=...
```

Do not commit API keys.

## Run A Real Model Stack

```bash
python -m agent_royale run task-packs/github/example.yaml task-packs/npm/example.yaml \
  --target openrouter:openai/gpt-4o-mini \
  --report reports/openrouter-gpt4o-mini-devtools.html
```

## Example Result

A real run against the GitHub and npm task packs produced:

```text
Exact accuracy: 50.0% (4/8)

Passed:
- npm_react_latest
- npm_typescript_license
- github_fastapi_forks
- github_playwright_latest_release

Failed:
- npm_vite_latest: returned an older npm version
- github_vscode_open_issues: returned a nearby but different count
- github_nextjs_stars: returned a nearby but stale count
- npm_next_weekly_downloads: used a non-canonical source
```

The point of this example is not to rank one model forever. The point is to show the workflow:

1. run a model/search stack on source-specific live-web questions
2. fetch independent ground truth
3. catch wrong, stale, nearby, or wrong-source answers
4. generate a report that is useful for debugging and model/provider comparison

Live web results will change. Re-run the pack when you need a current report.
