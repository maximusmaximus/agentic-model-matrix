# Agentic Model Matrix

Weekly-updated **Coding Best Practices** and **Model-to-SDLC-Stage Routing Matrix** designed to be referenced as a standalone module by autonomous conversation-to-production systems.

## What This Module Publishes

- [`BEST_PRACTICES.md`](BEST_PRACTICES.md) — Human-readable weekly engineering playbook and stage-by-stage model selection rationale.
- [`routing.json`](routing.json) — Machine-readable model routing matrix across 6 SDLC stages (`triage`, `research`, `consensus_specs`, `architecture`, `app_build`, `qa_deploy`).
- [`schema/routing.schema.json`](schema/routing.schema.json) — Contract validating stage schemas, governance flags, and hard policies.

## Core Policies

1. **Stage 5 (`app_build`) Pinning:** Application code generation is strictly locked to **Gemini models running on Antigravity (`agy`)** with an ordered quota-fallback chain.
2. **PR-Gated Activation:** The weekly workflow template ([`templates/github-workflows/weekly-matrix.yml`](templates/github-workflows/weekly-matrix.yml)) opens a Pull Request rather than pushing directly to `main`. Downstream consumers ingest updates once the PR is merged.
3. **Zero-Leak Public Hygiene:** Every commit and PR runs [`scripts/security_scan.py`](scripts/security_scan.py) to block credentials, private network identifiers, local paths, and personal emails.

## Enabling GitHub Actions Workflows

Workflow definitions live in [`templates/github-workflows/`](templates/github-workflows/) so repositories using a standard `repo`-scoped GitHub token can clone and push cleanly without `workflow` OAuth scope. To activate CI and the weekly Monday cron on GitHub:

```bash
mkdir -p .github/workflows
cp templates/github-workflows/*.yml .github/workflows/
# Push using a PAT or OAuth session that includes the `workflow` scope (e.g., `gh auth refresh -s workflow`)
```

## Referencing From Another Repo

Add as a Git submodule:

```bash
git submodule add https://github.com/maximusmaximus/agentic-model-matrix.git modules/model-matrix
```

Or fetch the pinned `main` raw artifacts:

- `https://raw.githubusercontent.com/maximusmaximus/agentic-model-matrix/main/routing.json`
- `https://raw.githubusercontent.com/maximusmaximus/agentic-model-matrix/main/BEST_PRACTICES.md`

## Local Usage & Verification

```bash
pip install -r requirements.txt
python scripts/generate_weekly_matrix.py --root .
python scripts/generate_weekly_matrix.py --root . --check
python scripts/security_scan.py --root .
pytest -v
```
