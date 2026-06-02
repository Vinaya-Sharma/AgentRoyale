# Roadmap

Agent Royale should stay narrow enough to be trusted and useful: unit tests for AI agents and retrieval layers that browse the web.

## v0.1: Local Runner

Status: shipped.

- CLI commands: `init`, `validate`, `run`, `report`
- YAML/JSON task packs
- endpoint, Python function, and configured OpenRouter adapter targets
- deterministic grading for exact live-web values
- JSONL run logs
- local HTML reports
- starter task packs for GitHub, npm, subscription pricing, and offline smoke tests

## v0.1.1: Retrieval-Layer Adapter Examples

Status: shipped.

- Tabstack target adapter example
- Firecrawl target adapter example
- Jina Reader free baseline adapter example
- Tavily search/extract adapter example
- Stagehand browser-agent adapter example
- Browser Use browser-agent adapter example
- README target matrix for retrieval-layer evals

## v0.2: CI And Contributor Loop

- GitHub Action examples
- JUnit XML output
- Markdown PR summary output
- richer issue templates
- more polished report screenshots
- task-pack contribution guide
- first wave of community task packs
- OpenAI Agents SDK example
- Bright Data-backed CI workflow docs
- web research API adapter example

## v0.3: Stronger Failure Taxonomy

- wrong field
- stale value
- wrong region
- wrong variant
- unit mismatch
- unsupported citation
- citation support checks beyond URL overlap
- provider failure vs tool failure
- before/after report comparison

## v0.4: Adapter Ecosystem

- provider adapters for common model/search stacks
- custom ground-truth scripts
- browser-agent examples
- web data and browser automation API examples
- LangGraph example
- Vercel AI SDK example
- MCP/tool-server examples
- import/export compatibility with existing eval tools where it helps
- schema-first target response validation

## v0.5: Community Gallery

- public gallery of task packs and reports
- vendor comparison examples
- domain-specific leaderboards
- hosted report viewer if the local workflow has clear traction

## Non-Goals For Now

- Generic subjective LLM evaluation
- Hosted enterprise workspace
- Replacing Promptfoo, LangSmith, Braintrust, or Ragas
- Universal model leaderboard claims

Agent Royale should complement those systems by owning the exact live-web retrieval wedge.
