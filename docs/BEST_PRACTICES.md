# Weekly Coding Best Practices & SDLC Model Routing Matrix

- **Week:** `2026-W47`
- **Schema Version:** `1.1.0`
- **Generated At (UTC):** `2026-11-20T14:29:53Z`
- **Content Hash:** `b30ad13b11b4`
- **Evaluation Sources:** `6/6` healthy (avg probe latency `126 ms`)
- **Governance:** PR-merge gated (`requires_pr_merge: true`) — CI validates security, schema, tests, and site parity before merge.
- **App Build Policy:** **Stage 5 (`app_build`) is strictly pinned to Gemini models running on Antigravity (`agy`)** with an ordered quota fallback chain.

---

## 1. Weekly Model-to-Stage Routing Summary

| Stage | Phase | Primary Model | Effort | `agy` Mode | Ordered Fallback Chain |
| --- | --- | --- | --- | --- | --- |
| 1. `triage` | Transcript Triage & Signal Classification | `gemini-4-hydrogen-high` | `medium` | `plan` | `gemini-4-hydrogen-high` → `gemini-4-neon-medium` → `gemini-3.8-flash-high` |
| 2. `research` | Deep Research & Technical Tradeoff Synthesis | `gemini-4-neon-high` | `high` | `plan` | `gemini-4-neon-high` → `gemini-4-carbon-high` → `claude-sonnet-5-5-high` |
| 3. `consensus_specs` | Consensus Promotion & Requirements Specification | `gemini-4-neon-high` | `high` | `plan` | `gemini-4-neon-high` → `claude-sonnet-5-5-high` → `gemini-4-carbon-high` |
| 4. `architecture` | System Architecture & Edge/Storage Blueprint | `claude-opus-5-5-high` | `high` | `plan` | `claude-opus-5-5-high` → `gemini-4-carbon-high` → `gemini-4-neon-xhigh` |
| 5. `app_build` | Full-Stack Web App Implementation (Gemini on Antigravity) | `gemini-4-neon-xhigh` | `xhigh` | `accept-edits` | `gemini-4-neon-xhigh` → `gemini-4-carbon-high` → `gemini-4-neon-high` → `gemini-4-hydrogen-high` → `gemini-4-argon-high` |
| 6. `qa_deploy` | Verification, Security Scan & Cloudflare Deployment | `gemini-4-neon-high` | `high` | `accept-edits` | `gemini-4-neon-high` → `gemini-4-hydrogen-high` → `claude-sonnet-5-5-high` |

---

## 2. Stage Best Practices & Selection Rationale

### 1. Transcript Triage & Signal Classification (`triage`)

- **Primary Provider / Model:** `antigravity` / `gemini-4-hydrogen-high` (`effort=medium`, `mode=plan`)
- **Fallback Chain:** `gemini-4-hydrogen-high`, `gemini-4-neon-medium`, `gemini-3.8-flash-high`

**Selection Criteria:**
- High-speed, low-cost long-context speaker diarization fidelity
- Low-latency structured JSON classification
- Strict verbatim quote anchoring without hallucinated requirements

**Coding & Workflow Best Practices:**
- Always anchor extracted requirements, research items, and non-goals to verbatim speaker quotes and utterance timestamps.
- Treat auto-generated meeting summaries as unverified hints; extract only from raw transcript turns.
- Separate explicit speaker consensus from contested points and open research items before generating specs.

### 2. Deep Research & Technical Tradeoff Synthesis (`research`)

- **Primary Provider / Model:** `antigravity` / `gemini-4-neon-high` (`effort=high`, `mode=plan`)
- **Fallback Chain:** `gemini-4-neon-high`, `gemini-4-carbon-high`, `claude-sonnet-5-5-high`

**Selection Criteria:**
- Grounded web/documentation synthesis with primary source citations
- Cost-efficient frontier reasoning (~32% lower cost/task than Carbon at High)
- Bounded exploration under strict time and token budgets

**Coding & Workflow Best Practices:**
- Timebox each open-to-research question and cap search fan-out to avoid research loops.
- Require primary documentation citations (official API docs, RFCs, or package registries) for every recommendation.
- Pre-fill low-risk technical choices for review, but pause at Gate 1 whenever pricing, auth, data ownership, or scope is affected.

### 3. Consensus Promotion & Requirements Specification (`consensus_specs`)

- **Primary Provider / Model:** `antigravity` / `gemini-4-neon-high` (`effort=high`, `mode=plan`)
- **Fallback Chain:** `gemini-4-neon-high`, `claude-sonnet-5-5-high`, `gemini-4-carbon-high`

**Selection Criteria:**
- Deterministic traceability from quote_id and research_id to requirement_id
- Strict negative-constraint enforcement for out-of-scope items
- High-precision specification authoring across 512K context windows

**Coding & Workflow Best Practices:**
- Promote only multi-speaker or decision-maker-confirmed items into locked requirements (`REQ-*`).
- Emit explicit negative constraints (`Out of scope`) and regression invariants (`Must not regress`) alongside acceptance criteria.
- Require Gate 1 human approval before transitioning locked requirements into application code generation.

### 4. System Architecture & Edge/Storage Blueprint (`architecture`)

- **Primary Provider / Model:** `antigravity` / `claude-opus-5-5-high` (`effort=high`, `mode=plan`)
- **Fallback Chain:** `claude-opus-5-5-high`, `gemini-4-carbon-high`, `gemini-4-neon-xhigh`

**Selection Criteria:**
- Long-horizon architectural clarity across swappable provider adapters
- Clean schema design for Cloudflare Workers, R2, and relational state
- Minimal complexity and zero speculative abstractions

**Coding & Workflow Best Practices:**
- Isolate external integrations (booking, calendar, call, transcript, repo, deploy) behind typed adapter interfaces.
- Model Cloudflare R2 keys, webhook idempotency keys, and correlation keys explicitly before writing handlers.
- Default to a single well-tested vertical slice when spinning up greenfield apps; use delta branches for follow-up meetings.

### 5. Full-Stack Web App Implementation (Gemini on Antigravity) (`app_build`)

- **Primary Provider / Model:** `antigravity` / `gemini-4-neon-xhigh` (`effort=xhigh`, `mode=accept-edits`)
- **Hard Constraint:** Must use **Gemini models on Antigravity**. On quota/capacity exhaustion, step down along `fallback_chain` while keeping the same Antigravity `--conversation` ID.
- **Fallback Chain:** `gemini-4-neon-xhigh`, `gemini-4-carbon-high`, `gemini-4-neon-high`, `gemini-4-hydrogen-high`, `gemini-4-argon-high`

**Selection Criteria:**
- Pinned strictly to Gemini models on Antigravity per platform policy
- Frontier multi-file coding accuracy with Gemini 4 Neon (xhigh) and Carbon fallback
- Ordered quota-aware fallback chain across Gemini 4 tiers with Orchestrator support

**Coding & Workflow Best Practices:**
- Scaffold against golden templates (Next.js App Router + TypeScript + Tailwind + Cloudflare Workers/R2, or FastAPI + React/Vite when Python is constrained).
- Pair Gemini 4 Neon as planner with parallel Gemini 4 Hydrogen subagents via Antigravity Orchestrator for multi-file feature slices.
- Keep each feature vertical end-to-end: schema, API route, UI state, error state, and automated test.
- If a Gemini tier hits a 5-hour or weekly quota limit mid-run, step down cleanly along `fallback_chain` while preserving the Antigravity conversation ID.
- Never embed placeholder stubs for in-scope features or commit credentials, local paths, or private network names.

### 6. Verification, Security Scan & Cloudflare Deployment (`qa_deploy`)

- **Primary Provider / Model:** `antigravity` / `gemini-4-neon-high` (`effort=high`, `mode=accept-edits`)
- **Fallback Chain:** `gemini-4-neon-high`, `gemini-4-hydrogen-high`, `claude-sonnet-5-5-high`

**Selection Criteria:**
- Fast automated build, lint, typecheck, and headless smoke-test execution
- Zero-leak scanning before git push and Cloudflare Worker/R2 deploy

**Coding & Workflow Best Practices:**
- Run typecheck, build, unit tests, HTTP health probes, and zero-leak secret/PII scans before opening Gate 2.
- Verify R2 bucket bindings, Worker routes, and environment variables in preview environments prior to production promotion.
- Open changes on `feat/<slice>` or `delta/<meeting-id>` branches; never push directly to `main`.

---

## 3. Cross-Cutting Engineering Standards (All Built Web Applications)

1. **Golden Stacks & Verification:** Default greenfield web apps to **Next.js (App Router + TypeScript + Tailwind + SQLite/D1/Postgres)** or **FastAPI + React/Vite** when Python constraints apply, bundled with typecheck, build, and HTTP smoke-test checks.
2. **Cloudflare Runtime & Storage:** Target **Cloudflare Workers / Pages** for compute/preview delivery and **Cloudflare R2** for transcripts, build bundles, and exported assets.
3. **Swappable Adapter Boundaries:** Keep scheduling, calendar, meeting, transcript, research, repository, and deployment providers behind typed interfaces so any vendor can be swapped via configuration.
4. **Quote-Backed Traceability:** Every shipped requirement (`REQ-*`) must trace to a verbatim speaker quote or an approved research brief (`RES-*`).
5. **Zero-Leak Public Hygiene:** Run `scripts/security_scan.py` in pre-commit and CI; never commit keys, private hostnames, local filesystem paths, personal emails, or internal IP addresses.

## 4. Reference Evaluation Sources

| Source ID | Kind | URL | Status | Latency | Last-Modified |
| --- | --- | --- | --- | --- | --- |
| `antigravity-docs` | `platform_docs` | https://antigravity.google/docs | `http_200` | `181 ms` | `Fri, 20 Nov 2026 04:04:49 GMT` |
| `antigravity-changelog` | `platform_changelog` | https://antigravity.google/changelog | `http_200` | `168 ms` | `Fri, 20 Nov 2026 04:04:49 GMT` |
| `arena-coding` | `public_leaderboard` | https://arena.ai/ | `http_200` | `142 ms` | — |
| `swe-bench-verified` | `public_benchmark` | https://www.swebench.com/ | `http_200` | `111 ms` | `Tue, 01 Sep 2026 02:54:51 GMT` |
| `livebench-coding` | `public_benchmark` | https://livebench.ai/ | `http_200` | `105 ms` | `Thu, 19 Nov 2026 18:01:32 GMT` |
| `cloudflare-workers-docs` | `runtime_docs` | https://developers.cloudflare.com/workers/ | `http_200` | `47 ms` | — |
