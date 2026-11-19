#!/usr/bin/env python3
"""
generate_weekly_matrix.py — CI-driven Best Practices, Model Routing Matrix,
Telemetry Stats, Changelog, README Live Sync, and GitHub Pages generator.

Reads sources.yaml, optionally probes public benchmark/docs URLs, validates all
invariants (including the Stage 5 Gemini-on-Antigravity hard lock and JSON Schema),
and emits:
  - routing.json
  - stats.json
  - history.json
  - BEST_PRACTICES.md
  - CHANGELOG.md
  - llms.txt
  - README.md (live status block between HTML markers)
  - docs/ (GitHub Pages interactive dashboard + static API mirrors)

Supports:
  --allow-live-fetch   Probe public evaluation URLs for HTTP status, latency, and Last-Modified
  --if-changed         Skip writing files when week_id, routing hash, and source headers are unchanged
  --force              Always rewrite artifacts (overrides --if-changed)
  --trigger <name>     Record trigger source in history/stats (e.g., ci-schedule, workflow_dispatch, manual)
  --check              Verify existing artifacts match schema, policy, and site parity without rewriting
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_site  # noqa: E402

REQUIRED_STAGES = [
    "triage",
    "research",
    "consensus_specs",
    "architecture",
    "app_build",
    "qa_deploy",
]
VALID_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
VALID_MODES = {"plan", "accept-edits", "auto"}
MAX_HISTORY_RUNS = 52

README_START_MARKER = "<!-- MATRIX_LIVE_STATS:START -->"
README_END_MARKER = "<!-- MATRIX_LIVE_STATS:END -->"


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def utc_now_iso(now: Optional[datetime.datetime] = None) -> str:
    dt = now or utc_now()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def current_week_id(now: Optional[datetime.datetime] = None) -> str:
    dt = now or utc_now()
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def load_sources(sources_path: Path) -> Dict[str, Any]:
    with open(sources_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_content_hash(matrix_core: Dict[str, Any]) -> str:
    """Deterministic SHA-256 hash of routing policy, stages, and source definitions."""
    canonical = {
        "schema_version": matrix_core.get("schema_version"),
        "governance": matrix_core.get("governance"),
        "app_build_policy": matrix_core.get("app_build_policy"),
        "source_urls": [
            {"id": s.get("id"), "kind": s.get("kind"), "url": s.get("url")}
            for s in matrix_core.get("evaluation_sources", [])
        ],
        "stages": matrix_core.get("stages", []),
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def probe_public_sources(sources: List[Dict[str, Any]], timeout_sec: int = 8) -> List[Dict[str, Any]]:
    """
    Lightweight reachability, latency, and Last-Modified probe against public docs/benchmarks.
    Never sends local environment data or credentials and never attempts to bypass HTTP 403/WAF.
    """
    checked_at = utc_now_iso()
    results: List[Dict[str, Any]] = []

    for src in sources:
        url = str(src.get("url", ""))
        entry: Dict[str, Any] = {
            "id": src.get("id", "unknown"),
            "kind": src.get("kind", "unknown"),
            "url": url,
            "notes": src.get("notes", ""),
            "status": "skipped",
            "http_status": None,
            "healthy": None,
            "latency_ms": None,
            "last_modified": None,
            "checked_at": checked_at,
        }
        if not url.startswith("https://"):
            results.append(entry)
            continue

        headers = {"User-Agent": "agentic-model-matrix-ci/1.1 (+https://github.com/maximusmaximus/agentic-model-matrix)"}
        t0 = time.monotonic()

        def _do_request(method: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
            req = urllib.request.Request(url, method=method, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    if method == "GET":
                        resp.read(1)
                    return int(resp.status), resp.headers.get("Last-Modified"), None
            except urllib.error.HTTPError as exc:
                return int(exc.code), exc.headers.get("Last-Modified") if exc.headers else None, None
            except Exception as exc:
                return None, None, type(exc).__name__

        code, last_mod, err_name = _do_request("HEAD")
        if code == 405:
            code, last_mod, err_name = _do_request("GET")

        elapsed_ms = round((time.monotonic() - t0) * 1000.0, 1)
        entry["latency_ms"] = elapsed_ms
        entry["last_modified"] = last_mod

        if code is not None:
            entry["http_status"] = code
            entry["status"] = f"http_{code}"
            entry["healthy"] = 200 <= code < 400
        else:
            entry["status"] = f"unreachable ({err_name})"
            entry["healthy"] = False

        results.append(entry)
    return results


def validate_matrix(matrix: Dict[str, Any], schema_path: Optional[Path] = None) -> Tuple[bool, List[str]]:
    errors: List[str] = []

    if not re.match(r"^\d+\.\d+\.\d+$", str(matrix.get("schema_version", ""))):
        errors.append("schema_version must match semver X.Y.Z")
    if not re.match(r"^\d{4}-W\d{2}$", str(matrix.get("week_id", ""))):
        errors.append("week_id must match YYYY-Www")

    gov = matrix.get("governance", {})
    if gov.get("requires_pr_merge") is not True:
        errors.append("governance.requires_pr_merge must be true")
    if gov.get("cadence") != "weekly":
        errors.append("governance.cadence must be 'weekly'")

    policy = matrix.get("app_build_policy", {})
    if policy.get("stage_id") != "app_build":
        errors.append("app_build_policy.stage_id must be 'app_build'")
    if policy.get("provider") != "antigravity":
        errors.append("app_build_policy.provider must be 'antigravity'")
    if policy.get("model_family") != "gemini":
        errors.append("app_build_policy.model_family must be 'gemini'")

    stages = matrix.get("stages", [])
    if len(stages) != len(REQUIRED_STAGES):
        errors.append(f"Expected {len(REQUIRED_STAGES)} stages, got {len(stages)}")
        return False, errors

    seen_ids = [s.get("id") for s in stages]
    if seen_ids != REQUIRED_STAGES:
        errors.append(f"Stage order/IDs must equal {REQUIRED_STAGES}, got {seen_ids}")

    for idx, stage in enumerate(stages, start=1):
        sid = stage.get("id", "<unknown>")
        if stage.get("order") != idx:
            errors.append(f"Stage {sid}: expected order {idx}, got {stage.get('order')}")
        if stage.get("effort") not in VALID_EFFORTS:
            errors.append(f"Stage {sid}: invalid effort {stage.get('effort')}")
        if stage.get("cli_mode") not in VALID_MODES:
            errors.append(f"Stage {sid}: invalid cli_mode {stage.get('cli_mode')}")
        chain = stage.get("fallback_chain", [])
        if not isinstance(chain, list) or len(chain) < 2:
            errors.append(f"Stage {sid}: fallback_chain must have at least 2 models")
        elif chain[0] != stage.get("primary_model"):
            errors.append(f"Stage {sid}: fallback_chain[0] must equal primary_model")
        if not stage.get("best_practices"):
            errors.append(f"Stage {sid}: best_practices cannot be empty")

        if sid == "app_build":
            if stage.get("primary_provider") != "antigravity":
                errors.append("Stage app_build: primary_provider must be 'antigravity'")
            if stage.get("model_family") != "gemini":
                errors.append("Stage app_build: model_family must be 'gemini'")
            for model_id in [stage.get("primary_model", "")] + list(chain):
                if "gemini" not in str(model_id).lower():
                    errors.append(
                        f"Stage app_build: non-Gemini model '{model_id}' violates Gemini-on-Antigravity policy"
                    )

    if schema_path and schema_path.exists():
        try:
            import jsonschema  # type: ignore

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(schema)
            for err in sorted(validator.iter_errors(matrix), key=lambda e: list(e.path)):
                loc = ".".join(str(p) for p in err.path) or "<root>"
                errors.append(f"JSON Schema ({loc}): {err.message}")
        except ImportError:
            pass

    return len(errors) == 0, errors


def _model_family(model_id: str) -> str:
    lower = model_id.lower()
    if "gemini" in lower:
        return "gemini"
    if "claude" in lower:
        return "claude"
    if "gpt" in lower or lower.startswith("o1") or lower.startswith("o3") or lower.startswith("o4"):
        return "openai"
    return "other"


def compute_matrix_diff(
    previous: Optional[Dict[str, Any]],
    current: Dict[str, Any],
) -> Tuple[List[str], bool, bool]:
    """
    Compare previous routing.json against current candidate matrix.
    Returns (human_changes, routing_changed, meaningful_update).
    """
    if not previous:
        return [f"Initialized routing matrix baseline ({current['week_id']}, schema v{current['schema_version']})."], True, True

    changes: List[str] = []
    routing_changed = False
    meaningful = False

    if previous.get("schema_version") != current.get("schema_version"):
        changes.append(
            f"Schema version updated: v{previous.get('schema_version')} -> v{current.get('schema_version')}"
        )
        routing_changed = True
        meaningful = True

    if previous.get("week_id") != current.get("week_id"):
        changes.append(f"ISO week rolled over: {previous.get('week_id')} -> {current.get('week_id')}")
        meaningful = True

    prev_stages = {s.get("id"): s for s in previous.get("stages", [])}
    for st in current.get("stages", []):
        sid = st["id"]
        old = prev_stages.get(sid)
        if not old:
            changes.append(f"Added stage `{sid}` with primary `{st['primary_model']}`")
            routing_changed = True
            meaningful = True
            continue
        if old.get("primary_model") != st.get("primary_model"):
            changes.append(
                f"Stage `{sid}` primary model: `{old.get('primary_model')}` -> `{st.get('primary_model')}`"
            )
            routing_changed = True
            meaningful = True
        elif old.get("fallback_chain") != st.get("fallback_chain"):
            changes.append(
                f"Stage `{sid}` fallback chain updated ({len(st.get('fallback_chain', []))} models)"
            )
            routing_changed = True
            meaningful = True
        if old.get("effort") != st.get("effort") or old.get("cli_mode") != st.get("cli_mode"):
            changes.append(
                f"Stage `{sid}` execution profile: effort={st.get('effort')}, mode={st.get('cli_mode')}"
            )
            routing_changed = True
            meaningful = True
        if old.get("best_practices") != st.get("best_practices"):
            changes.append(
                f"Stage `{sid}` best practices refined ({len(st.get('best_practices', []))} guidelines)"
            )
            routing_changed = True
            meaningful = True

    prev_sources = {s.get("id"): s for s in previous.get("evaluation_sources", [])}
    curr_sources = {s.get("id"): s for s in current.get("evaluation_sources", [])}

    for sid, src in curr_sources.items():
        old_src = prev_sources.get(sid)
        if not old_src:
            changes.append(f"Added evaluation source `{sid}` ({src.get('url')})")
            routing_changed = True
            meaningful = True
            continue
        if old_src.get("url") != src.get("url"):
            changes.append(f"Source `{sid}` URL updated: {old_src.get('url')} -> {src.get('url')}")
            routing_changed = True
            meaningful = True
        if old_src.get("status") != src.get("status") and src.get("status") != "configured":
            changes.append(f"Source `{sid}` status: `{old_src.get('status')}` -> `{src.get('status')}`")
            meaningful = True
        old_lm = old_src.get("last_modified")
        new_lm = src.get("last_modified")
        if new_lm and new_lm != old_lm:
            if old_lm:
                changes.append(f"Upstream update detected on `{sid}` (Last-Modified: {new_lm})")
                meaningful = True
            else:
                # First live telemetry capture from configured baseline
                meaningful = True

    for sid in prev_sources:
        if sid not in curr_sources:
            changes.append(f"Removed evaluation source `{sid}`")
            routing_changed = True
            meaningful = True

    prev_hash = previous.get("content_hash")
    if prev_hash and prev_hash != current.get("content_hash"):
        routing_changed = True
        meaningful = True

    if not changes:
        changes.append("Refreshed live source telemetry and dashboard (no routing policy changes).")

    return changes, routing_changed, meaningful


def build_routing_matrix(
    sources_cfg: Dict[str, Any],
    allow_live_fetch: bool = False,
    now: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    dt = now or utc_now()
    week_id = current_week_id(dt)
    generated_at = utc_now_iso(dt)

    eval_sources = sources_cfg.get("evaluation_sources", [])
    if allow_live_fetch:
        source_status = probe_public_sources(eval_sources)
    else:
        source_status = [
            {
                "id": s.get("id", "unknown"),
                "kind": s.get("kind", "unknown"),
                "url": s.get("url", ""),
                "notes": s.get("notes", ""),
                "status": "configured",
                "http_status": None,
                "healthy": None,
                "latency_ms": None,
                "last_modified": None,
                "checked_at": None,
            }
            for s in eval_sources
        ]

    gov_cfg = sources_cfg.get("governance", {})
    matrix: Dict[str, Any] = {
        "schema_version": str(sources_cfg.get("schema_version", "1.1.0")),
        "week_id": week_id,
        "generated_at": generated_at,
        "repository": str(sources_cfg.get("repository", "maximusmaximus/agentic-model-matrix")),
        "pages_url": str(sources_cfg.get("pages_url", "https://maximusmaximus.github.io/agentic-model-matrix/")),
        "governance": {
            "cadence": sources_cfg.get("cadence", "weekly"),
            "requires_pr_merge": bool(gov_cfg.get("requires_pr_merge", True)),
            "auto_merge_on_ci_pass": bool(gov_cfg.get("auto_merge_on_ci_pass", True)),
            "branch_prefix": gov_cfg.get("branch_prefix", "chore/weekly-matrix-"),
        },
        "app_build_policy": {
            "stage_id": "app_build",
            "provider": "antigravity",
            "model_family": "gemini",
            "quota_fallback_enabled": True,
        },
        "evaluation_sources": source_status,
        "stages": sources_cfg.get("stage_profiles", []),
    }
    matrix["content_hash"] = compute_content_hash(matrix)
    return matrix


def compute_stats_and_history(
    matrix: Dict[str, Any],
    existing_history: Optional[Dict[str, Any]],
    previous_matrix: Optional[Dict[str, Any]],
    changes: List[str],
    routing_changed: bool,
    trigger: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    stages = matrix.get("stages", [])
    sources = matrix.get("evaluation_sources", [])

    primary_counts = Counter(s["primary_model"] for s in stages)
    all_slot_models = [m for s in stages for m in s.get("fallback_chain", [])]
    unique_models = sorted(set(all_slot_models))
    family_slots = Counter(_model_family(m) for m in all_slot_models)
    family_primary = Counter(_model_family(s["primary_model"]) for s in stages)

    latencies = [s["latency_ms"] for s in sources if isinstance(s.get("latency_ms"), (int, float))]
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None
    healthy_count = sum(1 for s in sources if s.get("healthy") is True)
    sources_total = len(sources)
    health_pct = round((healthy_count / sources_total) * 100.0, 1) if sources_total else 0.0
    bp_count = sum(len(s.get("best_practices", [])) for s in stages)

    prior_runs: List[Dict[str, Any]] = []
    if existing_history and isinstance(existing_history.get("runs"), list):
        prior_runs = list(existing_history["runs"])
    elif previous_matrix and previous_matrix.get("generated_at"):
        # Seed baseline run from initial matrix commit when bootstrapping history.json
        prev_sources = previous_matrix.get("evaluation_sources", [])
        prior_runs.append({
            "timestamp": previous_matrix["generated_at"],
            "week_id": previous_matrix.get("week_id", matrix["week_id"]),
            "schema_version": previous_matrix.get("schema_version", "1.0.0"),
            "content_hash": previous_matrix.get("content_hash") or compute_content_hash(previous_matrix),
            "trigger": "initial-baseline",
            "routing_changed": True,
            "sources_healthy": sum(1 for s in prev_sources if str(s.get("status", "")).startswith("http_2")),
            "sources_total": len(prev_sources),
            "avg_latency_ms": None,
            "changes": ["Initial weekly best-practices & SDLC model routing matrix baseline."],
        })

    new_run = {
        "timestamp": matrix["generated_at"],
        "week_id": matrix["week_id"],
        "schema_version": matrix["schema_version"],
        "content_hash": matrix["content_hash"],
        "trigger": trigger,
        "routing_changed": routing_changed,
        "sources_healthy": healthy_count,
        "sources_total": sources_total,
        "avg_latency_ms": avg_latency,
        "changes": changes,
    }

    runs = [new_run] + prior_runs
    runs = runs[:MAX_HISTORY_RUNS]

    total_routing_changes = sum(1 for r in runs if r.get("routing_changed"))
    last_model_change_at = next(
        (r["timestamp"] for r in runs if r.get("routing_changed")),
        matrix["generated_at"],
    )

    app_stage = next(s for s in stages if s["id"] == "app_build")
    stage5_all_gemini = all("gemini" in m.lower() for m in app_stage["fallback_chain"])

    matrix_stats = {
        "stages_count": len(stages),
        "unique_models_count": len(unique_models),
        "total_fallback_slots": len(all_slot_models),
        "best_practices_count": bp_count,
        "sources_total": sources_total,
        "sources_healthy": healthy_count,
        "sources_health_pct": health_pct,
        "avg_source_latency_ms": avg_latency,
        "total_recorded_runs": len(runs),
        "stage5_pinned_to_gemini": stage5_all_gemini,
    }
    matrix["stats"] = matrix_stats
    matrix["changes_since_previous"] = changes

    stats_doc = {
        "schema_version": matrix["schema_version"],
        "week_id": matrix["week_id"],
        "generated_at": matrix["generated_at"],
        "content_hash": matrix["content_hash"],
        "repository": matrix["repository"],
        "pages_url": matrix["pages_url"],
        "last_update": {
            "timestamp": matrix["generated_at"],
            "week_id": matrix["week_id"],
            "trigger": trigger,
            "routing_changed": routing_changed,
            "diff_count": len(changes),
            "changes": changes,
        },
        "metrics": {
            **matrix_stats,
            "total_routing_changes": total_routing_changes,
            "last_model_change_at": last_model_change_at,
        },
        "model_distribution": {
            "unique_models": unique_models,
            "primary_models": dict(primary_counts),
            "family_primary_counts": dict(family_primary),
            "family_slot_counts": dict(family_slots),
        },
        "stage_5_compliance": {
            "pinned": True,
            "stage_id": "app_build",
            "provider": app_stage["primary_provider"],
            "model_family": app_stage["model_family"],
            "primary_model": app_stage["primary_model"],
            "fallback_depth": len(app_stage["fallback_chain"]),
            "all_gemini": stage5_all_gemini,
        },
        "source_health": sources,
    }

    history_doc = {
        "schema_version": matrix["schema_version"],
        "repository": matrix["repository"],
        "max_entries": MAX_HISTORY_RUNS,
        "updated_at": matrix["generated_at"],
        "total_runs": len(runs),
        "runs": runs,
    }

    return stats_doc, history_doc


def render_best_practices_md(matrix: Dict[str, Any]) -> str:
    stats = matrix.get("stats", {})
    healthy = stats.get("sources_healthy", 0)
    total_src = stats.get("sources_total", len(matrix.get("evaluation_sources", [])))
    avg_lat = stats.get("avg_source_latency_ms")
    lat_str = f"{avg_lat:.0f} ms" if isinstance(avg_lat, (int, float)) else "n/a"

    lines: List[str] = [
        "# Weekly Coding Best Practices & SDLC Model Routing Matrix",
        "",
        f"- **Week:** `{matrix['week_id']}`",
        f"- **Schema Version:** `{matrix['schema_version']}`",
        f"- **Generated At (UTC):** `{matrix['generated_at']}`",
        f"- **Content Hash:** `{matrix.get('content_hash', '')[:12]}`",
        f"- **Evaluation Sources:** `{healthy}/{total_src}` healthy (avg probe latency `{lat_str}`)",
        "- **Governance:** PR-merge gated (`requires_pr_merge: true`) — CI validates security, schema, tests, and site parity before merge.",
        "- **App Build Policy:** **Stage 5 (`app_build`) is strictly pinned to Gemini models running on Antigravity (`agy`)** with an ordered quota fallback chain.",
        "",
        "---",
        "",
        "## 1. Weekly Model-to-Stage Routing Summary",
        "",
        "| Stage | Phase | Primary Model | Effort | `agy` Mode | Ordered Fallback Chain |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for s in matrix["stages"]:
        chain_fmt = " → ".join(f"`{m}`" for m in s["fallback_chain"])
        lines.append(
            f"| {s['order']}. `{s['id']}` | {s['title']} | `{s['primary_model']}` | `{s['effort']}` | `{s['cli_mode']}` | {chain_fmt} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 2. Stage Best Practices & Selection Rationale",
        "",
    ])

    for s in matrix["stages"]:
        lines.append(f"### {s['order']}. {s['title']} (`{s['id']}`)")
        lines.append("")
        lines.append(
            f"- **Primary Provider / Model:** `{s['primary_provider']}` / `{s['primary_model']}` (`effort={s['effort']}`, `mode={s['cli_mode']}`)"
        )
        if s["id"] == "app_build":
            lines.append(
                "- **Hard Constraint:** Must use **Gemini models on Antigravity**. On quota/capacity exhaustion, step down along `fallback_chain` while keeping the same Antigravity `--conversation` ID."
            )
        lines.append(f"- **Fallback Chain:** {', '.join(f'`{m}`' for m in s['fallback_chain'])}")
        lines.append("")
        lines.append("**Selection Criteria:**")
        for c in s.get("selection_criteria", []):
            lines.append(f"- {c}")
        lines.append("")
        lines.append("**Coding & Workflow Best Practices:**")
        for bp in s.get("best_practices", []):
            lines.append(f"- {bp}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 3. Cross-Cutting Engineering Standards (All Built Web Applications)",
        "",
        "1. **Golden Stacks & Verification:** Default greenfield web apps to **Next.js (App Router + TypeScript + Tailwind + SQLite/D1/Postgres)** or **FastAPI + React/Vite** when Python constraints apply, bundled with typecheck, build, and HTTP smoke-test checks.",
        "2. **Cloudflare Runtime & Storage:** Target **Cloudflare Workers / Pages** for compute/preview delivery and **Cloudflare R2** for transcripts, build bundles, and exported assets.",
        "3. **Swappable Adapter Boundaries:** Keep scheduling, calendar, meeting, transcript, research, repository, and deployment providers behind typed interfaces so any vendor can be swapped via configuration.",
        "4. **Quote-Backed Traceability:** Every shipped requirement (`REQ-*`) must trace to a verbatim speaker quote or an approved research brief (`RES-*`).",
        "5. **Zero-Leak Public Hygiene:** Run `scripts/security_scan.py` in pre-commit and CI; never commit keys, private hostnames, local filesystem paths, personal emails, or internal IP addresses.",
        "",
        "## 4. Reference Evaluation Sources",
        "",
        "| Source ID | Kind | URL | Status | Latency | Last-Modified |",
        "| --- | --- | --- | --- | --- | --- |",
    ])

    for src in matrix.get("evaluation_sources", []):
        lat = f"`{round(src['latency_ms'])} ms`" if isinstance(src.get("latency_ms"), (int, float)) else "—"
        lm = f"`{src['last_modified']}`" if src.get("last_modified") else "—"
        lines.append(
            f"| `{src['id']}` | `{src['kind']}` | {src['url']} | `{src['status']}` | {lat} | {lm} |"
        )

    lines.append("")
    return "\n".join(lines)


def render_changelog_md(history_doc: Dict[str, Any]) -> str:
    lines = [
        "# Changelog — Agentic Model Matrix",
        "",
        "Automated ledger of every matrix update, routing diff, and live source probe recorded by CI.",
        "",
        f"- **Last Updated (UTC):** `{history_doc['updated_at']}`",
        f"- **Recorded Runs:** `{history_doc['total_runs']}` (retained up to `{history_doc['max_entries']}`)",
        "",
    ]
    for run in history_doc.get("runs", []):
        tag = "routing change" if run.get("routing_changed") else "telemetry refresh"
        health = f"{run.get('sources_healthy', 0)}/{run.get('sources_total', 0)} healthy"
        lat = f", avg {round(run['avg_latency_ms'])} ms" if isinstance(run.get("avg_latency_ms"), (int, float)) else ""
        lines.append(f"## {run['timestamp']} — `{run['week_id']}` ({tag})")
        lines.append("")
        lines.append(
            f"- **Trigger:** `{run.get('trigger', 'ci')}` | **Hash:** `{str(run.get('content_hash', ''))[:12]}` | **Sources:** `{health}{lat}`"
        )
        for ch in run.get("changes", []):
            lines.append(f"- {ch}")
        lines.append("")
    return "\n".join(lines)


def render_llms_txt(matrix: Dict[str, Any]) -> str:
    repo = matrix.get("repository", "maximusmaximus/agentic-model-matrix")
    pages = matrix.get("pages_url", "https://maximusmaximus.github.io/agentic-model-matrix/").rstrip("/") + "/"
    raw_base = f"https://raw.githubusercontent.com/{repo}/main/"

    lines = [
        "# Agentic Model Matrix",
        "",
        "> Machine-readable SDLC model routing matrix and weekly coding best practices.",
        "> Hard invariant: Stage 5 (`app_build`) is strictly pinned to Gemini models running on Antigravity (`agy`).",
        "",
        "## Live Metadata",
        f"- Week ID: {matrix['week_id']}",
        f"- Schema Version: {matrix['schema_version']}",
        f"- Last Updated (UTC): {matrix['generated_at']}",
        f"- Content Hash: {matrix.get('content_hash', '')}",
        f"- Live Dashboard: {pages}",
        "",
        "## Primary Machine Endpoints (GitHub Pages — CORS enabled)",
        f"- [Routing Matrix JSON]({pages}routing.json): Authoritative 6-stage model selection, effort, CLI modes, and ordered fallback chains.",
        f"- [Live Stats & Source Health JSON]({pages}stats.json): Probe health, latencies, model distribution, and Stage 5 compliance.",
        f"- [Run & Change History JSON]({pages}history.json): Chronological ledger of CI runs and routing diffs.",
        f"- [JSON Schema Contract]({pages}schema/routing.schema.json): JSON Schema Draft 2020-12 contract.",
        f"- [Coding Best Practices Playbook]({pages}BEST_PRACTICES.md): Human- and agent-readable engineering guidelines per stage.",
        f"- [Changelog]({pages}CHANGELOG.md): Recent model routing changes and telemetry updates.",
        "",
        "## Raw GitHub Endpoints",
        f"- {raw_base}routing.json",
        f"- {raw_base}stats.json",
        f"- {raw_base}history.json",
        f"- {raw_base}schema/routing.schema.json",
        f"- {raw_base}BEST_PRACTICES.md",
        "",
        "## Active Stage Summary",
    ]
    for s in matrix.get("stages", []):
        chain = " -> ".join(s["fallback_chain"])
        lines.append(
            f"- Stage {s['order']} ({s['id']}): primary={s['primary_model']} effort={s['effort']} mode={s['cli_mode']} | chain=[{chain}]"
        )
    lines.append("")
    return "\n".join(lines)


def render_readme_live_block(
    matrix: Dict[str, Any],
    stats_doc: Dict[str, Any],
    history_doc: Dict[str, Any],
) -> str:
    metrics = stats_doc["metrics"]
    avg_lat = metrics.get("avg_source_latency_ms")
    lat_txt = f"{round(avg_lat)} ms" if isinstance(avg_lat, (int, float)) else "n/a"
    health_txt = f"{metrics['sources_healthy']}/{metrics['sources_total']} ({metrics['sources_health_pct']:.0f}%)"

    lines = [
        README_START_MARKER,
        f"> **Last Updated:** `{matrix['generated_at']}` · **Week:** `{matrix['week_id']}` · **Sources:** `{health_txt}` (avg `{lat_txt}`) · **CI Runs:** `{metrics['total_recorded_runs']}` · **Hash:** `{matrix['content_hash'][:12]}`",
        "",
        "| Stage | Phase | Primary Model | Effort | `agy` Mode | Fallback Chain |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for s in matrix["stages"]:
        lock = " 🔒" if s["id"] == "app_build" else ""
        chain = " → ".join(f"`{m}`" for m in s["fallback_chain"])
        lines.append(
            f"| {s['order']}. `{s['id']}`{lock} | {s['title']} | `{s['primary_model']}` | `{s['effort']}` | `{s['cli_mode']}` | {chain} |"
        )

    lines.extend([
        "",
        "### Latest Changes & Updates",
        "",
    ])
    for run in history_doc.get("runs", [])[:5]:
        summary = "; ".join(run.get("changes", [])[:3])
        extra = f" (+{len(run['changes']) - 3} more)" if len(run.get("changes", [])) > 3 else ""
        lines.append(
            f"- **`{run['timestamp']}`** (`{run['week_id']}`, `{run.get('trigger', 'ci')}`): {summary}{extra}"
        )

    lines.append(README_END_MARKER)
    return "\n".join(lines)


def _write_lf(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def sync_readme(root: Path, live_block: str) -> bool:
    readme_path = root / "README.md"
    if not readme_path.exists():
        return False
    text = readme_path.read_text(encoding="utf-8")
    if README_START_MARKER not in text or README_END_MARKER not in text:
        return False
    pattern = re.compile(
        re.escape(README_START_MARKER) + r".*?" + re.escape(README_END_MARKER),
        re.DOTALL,
    )
    updated = pattern.sub(lambda _m: live_block, text, count=1)
    if updated != text:
        _write_lf(readme_path, updated)
    return True


def verify_existing(root: Path) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    routing_path = root / "routing.json"
    schema_path = root / "schema" / "routing.schema.json"
    required_files = [
        "routing.json",
        "stats.json",
        "history.json",
        "BEST_PRACTICES.md",
        "CHANGELOG.md",
        "llms.txt",
        "README.md",
        "docs/index.html",
        "docs/routing.json",
        "docs/stats.json",
        "docs/history.json",
        "docs/llms.txt",
        "docs/.nojekyll",
    ]
    for rel in required_files:
        if not (root / rel).exists():
            errors.append(f"Missing required artifact: {rel}")

    if errors:
        return False, errors

    routing = json.loads(routing_path.read_text(encoding="utf-8"))
    ok, errs = validate_matrix(routing, schema_path=schema_path)
    if not ok:
        errors.extend(errs)

    stats = json.loads((root / "stats.json").read_text(encoding="utf-8"))
    history = json.loads((root / "history.json").read_text(encoding="utf-8"))
    docs_routing = json.loads((root / "docs" / "routing.json").read_text(encoding="utf-8"))

    if stats.get("content_hash") != routing.get("content_hash"):
        errors.append("stats.json content_hash does not match routing.json")
    if stats.get("generated_at") != routing.get("generated_at"):
        errors.append("stats.json generated_at does not match routing.json")
    if not history.get("runs"):
        errors.append("history.json must contain at least 1 recorded run")
    elif history["runs"][0].get("timestamp") != routing.get("generated_at"):
        errors.append("history.json latest run timestamp does not match routing.json")
    if docs_routing != routing:
        errors.append("docs/routing.json is out of sync with root routing.json")

    bp_text = (root / "BEST_PRACTICES.md").read_text(encoding="utf-8")
    if routing["week_id"] not in bp_text or routing["generated_at"] not in bp_text:
        errors.append("BEST_PRACTICES.md is out of sync with routing.json")

    readme_text = (root / "README.md").read_text(encoding="utf-8")
    if README_START_MARKER not in readme_text or README_END_MARKER not in readme_text:
        errors.append("README.md is missing MATRIX_LIVE_STATS markers")
    elif routing["generated_at"] not in readme_text:
        errors.append("README.md live stats block is out of sync with routing.json")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify weekly best-practices, model routing matrix, stats, changelog, and GitHub Pages."
    )
    parser.add_argument("--root", default=".", help="Repository root containing sources.yaml")
    parser.add_argument("--allow-live-fetch", action="store_true", help="Probe public evaluation URLs during generation")
    parser.add_argument("--if-changed", action="store_true", help="Skip rewriting if week_id, routing hash, and source headers are unchanged")
    parser.add_argument("--force", action="store_true", help="Force regeneration even when --if-changed is set")
    parser.add_argument("--trigger", default="manual", help="Trigger label recorded in stats/history")
    parser.add_argument("--check", action="store_true", help="Verify existing artifacts match schema, policy, and site parity without rewriting")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    sources_path = root / "sources.yaml"
    schema_path = root / "schema" / "routing.schema.json"
    routing_path = root / "routing.json"
    stats_path = root / "stats.json"
    history_path = root / "history.json"
    bp_path = root / "BEST_PRACTICES.md"
    changelog_path = root / "CHANGELOG.md"
    llms_path = root / "llms.txt"

    if not sources_path.exists():
        print(f"ERROR: Missing {sources_path}", file=sys.stderr)
        return 1

    if args.check:
        ok, errs = verify_existing(root)
        if not ok:
            print("CHECK FAILED:", file=sys.stderr)
            for err in errs:
                print(f"  - {err}", file=sys.stderr)
            return 1
        existing = json.loads(routing_path.read_text(encoding="utf-8"))
        print(
            f"CHECK PASSED: routing.json ({existing['week_id']}, hash {existing.get('content_hash', '')[:12]}), "
            f"stats, history, README live block, and docs/ site are valid and in sync."
        )
        return 0

    previous_matrix = json.loads(routing_path.read_text(encoding="utf-8")) if routing_path.exists() else None
    existing_history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else None

    sources_cfg = load_sources(sources_path)
    matrix = build_routing_matrix(sources_cfg, allow_live_fetch=args.allow_live_fetch)

    changes, routing_changed, meaningful = compute_matrix_diff(previous_matrix, matrix)
    if args.if_changed and not args.force and not meaningful:
        print("NO_CHANGES: week_id, routing hash, and upstream source headers are unchanged.")
        return 0

    stats_doc, history_doc = compute_stats_and_history(
        matrix=matrix,
        existing_history=existing_history,
        previous_matrix=previous_matrix,
        changes=changes,
        routing_changed=routing_changed,
        trigger=args.trigger,
    )

    ok, errs = validate_matrix(matrix, schema_path=schema_path)
    if not ok:
        print("GENERATION VALIDATION FAILED:", file=sys.stderr)
        for err in errs:
            print(f"  - {err}", file=sys.stderr)
        return 1

    _write_lf(routing_path, json.dumps(matrix, indent=2, ensure_ascii=False) + "\n")
    _write_lf(stats_path, json.dumps(stats_doc, indent=2, ensure_ascii=False) + "\n")
    _write_lf(history_path, json.dumps(history_doc, indent=2, ensure_ascii=False) + "\n")
    _write_lf(bp_path, render_best_practices_md(matrix))
    _write_lf(changelog_path, render_changelog_md(history_doc))
    _write_lf(llms_path, render_llms_txt(matrix))

    live_block = render_readme_live_block(matrix, stats_doc, history_doc)
    sync_readme(root, live_block)
    build_site.build_site(root)

    print(
        f"GENERATED: routing.json, stats.json, history.json, BEST_PRACTICES.md, CHANGELOG.md, "
        f"llms.txt, README.md, and docs/ for week {matrix['week_id']} (hash {matrix['content_hash'][:12]})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
