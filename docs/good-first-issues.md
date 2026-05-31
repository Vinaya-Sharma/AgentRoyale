# Good First Issues To Open Before Launch

These are ready-made issue ideas for turning launch attention into contributor activity.

## Task Packs

1. `Task pack: cloud pricing`
   Add exact source-specific tasks for AWS, GCP, or Azure pricing pages.

2. `Task pack: app store metadata`
   Add iOS or Google Play rating/version/count tasks with stable ground truth.

3. `Task pack: finance quotes`
   Add exact quote-field tasks for Yahoo Finance or another stable public source.

4. `Task pack: docs freshness`
   Add tasks for latest docs version, release date, or API reference facts.

5. `Task pack: model pricing`
   Add source-specific pricing tasks for model providers.

## Adapters

6. `Adapter: custom ground-truth script`
   Let tasks call a local Python script as the oracle.

7. `Adapter: JavaScript function target`
   Add `file.js:function` target support for Node/TypeScript users.

8. `Adapter: JUnit XML output`
   Emit CI-friendly JUnit results.

9. `Adapter: Markdown PR summary`
   Generate a short Markdown report suitable for GitHub comments.

10. `Example: LangGraph agent endpoint`
    Add a LangGraph example that exposes `POST /api/agent` and can be tested with Agent Royale.

11. `Example: Vercel AI SDK endpoint`
    Add a Next.js/Vercel AI SDK route that implements the Agent Royale target contract.

## Reports

12. `Report: before/after comparison`
    Compare two JSONL runs and show regressions.

13. `Report: failure mode cards`
    Make wrong source, wrong value, no answer, and unsupported citation visually distinct.

14. `Report: task-pack summary`
    Group report rows by labels/domain.

## Grading And Failure Modes

15. `Classifier: wrong field`
    Detect common cases where a model returns stars instead of forks, annual instead of monthly pricing, etc.

16. `Classifier: stale value`
    Label near-but-old values separately from arbitrary wrong answers.

17. `Grader: date tolerance`
    Add date tolerance for tasks where timezone or publication date boundaries matter.

Open these with the issue templates in `.github/ISSUE_TEMPLATE/`. Label the easiest ones `good first issue`.
