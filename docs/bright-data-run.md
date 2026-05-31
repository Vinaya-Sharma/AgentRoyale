# Real Bright Data-Backed Run

This is a real Agent Royale V2 run using:

- OpenRouter as the model stack under test
- Bright Data as the independent ground-truth extractor
- `task-packs/bright-data/linkedin-company.yaml`

Command:

```bash
python -m agent_royale run task-packs/bright-data/linkedin-company.yaml \
  --target openrouter:openai/gpt-4o-mini \
  --report reports/bright-data-linkedin-openrouter.html
```

Result:

```text
Exact accuracy: 0.0% (0/2)
```

What happened:

| Task | Bright Data ground truth | Model claim | Result |
| --- | ---: | ---: | --- |
| OpenAI LinkedIn employees | 9,181 | 6,107 | wrong_value |
| Anthropic LinkedIn followers | 3,565,226 | 3,057,254 | wrong_value |

Why this is useful:

- The model returned plausible, source-looking answers.
- Agent Royale fetched the evaluator-side value separately.
- Bright Data provided structured LinkedIn company fields.
- The grader caught exact-value failures without an LLM judge.

This is the intended split:

```text
OpenRouter model stack -> answer
Bright Data extraction -> ground truth
Agent Royale -> deterministic report
```

Values change over time. Re-run the task pack for a current result.
