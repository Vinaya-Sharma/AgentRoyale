# Task Spec

Agent Royale task packs are YAML or JSON files that describe exact, source-specific retrieval tests.

## Minimal Shape

```yaml
name: github-metadata
description: Exact retrieval tasks for GitHub repository metadata.
tasks:
  - id: github_nextjs_stars
    question: "Using GitHub, how many stars does the vercel/next.js repository currently have?"
    required_source: "github.com/vercel/next.js"
    answer_type: number
    tolerance: 0
    labels: [github, repository_metadata, stars]
    notes: "Ground truth comes from the GitHub REST API stargazers_count field."
    ground_truth:
      method: http_json
      url: "https://api.github.com/repos/vercel/next.js"
      field: "stargazers_count"
      source_url: "github.com/vercel/next.js"
```

## Fields

`id`: stable unique task identifier.

`question`: natural user-facing question. It should name the required source.

`required_source`: source the tested stack should use or cite.

`answer_type`: one of `string`, `number`, `currency`, `percentage`, `date`, or `enum`.

`tolerance`: exact by default. Numeric and currency tasks can use absolute values or percentages.

`labels`: searchable task metadata.

`notes`: oracle details and known failure modes.

`stability`: optional source stability label. Use `stable`, `semi_stable`, or `volatile`.

`ci_safe`: optional boolean. Set to `false` for volatile live-web tasks that should produce reports but should not fail CI by default.

`ground_truth`: how Agent Royale fetches or verifies the correct value.

## Ground Truth Methods

### static

Use for smoke tests or manual snapshots.

```yaml
ground_truth:
  method: static
  value: "$19.00"
  source_url: "example.com/pricing"
```

### http_json

Fetch JSON and read a dotted field path.

```yaml
ground_truth:
  method: http_json
  url: "https://registry.npmjs.org/react/latest"
  field: "version"
  source_url: "npmjs.com/package/react"
```

### http_regex

Fetch text or HTML and capture a value.

```yaml
ground_truth:
  method: http_regex
  url: "https://example.com/pricing"
  regex: "Pro[\\s\\S]{0,800}?\\$\\s*([0-9]+(?:\\.[0-9]{2})?)"
  require_near_text:
    - "Pro"
    - "monthly"
  reject_near_text:
    - "Enterprise"
  source_url: "example.com/pricing"
```

Regex tasks should be treated as maintained source-specific parsers. `require_near_text` and `reject_near_text` help prevent broad regexes from accepting nearby but wrong values. If multiple plausible values remain, Agent Royale marks the oracle ambiguous and skips scoring that task.

### bright_data

Use the existing Agent Royale Bright Data client as the independent oracle. Requires `BRIGHT_DATA_API_KEY`.

```yaml
ground_truth:
  method: bright_data
  tool: web_data_linkedin_company_profile
  url: "https://www.linkedin.com/company/openai/"
  field: "0.employees_in_linkedin"
```

Or with page extraction:

```yaml
ground_truth:
  method: bright_data
  tool: scrape_as_markdown
  url: "https://example.com/pricing"
  regex: "Pro[\\s\\S]{0,800}?\\$\\s*([0-9]+(?:\\.[0-9]{2})?)"
```

## What Makes A Good Task

- One required source.
- One exact target field.
- A deterministic oracle.
- Clear source stability and CI-safety.
- Context hints for noisy pages, such as plan names, billing intervals, variants, or units.
- A natural question a user might actually ask.
- Clear notes about source quirks.

## What Makes A Bad Task

- Broad multi-source questions.
- Subjective answers.
- Questions where multiple sources can reasonably disagree.
- Questions that require long-form synthesis.
- Oracles that are weaker than the model being tested.

## Validate

```bash
python -m agent_royale validate task-packs
```

## Audit Oracle Health

Use `audit` to fetch task-pack oracles before testing a target:

```bash
python -m agent_royale audit task-packs/devtools/dependency-research-v1.yaml
```

Every scored run now stores a ground-truth snapshot with source URL, fetch time, parser, evidence text, oracle status, and validation checks. Tasks with failed or ambiguous oracles are skipped rather than counted as target failures.

## CI-Safe Runs

Use `--ci` when a build should run only tasks marked `ci_safe: true`:

```bash
python -m agent_royale run task-packs \
  --target examples/echo_agent.py:answer \
  --ci \
  --fail-under-exact 0.9
```

Volatile packs, such as ecommerce prices or social counts, should generally set `ci_safe: false` and be run as scheduled or on-demand reports.
