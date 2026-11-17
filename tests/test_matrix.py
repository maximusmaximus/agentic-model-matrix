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
    assert routing_path.exists(), "routing.json must exist"
    data = json.loads(routing_path.read_text(encoding="utf-8"))
    ok, errs = gen.validate_matrix(data)
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


def test_best_practices_markdown_contains_week_id_and_stages():
    data = json.loads((ROOT / "routing.json").read_text(encoding="utf-8"))
    md = (ROOT / "BEST_PRACTICES.md").read_text(encoding="utf-8")
    assert data["week_id"] in md
    for stage in data["stages"]:
        assert stage["id"] in md
        assert stage["primary_model"] in md


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
