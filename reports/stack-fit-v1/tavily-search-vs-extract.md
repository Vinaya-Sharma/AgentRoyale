# Agent Royale Comparison

- Before: `runs/stack-fit-v1/tavily-search-known-source.jsonl`
- After: `runs/stack-fit-v1/tavily-known-source-extract.jsonl`
- Exact accuracy: 20.0% -> 80.0% (+60.0%)
- Source-supported accuracy: 20.0% -> 60.0% (+40.0%)
- Scoreable runs: 5 -> 5
- Oracle skips: 0 -> 0
- Regressions: 0
- Improvements: 2

## Task Changes

| Task | Source-supported before | Source-supported after | Exact before | Exact after | Outcomes |
|---|---:|---:|---:|---:|---|
| `stackfit_known_next_package_manager` | 0.0% | 0.0% | 0.0% | 100.0% | wrong_value -> unsupported_citation |
| `stackfit_known_openai_python_client_class` | 100.0% | 100.0% | 100.0% | 100.0% | correct -> correct |
| `stackfit_known_playwright_release_tag` | 0.0% | 100.0% | 0.0% | 100.0% | no_answer -> correct |
| `stackfit_known_react_default_branch` | 0.0% | 100.0% | 0.0% | 100.0% | no_answer -> correct |
| `stackfit_known_rust_license_spdx` | 0.0% | 0.0% | 0.0% | 0.0% | no_answer -> wrong_value |
