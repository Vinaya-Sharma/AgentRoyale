# Changelog

## v0.2.6

- Reworked the README around the repeatable product workflow: lint, audit, run, report, and compare.
- Added a no-key golden-path walkthrough for the dependency-research eval.
- Added a corrected dependency-research target so teams can see a concrete before/after comparison from 57.1% to 100.0% exact accuracy on the demo pack.

## v0.2.5

- Added `agent-royale compare` for before/after run comparisons, including exact accuracy, source-supported accuracy, oracle skips, latency, task-level regressions, and optional Markdown output.
- Added `agent-royale lint` for static task-pack checks that catch fragile live-web oracles, broad numeric regexes, volatile CI gates, missing provenance, and weak Bright Data search-result oracles.
- Updated docs with a repeatable engineering workflow: lint task packs, audit oracle health, run only CI-safe packs in builds, and compare candidate runs against a baseline.

## v0.2.4

- Added auditable ground-truth snapshots with oracle status, evidence snippets, parser metadata, and source provenance.
- Added `agent-royale audit` for checking oracle health before running a target.
- Added context-aware regex extraction with `require_near_text` and `reject_near_text`, plus non-scored oracle outcomes for ambiguous or failed ground truth.
- Added `stability`, `ci_safe`, and `run --ci` support so volatile live-web tasks can be reported without blocking builds by default.
- Updated reports to separate Oracle Health from target exact accuracy.

## v0.2.3

- Added a focused Bright Data ecommerce accuracy pack covering Samsung page-title, storage-option, and variant ambiguity.
- Added a Bright Data target adapter example for evaluating Bright Data-backed ecommerce retrieval as an Agent Royale target.

## v0.2.2

- Added a Bright Data Rapid-mode starter template for `agent-royale init task-pack`.
- Expanded Bright Data guidance with a tool-selection table for Rapid mode, structured tools, and public API alternatives.

## v0.2.1

- Clarified report metrics by separating exact-value matches from source-supported matches.
- Reserved unsupported-citation labels for exact answers whose citations do not support the required source.
- Reworked the README explanation around the simplest product loop: task pack, target agent, oracle check, report.

## v0.2.0

- Added Dev Web Retrieval Eval v1 with 28 source-specific tasks across dependency metadata, docs freshness, and SaaS pricing.
- Added a flagship demo target that uses real public sources and intentionally demonstrates wrong-source, wrong-field, and wrong-billing-interval failures.
- Ran and documented launch experiments for the flagship demo target and `openrouter:openai/gpt-4o-mini`.
- Added public experiment documentation and reproducible commands.

## v0.1.3

- Polished the public launch page with clearer product positioning and final UI copy fixes.
- Added launch-ready screenshots for the homepage, task explorer, leaderboard, and dependency-research report.

## v0.1.2

- Added a realistic dependency-research eval pack and walkthrough.
- Reworked the README to lead with the product workflow, expected input/output, and practical launch example.
- Kept the original 32-task experiment as supporting evidence rather than the primary product story.

## v0.1.1

- Added target adapter examples for Tabstack, Firecrawl, Jina Reader, Tavily, Stagehand, and Browser Use.
- Reframed Agent Royale around evaluating AI web retrieval layers with the same task packs and independent ground truth.
- Added a README target matrix covering model web search, web data APIs, URL-to-markdown readers, and browser agents.

## v0.1.0

- Initial local runner with task-pack validation, target execution, deterministic grading, JSONL run logs, and HTML reports.
