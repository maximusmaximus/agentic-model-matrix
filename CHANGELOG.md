# Changelog — Agentic Model Matrix

Automated ledger of every matrix update, routing diff, and live source probe recorded by CI.

- **Last Updated (UTC):** `2026-11-19T16:09:14Z`
- **Recorded Runs:** `4` (retained up to `52`)

## 2026-11-19T16:09:14Z — `2026-W47` (telemetry refresh)

- **Trigger:** `workflow_dispatch` | **Hash:** `b30ad13b11b4` | **Sources:** `6/6 healthy, avg 140 ms`
- Upstream update detected on `livebench-coding` (Last-Modified: Tue, 17 Nov 2026 21:07:21 GMT)

## 2026-11-19T16:05:28Z — `2026-W47` (telemetry refresh)

- **Trigger:** `workflow_dispatch` | **Hash:** `b30ad13b11b4` | **Sources:** `6/6 healthy, avg 178 ms`
- Upstream update detected on `livebench-coding` (Last-Modified: Tue, 17 Nov 2026 21:07:20 GMT)

## 2026-11-19T15:56:02Z — `2026-W47` (routing change)

- **Trigger:** `review-upgrade` | **Hash:** `b30ad13b11b4` | **Sources:** `6/6 healthy, avg 114 ms`
- Schema version updated: v1.0.0 -> v1.1.0
- Stage `triage` primary model: `gemini-3.8-flash-high` -> `gemini-4-hydrogen-high`
- Stage `research` primary model: `gemini-4-carbon-high` -> `gemini-4-neon-high`
- Stage `consensus_specs` primary model: `gemini-4-hydrogen-high` -> `gemini-4-neon-high`
- Stage `architecture` fallback chain updated (3 models)
- Stage `app_build` primary model: `gemini-4-hydrogen-xhigh` -> `gemini-4-neon-xhigh`
- Stage `app_build` best practices refined (5 guidelines)
- Stage `qa_deploy` primary model: `gemini-4-carbon-high` -> `gemini-4-neon-high`
- Source `antigravity-docs` status: `configured` -> `http_200`
- Added evaluation source `antigravity-changelog` (https://antigravity.google/changelog)
- Added evaluation source `arena-coding` (https://arena.ai/)
- Source `swe-bench-verified` status: `configured` -> `http_200`
- Source `livebench-coding` status: `configured` -> `http_200`
- Source `cloudflare-workers-docs` status: `configured` -> `http_200`
- Removed evaluation source `lmarena-coding`

## 2026-11-17T20:38:51Z — `2026-W47` (routing change)

- **Trigger:** `initial-baseline` | **Hash:** `c8ff92c089f3` | **Sources:** `0/5 healthy`
- Initial weekly best-practices & SDLC model routing matrix baseline.
