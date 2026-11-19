import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_weekly_matrix as gen
import security_scan


def test_routing_matrix_valid_and_pinned_to_gemini_antigravity():
    routing_path = ROOT / "routing.json"
    schema_path = ROOT / "schema" / "routing.schema.json"
    assert routing_path.exists(), "routing.json must exist"
    data = json.loads(routing_path.read_text(encoding="utf-8"))
    ok, errs = gen.validate_matrix(data, schema_path=schema_path)
    assert ok, f"Validation failed: {errs}"

    app_stage = [s for s in data["stages"] if s["id"] == "app_build"][0]
    assert app_stage["primary_provider"] == "antigravity"
    assert app_stage["model_family"] == "gemini"
    assert all("gemini" in m.lower() for m in app_stage["fallback_chain"])


def test_non_gemini_model_in_app_build_is_rejected():
    data = json.loads((ROOT / "routing.json").read_text(encoding="utf-8"))
    mutated = copy.deepcopy(data)
    for stage in mutated["stages"]:
        if stage["id"] == "app_build":
            stage["primary_model"] = "claude-opus-5-5-high"
            stage["fallback_chain"][0] = "claude-opus-5-5-high"
    ok, errs = gen.validate_matrix(mutated)
    assert not ok
    assert any("Gemini-on-Antigravity" in e for e in errs)


def test_all_generated_artifacts_and_docs_in_sync():
    ok, errs = gen.verify_existing(ROOT)
    assert ok, f"Artifact sync/parity check failed: {errs}"


def test_best_practices_and_llms_txt_contain_stages_and_metadata():
    data = json.loads((ROOT / "routing.json").read_text(encoding="utf-8"))
    md = (ROOT / "BEST_PRACTICES.md").read_text(encoding="utf-8")
    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    index_html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")

    assert data["week_id"] in md
    assert data["week_id"] in llms
    assert data["week_id"] in index_html
    for stage in data["stages"]:
        assert stage["id"] in md
        assert stage["primary_model"] in md
        assert stage["primary_model"] in llms


def test_stats_and_history_structure():
    routing = json.loads((ROOT / "routing.json").read_text(encoding="utf-8"))
    stats = json.loads((ROOT / "stats.json").read_text(encoding="utf-8"))
    history = json.loads((ROOT / "history.json").read_text(encoding="utf-8"))

    assert stats["content_hash"] == routing["content_hash"]
    assert stats["stage_5_compliance"]["all_gemini"] is True
    assert stats["metrics"]["stages_count"] == 6
    assert history["total_runs"] == len(history["runs"])
    assert history["runs"][0]["timestamp"] == routing["generated_at"]


def test_diff_engine_detects_model_change_and_noop():
    routing = json.loads((ROOT / "routing.json").read_text(encoding="utf-8"))
    # Identical matrix -> no routing change, no meaningful update
    changes, routing_changed, meaningful = gen.compute_matrix_diff(routing, copy.deepcopy(routing))
    assert not routing_changed
    assert not meaningful
    assert changes

    # Mutate a primary model -> routing change detected
    updated = copy.deepcopy(routing)
    updated["stages"][0]["primary_model"] = "gemini-4-neon-high"
    updated["stages"][0]["fallback_chain"][0] = "gemini-4-neon-high"
    updated["content_hash"] = gen.compute_content_hash(updated)
    changes2, routing_changed2, meaningful2 = gen.compute_matrix_diff(routing, updated)
    assert routing_changed2
    assert meaningful2
    assert any("triage" in c and "gemini-4-neon-high" in c for c in changes2)


def test_security_scan_passes_clean_repo():
    findings = security_scan.scan_repository(ROOT)
    assert findings == [], f"Unexpected security findings: {findings}"


def test_security_scan_detects_leaks():
    # security-scan:ignore — intentional synthetic test fixture
    sample = "token=ghp_1234567890abcdefghij1234567890\nhost=box.tailabc123.ts.net\n"  # security-scan:ignore
    # Remove ignore comment on split lines when invoking scan_text directly
    clean_sample = sample.replace("  # security-scan:ignore", "")
    findings = security_scan.scan_text(clean_sample, "synthetic.txt")
    rules = {f["rule"] for f in findings}
    assert "github_token" in rules
    assert "tailscale_domain" in rules
