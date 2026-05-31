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
  source_url: "example.com/pricing"
```

Regex tasks should be treated as maintained source-specific parsers. If the page changes, update or quarantine the task.

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
