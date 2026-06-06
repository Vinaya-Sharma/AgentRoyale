# Agent Royale Comparison

- Before: `runs/stack-fit-v1/tavily-search-known-source.jsonl`
- After: `runs/stack-fit-v1/tavily-known-source-extract.jsonl`
- Exact accuracy: 33.3% -> 100.0% (+66.7%)
- Source-supported accuracy: 33.3% -> 66.7% (+33.3%)
- Scoreable runs: 3 -> 3
- Oracle skips: 0 -> 0
- Regressions: 0
- Improvements: 1

## Task Changes

| Task | Source-supported before | Source-supported after | Exact before | Exact after | Outcomes |
|---|---:|---:|---:|---:|---|
| `stackfit_known_next_package_manager` | 0.0% | 0.0% | 0.0% | 100.0% | wrong_value -> unsupported_citation |
| `stackfit_known_openai_python_client_class` | 100.0% | 100.0% | 100.0% | 100.0% | correct -> correct |
| `stackfit_known_playwright_release_tag` | 0.0% | 100.0% | 0.0% | 100.0% | wrong_value -> correct |
