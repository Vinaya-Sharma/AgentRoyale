# Task Pack Ideas

Agent Royale task packs work best when they test one exact value from one required source. This page lists good public-facing contribution ideas for developers who want to add a domain they know well.

## Good Starter Domains

- Cloud pricing: instance hourly prices, storage prices, API prices, free-tier limits.
- Model pricing: input/output token prices from official provider pricing pages.
- Documentation freshness: latest stable versions, release dates, deprecation dates, supported runtime versions.
- Developer packages: package versions, weekly downloads, license fields, latest release tags.
- Finance data: quote fields, market-cap fields, ETF prices, crypto prices.
- App stores: current app version, rating, rating count, last-updated date.
- Ecommerce: current price, rating, review count, seller, shipping status.
- Local business data: hours, ratings, review counts, address fields.
- Travel: hotel rating, review score, room price, flight or route metadata.
- Social metrics: subscriber counts, follower counts, video counts, post counts.
- Company intelligence: employee counts, follower counts, funding fields, office locations.

## What A Good Task Looks Like

Good tasks are narrow, auditable, and easy to grade:

```text
Using npm, what is the latest published version of the react package?
Using GitHub, how many open issues does the microsoft/playwright repository currently have?
Using Apple's App Store listing for ChatGPT, what version is currently shown?
```

Each task should include:

- One required source.
- One target field.
- A deterministic ground-truth method.
- A clear answer type such as `number`, `currency`, `date`, or `string`.
- Notes explaining common mistakes, such as stale values, wrong regions, wrong variants, or nearby fields.

## Ground Truth Guidance

Use public APIs when they expose the exact field. For example, GitHub repository metadata, npm package metadata, Yahoo Finance quote fields, and Apple App Store lookup data are usually better as API-backed tasks.

Use Bright Data or maintained page extraction when the source is only available on the public web, the page is dynamic, or a normal HTTP request does not expose the value reliably. LinkedIn company fields and ecommerce product pages are good examples.

Avoid tasks where the correct answer depends on taste, synthesis, multiple sources, or hidden account-specific state. Agent Royale is strongest when the answer is either right or wrong.

## Create A Pack

```bash
python -m agent_royale init task-pack cloud-pricing
python -m agent_royale validate task-packs/cloud-pricing/example.yaml
```

Then replace the starter task with real source-specific tasks and open a pull request.
