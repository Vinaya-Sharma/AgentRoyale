# Agent Royale: An Open Source Grading Layer for Web Retrieval Agents

AI products are starting to depend on live web data, but the hard part is no longer just getting access to the web.

The tooling ecosystem is genuinely strong right now. OpenRouter makes it easy to try a huge range of models. Tavily and Jina AI are fast for search and retrieval. Firecrawl, Browserbase, and Bright Data help with structured extraction, scraping, and browser-based workflows.

That gives builders a lot of good options, but it also creates a harder question:

**Which stack should I actually trust for my product?**

For a demo, almost anything can look good. A model can sound confident. A citation can look convincing. A scraper can return a page. A browser workflow can work once.

But when your product depends on exact live-web answers, "it looked right" is not enough.

If your agent is answering questions about pricing pages, product data, docs, releases, or company metrics, you need to know which model, tool, or agent actually returns the right value from the right source.

That is why I built Agent Royale.

**Image:** `docs/assets/launch/v3-report-decision-dashboard.png`

**Caption:** Agent Royale turns live-web agent runs into a decision report: exact values, source-supported accuracy, oracle skips, latency, cost, and what to fix next.

## The Problem

When people talk about AI agents accessing the live web, the conversation usually focuses on access.

Can the model search?

Can it browse?

Can it scrape?

Can it use a browser?

Can it call a retrieval API?

Those questions matter, but they are only the first layer.

The harder question is accuracy.

If an agent says a pricing page lists $99/month, is that actually the current price?

If it cites a docs page, does the cited page really support the answer?

If two models return different release versions, which one is right?

If a cheaper stack is 80% as accurate, is that acceptable for your use case?

If a stronger stack costs more but prevents bad product decisions, is it worth it?

Most teams end up answering these questions manually. They run a few models, look at a few outputs, eyeball the citations, and pick the stack that feels good enough.

That is slow. It is inconsistent. And it becomes painful the moment you change prompts, swap models, add retries, or route between tools.

I wanted a way to make those decisions with actual evidence.

## What Agent Royale Does

Agent Royale is an open source evaluation layer for web retrieval agents.

You define task packs for the questions your product actually cares about. For example:

- pricing pages
- product details
- GitHub releases
- npm package versions
- docs freshness
- company profile metrics
- ecommerce product data

**Image:** `docs/assets/launch/tasks.png`

**Caption:** Task packs define the questions, required sources, saved ground truth, model answers, citations, and failure patterns.

Then Agent Royale runs those tasks across the models, tools, or agents you want to compare.

The important part is that it does not just ask, "Did the agent answer?"

It checks whether the answer is actually correct.

Agent Royale fetches independent ground truth, compares exact values deterministically, checks whether the source is right, checks whether citations support the claim, and generates reports showing:

- correct vs. wrong values
- wrong sources
- unsupported citations
- oracle skips
- latency
- cost
- regressions after changes
- what to fix next

The goal is to help builders stop guessing which web retrieval stack works best for their use case.

## The Three Layers Of Web Retrieval

As I worked on this, I started thinking about web retrieval stacks in three layers.

### 1. Out-Of-The-Box Models

This is the fastest way to start.

You use models through something like OpenRouter, pick a few candidates, and see how they perform with search or native browsing behavior.

This is great for quick experimentation because OpenRouter makes access easy. You can try a lot of models without rebuilding your app around each one.

But access alone does not tell you which model is actually right for your workflow.

Agent Royale helps here by running the same task bank across multiple OpenRouter models and giving you a report on which one returned the exact right answers from the right sources.

### 2. Specialized Retrieval Tools

Sometimes a model with search is not enough.

You may need a faster search API, a scraper, a structured extraction tool, or a browser workflow.

That is where tools like Tavily, Jina AI, Firecrawl, Browserbase, and Bright Data become useful. Each one is strong in different parts of the live-web problem.

But again, the question is not just "Can this tool access the page?"

The question is: "Does this stack produce the correct answer for my task?"

Agent Royale works directly with these tools so developers can compare retrieval approaches using the same grading layer.

### 3. Custom Agents

Eventually, some teams need their own pipeline.

They may combine models, search, scraping, browser automation, retries, routing, source policies, and custom prompts.

That flexibility is powerful, but it also makes evaluation harder. A small prompt change or fallback change can improve one task and quietly break another.

Agent Royale gives custom agents a repeatable benchmark. You can run your task pack before and after changes and see exactly what improved, what regressed, and what still needs work.

**Image:** `docs/assets/experiments/stack-fit-v1/openrouter-dev-web-retrieval-report.png`

**Caption:** The same grading layer can evaluate out-of-the-box models, specialized retrieval tools, and custom agent stacks.

## Why Ground Truth Is The Hard Part

The hardest part of this project was not generating a report.

The hardest part was making sure the grader itself was trustworthy.

If the grader has bad ground truth, then the whole evaluation becomes useless.

So V3 of Agent Royale focused heavily on strengthening the ground-truth extraction pipeline.

For every task, Agent Royale tries to verify the independent oracle before scoring any agent output. If the oracle cannot safely verify the ground truth, that task is skipped instead of being scored.

That means a task can be:

- verified and scoreable
- ambiguous and skipped
- missing required evidence and skipped
- source-unreachable and quarantined
- selector-broken and flagged for salvage

This matters because I do not want the tool to silently grade against weak evidence.

If a developer writes a hard task, the goal is not to hide it or replace it with an easier one. The goal is to make the extraction path more robust, and if the oracle still cannot verify the value, make that transparent.

That is why the reports now show oracle skips separately from agent failures.

A bad oracle should not count against the agent. It should tell the developer that the task needs a better ground-truth path.

## Built With Bright Data Support

A big part of the project was building with Bright Data support for live-web ground truth.

Bright Data was useful because many of the tasks I cared about were not clean API calls. They were messy public web pages: ecommerce product pages, company pages, docs pages, and dynamic sources where ordinary scraping can fail.

For V3, I tested Bright Data-backed task packs across three main domains:

- developer dependency and docs research
- ecommerce product and pricing accuracy
- company intelligence and public profile metrics

This helped me stress-test different ground-truth paths: simple page extraction, structured tools, fallback routing, and cases where a task should be quarantined instead of scored.

One example I spent time on was a Samsung product task. The first version tried to extract storage prices from markdown, but the page returned storage labels without nearby prices. Instead of loosening the regex and pretending it was fine, I moved the task to the canonical SKU page and verified the price from Samsung's structured Product JSON-LD in the HTML fallback.

That is the kind of behavior I want Agent Royale to encourage.

Do not mask hard tasks.

Do not grade against weak evidence.

Fix the oracle or quarantine the task.

**Image:** `docs/assets/experiments/stack-fit-v1/bright-data-dynamic-ecommerce-report.png`

**Caption:** Bright Data-backed ecommerce tasks helped stress-test ground-truth extraction, fallback routing, and quarantine behavior.

## What The Reports Show

The HTML reports are designed to be decision dashboards.

**Image:** `docs/assets/report-preview.png`

**Caption:** Reports are designed for stack decisions: what passed, what failed, what was skipped, and what to fix next.

Instead of dumping raw eval output, they show the things a builder actually needs to know:

- How many tasks were scoreable?
- How many answers matched the exact oracle value?
- Did the agent use the right source?
- Did the citation actually support the claim?
- Which failures were wrong values vs. wrong sources?
- Which tasks were skipped because the oracle was not safe?
- What was the latency?
- What was the reported cost?
- What should be fixed next?

This is important because the cost of picking the wrong stack is not just technical.

If your agent returns the wrong price, stale docs, unsupported citations, or the wrong company metric, that can create bad user experiences and bad product decisions.

Agent Royale helps turn stack selection into something more measurable.

Instead of asking, "Which model feels best?" you can ask:

**Which stack is accurate enough for this workflow, at the latency and cost I can accept?**

## Who This Is For

Agent Royale is for builders working on products where live-web accuracy matters.

That could mean:

- AI search products
- research agents
- ecommerce agents
- developer tools
- sales or company intelligence workflows
- support copilots
- internal automation
- model/tool routing experiments

It is especially useful if you are already building with tools like OpenRouter, Tavily, Jina AI, Firecrawl, Browserbase, or Bright Data and want a clearer way to compare results.

Agent Royale is not trying to replace those tools.

It works with them.

The point is to give developers a grading layer on top of the retrieval stack so they can understand which option is actually best for their own task bank.

## What I Learned

The biggest thing I learned is that web retrieval quality is not one-dimensional.

A stack can be fast but wrong.

A model can cite the right domain but the wrong page.

A scraper can retrieve the page but miss the exact field.

A browser workflow can work once and fail later.

A task can look simple to a human and still be hard to verify automatically.

That is why evals need to track more than pass/fail.

They need to show the source, the evidence, the oracle status, the failure mode, and the cost of getting the answer.

The best stack depends on the task.

That is the practical superpower I want Agent Royale to give developers: a way to decide which model, tool, or agent to use based on real performance on the work they actually care about.

## Open Source

Agent Royale is now open source.

You can define your own task packs, plug in your own models or agents, run comparisons, and generate reports.

I would especially love:

- weird web retrieval failures
- task pack ideas
- examples from different domains
- feedback on the reports
- integrations with more retrieval stacks

The goal is to make it easier for builders to evaluate live-web agents with the same seriousness we bring to product code.

Because if agents are going to act on live information, we need to know when they are actually right.

Repo: https://github.com/Vinaya-Sharma/AgentRoyale
