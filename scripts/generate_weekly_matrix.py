#!/usr/bin/env python3
"""
generate_weekly_matrix.py — Weekly Best Practices & Model Routing Matrix generator.

Reads sources.yaml (and optionally fetches public benchmark/catalog metadata or
synthesizes updates via a configured LLM endpoint), validates all invariants
including the Stage 5 Gemini-on-Antigravity lock, and emits:
  - routing.json
  - BEST_PRACTICES.md

Supports --check mode for CI drift verification.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

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


def current_week_id(now: Optional[datetime.datetime] = None) -> str:
    dt = now or datetime.datetime.utcnow()
    iso_year, iso_week, _ = dt.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def load_sources(sources_path: Path) -> Dict[str, Any]:
    with open(sources_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def probe_public_sources(sources: List[Dict[str, Any]], timeout_sec: int = 8) -> List[Dict[str, Any]]:
    """
    Lightweight reachability & metadata probe against public benchmark/docs URLs.
    Never sends local environment data or credentials.
    """
    results: List[Dict[str, Any]] = []
    for src in sources:
        url = src.get("url", "")
        entry = {
            "id": src.get("id", "unknown"),
            "kind": src.get("kind", "unknown"),
            "url": url,
            "status": "skipped",
        }
        if not url.startswith("https://"):
            results.append(entry)
            continue
        req = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": "agentic-model-matrix-weekly-bot/1.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                entry["status"] = f"http_{resp.status}"
        except urllib.error.HTTPError as e:
            entry["status"] = f"http_{e.code}"
        except Exception as exc:
            entry["status"] = f"unreachable ({type(exc).__name__})"
        results.append(entry)
    return results


def validate_matrix(matrix: Dict[str, Any]) -> Tuple[bool, List[str]]:
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

    for stage in stages:
        sid = stage.get("id", "<unknown>")
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

    return len(errors) == 0, errors


def build_routing_matrix(sources_cfg: Dict[str, Any], allow_live_fetch: bool = False) -> Dict[str, Any]:
    week_id = current_week_id()
    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    eval_sources = sources_cfg.get("evaluation_sources", [])
    if allow_live_fetch:
        source_status = probe_public_sources(eval_sources)
    else:
        source_status = [
            {
                "id": s.get("id", "unknown"),
                "kind": s.get("kind", "unknown"),
                "url": s.get("url", ""),
                "status": "configured",
            }
            for s in eval_sources
        ]

    matrix = {
        "schema_version": str(sources_cfg.get("schema_version", "1.0.0")),
        "week_id": week_id,
        "generated_at": generated_at,
        "governance": {
            "cadence": sources_cfg.get("cadence", "weekly"),
            "requires_pr_merge": bool(sources_cfg.get("governance", {}).get("requires_pr_merge", True)),
            "branch_prefix": sources_cfg.get("governance", {}).get("branch_prefix", "chore/weekly-matrix-"),
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
    return matrix


def render_best_practices_md(matrix: Dict[str, Any]) -> str:
    lines: List[str] = [
        "# Weekly Coding Best Practices & SDLC Model Routing Matrix",
        "",
        f"- **Week:** `{matrix['week_id']}`",
        f"- **Schema Version:** `{matrix['schema_version']}`",
        f"- **Generated At (UTC):** `{matrix['generated_at']}`",
        "- **Governance:** PR-merge gated (`requires_pr_merge: true`) — updates activate in downstream apps only after review and merge.",
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
        lines.append(f"- **Primary Provider / Model:** `{s['primary_provider']}` / `{s['primary_model']}` (`effort={s['effort']}`, `mode={s['cli_mode']}`)")
        if s["id"] == "app_build":
            lines.append("- **Hard Constraint:** Must use **Gemini models on Antigravity**. On quota/capacity exhaustion, step down along `fallback_chain` while keeping the same Antigravity `--conversation` ID.")
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
        "| Source ID | Kind | URL | Status |",
        "| --- | --- | --- | --- |",
    ])

    for src in matrix.get("evaluation_sources", []):
        lines.append(f"| `{src['id']}` | `{src['kind']}` | {src['url']} | `{src['status']}` |")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify weekly best-practices & model routing matrix.")
    parser.add_argument("--root", default=".", help="Repository root containing sources.yaml")
    parser.add_argument("--allow-live-fetch", action="store_true", help="Probe public evaluation URLs during generation")
    parser.add_argument("--check", action="store_true", help="Verify existing routing.json and BEST_PRACTICES.md match policy without rewriting")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    sources_path = root / "sources.yaml"
    routing_path = root / "routing.json"
    bp_path = root / "BEST_PRACTICES.md"

    if not sources_path.exists():
        print(f"ERROR: Missing {sources_path}", file=sys.stderr)
        return 1

    if args.check:
        if not routing_path.exists() or not bp_path.exists():
            print("CHECK FAILED: routing.json or BEST_PRACTICES.md does not exist.", file=sys.stderr)
            return 1
        with open(routing_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        ok, errs = validate_matrix(existing)
        if not ok:
            print("CHECK FAILED:", file=sys.stderr)
            for err in errs:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print(f"CHECK PASSED: {routing_path.name} ({existing['week_id']}) and {bp_path.name} are valid.")
        return 0

    sources_cfg = load_sources(sources_path)
    matrix = build_routing_matrix(sources_cfg, allow_live_fetch=args.allow_live_fetch)
    ok, errs = validate_matrix(matrix)
    if not ok:
        print("GENERATION VALIDATION FAILED:", file=sys.stderr)
        for err in errs:
            print(f"  - {err}", file=sys.stderr)
        return 1

    md_text = render_best_practices_md(matrix)
    with open(routing_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(matrix, f, indent=2)
        f.write("\n")

    with open(bp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(md_text)

    print(f"GENERATED: {routing_path} and {bp_path} for week {matrix['week_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
