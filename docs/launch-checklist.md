# V2 Launch Checklist

## Before Posting

- [ ] Repo is public.
- [ ] README screenshot loads.
- [ ] CI is green.
- [ ] `v0.1.0` release exists.
- [ ] Starter issues are open and labeled.
- [ ] Launch post links to the repo.
- [ ] Bright Data wording is accurate: used where web extraction is needed, not required for everything.
- [ ] No secrets are committed.

## Smoke Test

```bash
git clone https://github.com/Vinaya-Sharma/AgentRoyale.git
cd AgentRoyale
pip install -r requirements.txt
pip install -e .
python -m agent_royale validate task-packs
python -m agent_royale run task-packs/static-smoke.yaml \
  --target examples/echo_agent.py:answer \
  --report reports/smoke.html
```

## First Comment / Follow-Up

If people ask how to use it on their own stack:

```bash
python -m agent_royale run task-packs/github/example.yaml \
  --target http://localhost:3000/api/agent \
  --report reports/github.html
```

If people ask where Bright Data fits:

```text
Agent Royale uses public APIs for GitHub and npm task packs. Bright Data powers reliable web extraction for LinkedIn, ecommerce, app store, and dynamic pricing task packs.
```

## Best Contributor Ask

Want to help? The best first PR is a task pack for a source your agent depends on.
