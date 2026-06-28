# V3 Progress Summary

This document summarizes the recent Agent Royale work: reliability upgrades, Bright Data task-pack cleanup, report UX improvements, and the latest targeted rerun results.

## Current Positioning

Agent Royale is a testing layer for AI agents and retrieval stacks that browse the web. Teams write source-specific questions in task banks, Agent Royale fetches independent ground truth, runs the target agent/model/tool stack, and grades whether the answer is exact, source-supported, and citation-backed.

The current V3 focus is external-user reliability:

- make ground-truth extraction more robust
- make task quarantine/salvage transparent
- make reports easier to understand quickly
- communicate why developers can trust the automated grading scheme

## Major Changes Shipped

### 1. Stronger Grading And Provenance

The runner now records richer grading fields:

- `value_correct`
- `source_correct`
- `citation_supports_claim`
- `final_verdict`
- `grading_trace`
- `citation_checks`
- task-pack metadata and stable task hashes
- oracle status and ground-truth snapshots

This makes report output more explainable and separates wrong values, wrong sources, unsupported citations, and oracle issues.

Related commits:

- `a9daa49` Strengthen grading reliability and reports

### 2. Demo And Sweep Commands

Added easier ways to demonstrate and compare stacks:

- `agent-royale demo`
- `agent-royale sweep`
- ranked sweep summaries with recommendations and outcome breakdowns

Related commit:

- `51de90a` Add demo and sweep commands

### 3. Bright Data Task-Pack Stabilization

Audited Bright Data-backed task packs and tightened public scoreable tasks.

Changes included:

- versioned Bright Data task packs
- tightened ambiguous regexes for Rapid-mode tasks
- replaced broad/flaky Samsung storage-options extraction with narrower Samsung price extraction
- replaced the failing Best Buy scoreable task with a reliable Samsung product-price task
- kept Best Buy in a public salvage/quarantine trail instead of hiding it

At that point, the Bright Data-backed oracle audit verified `13/13` scoreable tasks.

Related commits:

- `ba59848` Stabilize Bright Data task packs
- `70a7ff8` Document oracle salvage workflow

### 4. Oracle Salvage Routing

Added source-aware Bright Data fallback routing for ecommerce pages:

```text
structured ecommerce tool -> scrape_as_markdown -> scrape_as_html -> direct_http -> quarantine/browser workflow
```

The runner now knows to try structured ecommerce tools for supported domains such as Best Buy, Walmart, eBay, Home Depot, and Amazon before generic page extraction. It also treats structured tool error payloads as failures, instead of accepting error text as valid evidence.

Related commit:

- `eca124b` Add oracle salvage routing

### 5. V3 Task-Bank Focus

Defined three final V3 task-bank domains:

1. Developer dependency and docs research
2. Ecommerce product and pricing accuracy
3. Company intelligence and public profile metrics

The repo now has a dedicated V3 task-bank doc explaining the domain rationale, ground-truth strategy, and quarantine/salvage policy.

Related commit:

- `c44a5c7` Define V3 task bank focus

### 6. Reliability Documentation

Added diagrams and tables explaining why the tool is reliable:

- trust pipeline
- scoreable vs. quarantined task flow
- Bright Data salvage routing
- ground-truth paths
- report fields and what they prove
- failure modes and product actions

The README now links to the reliability model so users can understand the grading system without overloading the report itself.

Related commit:

- `9630ee7` Explain reliability model with diagrams

### 7. Report UX Improvements

The HTML report was redesigned from raw eval output into a decision dashboard.

Added:

- source-supported accuracy as the main score
- decision summary
- denominator-aware metrics
- scoreable tasks
- oracle skips not scored
- median/p95 latency
- reported cost
- "What To Fix Next" cards
- outcome breakdown bar
- task-level summary
- cleaner task details

Then the report was simplified based on mentor feedback:

- visible table now focuses on agent answer vs. ground truth
- tool usage moved into its own column
- repeated visible claim/evidence clutter removed
- methodology/explainer content moved to docs
- "Oracle verified" removed from per-row outcome badges
- long task IDs now wrap cleanly in fix-next cards

Related commits:

- `f1291fa` Polish HTML report decision UX
- `de80ade` Refresh flagship report assets
- `9f4c00e` Simplify HTML report outcomes
- `2fb3a1d` Refresh README report screenshots
- `f02a7ee` Wrap fix-next report cards

## Current Report Assets

Regenerated flagship reports:

- `reports/stack-fit-v1/bright-data-dynamic-ecommerce.html`
- `reports/stack-fit-v1/openrouter-dev-web-retrieval.html`
- `reports/dev-web-retrieval-v1/flagship-demo.html`

Updated screenshots:

- `docs/assets/launch/v3-report-decision-dashboard.png`
- `docs/assets/report-preview.png`
- experiment screenshots under `docs/assets/experiments/`

The README now shows the cleaner report dashboard and explains that reports are built for quick decisions: agent answer vs. ground truth, tool used, source-supported accuracy, scoreable tasks, oracle skips, latency, reported cost, failure breakdowns, and fix-next guidance.

## Latest Targeted Bright Data Rerun

To avoid wasting credits, only the current problematic tasks were rerun.

### Verified

`bd_rapid_mcp_free_requests`

- status: verified
- value: `5,000`
- source: Bright Data MCP Server docs
- artifact: `reports/targeted-bright-data-rapid-rerun.jsonl`

`bd_rapid_python_latest_release`

- status: verified
- value: `3.14.6`
- source: `python.org/downloads`
- artifact: `reports/targeted-bright-data-rapid-rerun.jsonl`

### Samsung Salvaged

`bd_ecom_v1_samsung_s25_ultra_512gb_price`

- status: verified
- value: `1419.99`
- tool: `scrape_as_html` after `scrape_as_markdown` selector miss
- source: Samsung Galaxy S25 Ultra product page
- artifact: `reports/targeted-samsung-512gb-fix-rerun.jsonl`

The old markdown-only attempt saw storage labels:

```text
Storage Storage 256GB 512GB 1TB
```

But it did not include the prices near that storage section. The task now points at Samsung's canonical 512GB SKU page and verifies the price from Samsung's Product JSON-LD/schema.org offer in the HTML fallback, anchored to `SM-S938UZKEXAA` and `priceCurrency: USD`.

## Open Bright Data Questions

These are the useful questions to ask Tomer/Bright Data:

1. For Samsung product pages, is there a structured product collector that exposes variant prices directly, or should Agent Royale keep using HTML/schema.org fallback for SKU-level prices?
2. For the quarantined Best Buy product page, should the next attempt use `web_data_bestbuy_products`, a different URL pattern, or a rendered/browser workflow?

## Current State

Shipped and pushed:

- reliability model docs
- V3 task-bank docs
- Bright Data salvage workflow
- oracle salvage routing
- cleaner HTML report UX
- refreshed README and screenshots
- targeted Bright Data rerun artifacts

Still open:

- decide whether Samsung variant prices should use a structured Bright Data collector when available, or keep the current HTML/schema.org fallback
- decide the best Bright Data path for Best Buy product pages
- optionally add a rendered/browser workflow once the best collector path is confirmed
- eventually add comparison-focused HTML reports for before/after or multi-stack sweeps

## Verification Commands Recently Run

```bash
python3 -m agent_royale validate task-packs
python3 -m agent_royale lint task-packs/bright-data
python3 -m compileall agent_royale/report.py
```

The Bright Data lint still has one expected warning for the Rapid search-result demo because search-result ordering is a weaker oracle than a required-source page scrape.
