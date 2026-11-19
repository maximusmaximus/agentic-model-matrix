#!/usr/bin/env python3
"""
build_site.py — Builds the static GitHub Pages dashboard & static JSON/Markdown API in docs/.

Generates:
  - docs/.nojekyll
  - docs/index.html        (self-contained live dashboard for humans & agents)
  - docs/routing.json      (CORS-friendly static API mirror)
  - docs/stats.json
  - docs/history.json
  - docs/BEST_PRACTICES.md
  - docs/CHANGELOG.md
  - docs/llms.txt
  - docs/schema/routing.schema.json
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict


MIRROR_FILES = [
    "routing.json",
    "stats.json",
    "history.json",
    "BEST_PRACTICES.md",
    "CHANGELOG.md",
    "llms.txt",
    "schema/routing.schema.json",
]


def _safe_json_for_script_tag(payload: Dict[str, Any]) -> str:
    """Serialize JSON safely for embedding inside an HTML <script type="application/json"> tag."""
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    return raw.replace("</", "<\\/").replace("<!--", "<\\!--")


def render_index_html(
    routing: Dict[str, Any],
    stats: Dict[str, Any],
    history: Dict[str, Any],
) -> str:
    repo = str(routing.get("repository") or "maximusmaximus/agentic-model-matrix")
    pages_url = str(routing.get("pages_url") or f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/")
    if not pages_url.endswith("/"):
        pages_url += "/"
    week_id = html.escape(str(routing.get("week_id", "")))
    generated_at = html.escape(str(routing.get("generated_at", "")))
    schema_version = html.escape(str(routing.get("schema_version", "")))
    content_hash = html.escape(str(routing.get("content_hash", ""))[:12])

    embedded_payload = _safe_json_for_script_tag({
        "routing": routing,
        "stats": stats,
        "history": history,
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Agentic Model Matrix — Live SDLC Routing &amp; Best Practices ({week_id})</title>
  <meta name="description" content="CI-automated Coding Best Practices and 6-stage SDLC Model Routing Matrix (Stage 5 strictly pinned to Gemini on Antigravity) with live source health, stats, and change history." />
  <style>
    :root {{
      --bg: #070b14;
      --bg-elev: #0e1525;
      --bg-card: #111a2e;
      --bg-card-hover: #16223b;
      --border: #1e2d4a;
      --border-strong: #2c4168;
      --text: #e6edf8;
      --text-muted: #93a4c3;
      --text-dim: #647597;
      --cyan: #38bdf8;
      --cyan-soft: rgba(56, 189, 248, 0.14);
      --emerald: #34d399;
      --emerald-soft: rgba(52, 211, 153, 0.14);
      --amber: #fbbf24;
      --amber-soft: rgba(251, 191, 36, 0.14);
      --rose: #fb7185;
      --rose-soft: rgba(251, 113, 133, 0.14);
      --violet: #a78bfa;
      --violet-soft: rgba(167, 139, 250, 0.14);
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, Helvetica, Arial, sans-serif;
      --radius: 12px;
      --radius-sm: 8px;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      background:
        radial-gradient(1200px 600px at 10% -10%, rgba(56, 189, 248, 0.10), transparent 60%),
        radial-gradient(900px 500px at 90% -10%, rgba(167, 139, 250, 0.09), transparent 60%),
        var(--bg);
      color: var(--text);
      font-family: var(--sans);
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }}
    a {{ color: var(--cyan); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code, pre {{ font-family: var(--mono); }}
    .container {{
      max-width: 1220px;
      margin: 0 auto;
      padding: 24px 20px 64px;
    }}
    .topbar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand-mark {{
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: linear-gradient(135deg, #38bdf8, #818cf8);
      display: grid;
      place-items: center;
      font-weight: 800;
      font-size: 16px;
      color: #070b14;
      letter-spacing: -0.04em;
      box-shadow: 0 6px 24px rgba(56, 189, 248, 0.25);
    }}
    .brand h1 {{
      margin: 0;
      font-size: 20px;
      letter-spacing: -0.02em;
    }}
    .brand-sub {{
      font-size: 13px;
      color: var(--text-muted);
    }}
    .nav-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .nav-btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 12px;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: var(--bg-elev);
      color: var(--text);
      font-size: 13px;
      font-weight: 500;
      transition: border-color 0.15s, background 0.15s;
    }}
    .nav-btn:hover {{
      border-color: var(--cyan);
      background: var(--bg-card-hover);
      text-decoration: none;
    }}
    .nav-btn.primary {{
      background: var(--cyan-soft);
      border-color: rgba(56, 189, 248, 0.45);
      color: var(--cyan);
    }}
    .hero {{
      background: linear-gradient(180deg, rgba(17, 26, 46, 0.92), rgba(14, 21, 37, 0.92));
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 22px 24px;
      margin-bottom: 22px;
    }}
    .pill-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      font-family: var(--mono);
      border: 1px solid var(--border);
      background: rgba(255, 255, 255, 0.03);
      color: var(--text-muted);
    }}
    .pill.emerald {{ background: var(--emerald-soft); border-color: rgba(52, 211, 153, 0.35); color: var(--emerald); }}
    .pill.cyan {{ background: var(--cyan-soft); border-color: rgba(56, 189, 248, 0.35); color: var(--cyan); }}
    .pill.violet {{ background: var(--violet-soft); border-color: rgba(167, 139, 250, 0.35); color: var(--violet); }}
    .pill.amber {{ background: var(--amber-soft); border-color: rgba(251, 191, 36, 0.35); color: var(--amber); }}
    .pill.rose {{ background: var(--rose-soft); border-color: rgba(251, 113, 133, 0.35); color: var(--rose); }}
    .dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: currentColor;
      display: inline-block;
    }}
    .hero p {{
      margin: 0;
      color: var(--text-muted);
      font-size: 15px;
      max-width: 920px;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
      gap: 12px;
      margin-bottom: 26px;
    }}
    .kpi {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 16px 18px;
    }}
    .kpi-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--text-dim);
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .kpi-value {{
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text);
    }}
    .kpi-sub {{
      margin-top: 4px;
      font-size: 12px;
      color: var(--text-muted);
      font-family: var(--mono);
    }}
    section {{
      margin-bottom: 28px;
    }}
    .section-head {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }}
    .section-head h2 {{
      margin: 0;
      font-size: 18px;
      letter-spacing: -0.01em;
    }}
    .section-sub {{
      font-size: 13px;
      color: var(--text-muted);
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .filter-btn {{
      background: var(--bg-elev);
      color: var(--text-muted);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px 11px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }}
    .filter-btn.active {{
      background: var(--cyan-soft);
      border-color: rgba(56, 189, 248, 0.5);
      color: var(--cyan);
    }}
    .search-input {{
      background: var(--bg-elev);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 6px 11px;
      color: var(--text);
      font-size: 13px;
      min-width: 210px;
    }}
    .search-input:focus {{
      outline: none;
      border-color: var(--cyan);
    }}
    .stage-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 14px;
    }}
    .stage-card {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      transition: border-color 0.15s;
    }}
    .stage-card:hover {{
      border-color: var(--border-strong);
    }}
    .stage-card.pinned {{
      border-color: rgba(52, 211, 153, 0.45);
      box-shadow: 0 0 0 1px rgba(52, 211, 153, 0.12) inset;
    }}
    .stage-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
    }}
    .stage-num {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--cyan);
      font-weight: 700;
    }}
    .stage-title {{
      margin: 2px 0 0;
      font-size: 16px;
      font-weight: 700;
    }}
    .model-box {{
      background: var(--bg-elev);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 10px 12px;
    }}
    .model-primary {{
      font-family: var(--mono);
      font-size: 14px;
      font-weight: 700;
      color: var(--text);
    }}
    .chain {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      margin-top: 8px;
    }}
    .chain-node {{
      font-family: var(--mono);
      font-size: 11px;
      padding: 3px 7px;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border);
      color: var(--text-muted);
    }}
    .chain-node.primary-node {{
      color: var(--cyan);
      border-color: rgba(56, 189, 248, 0.4);
      background: var(--cyan-soft);
    }}
    .chain-arrow {{
      color: var(--text-dim);
      font-size: 11px;
    }}
    .stage-lists {{
      font-size: 13px;
      color: var(--text-muted);
    }}
    .stage-lists h4 {{
      margin: 8px 0 4px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      color: var(--text-dim);
    }}
    .stage-lists ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .stage-lists li {{
      margin-bottom: 4px;
    }}
    .cmd-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      background: #090e1a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 10px;
      margin-top: auto;
    }}
    .cmd-code {{
      font-size: 11.5px;
      color: #cbd5e1;
      overflow-x: auto;
      white-space: nowrap;
    }}
    .copy-btn {{
      flex-shrink: 0;
      background: var(--bg-card);
      color: var(--text-muted);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 4px 9px;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
    }}
    .copy-btn:hover {{
      color: var(--cyan);
      border-color: var(--cyan);
    }}
    .two-col {{
      display: grid;
      grid-template-columns: 1.25fr 1fr;
      gap: 16px;
    }}
    @media (max-width: 900px) {{
      .two-col {{ grid-template-columns: 1fr; }}
      .stage-grid {{ grid-template-columns: 1fr; }}
    }}
    .panel {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px 20px;
    }}
    .panel h3 {{
      margin: 0 0 12px;
      font-size: 15px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      text-align: left;
      padding: 9px 10px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    th {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-dim);
      font-weight: 700;
    }}
    tr:last-child td {{ border-bottom: none; }}
    .bar-track {{
      width: 100%;
      height: 8px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.06);
      overflow: hidden;
      margin-top: 5px;
    }}
    .bar-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--cyan), var(--violet));
    }}
    .bar-fill.emerald {{ background: linear-gradient(90deg, #10b981, #34d399); }}
    .bar-fill.amber {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
    .bar-row {{
      margin-bottom: 12px;
    }}
    .bar-meta {{
      display: flex;
      justify-content: space-between;
      font-size: 12.5px;
      font-family: var(--mono);
    }}
    .change-list {{
      margin: 0;
      padding-left: 18px;
      font-size: 13px;
      color: var(--text);
    }}
    .change-list li {{ margin-bottom: 6px; }}
    .code-block {{
      background: #090e1a;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
      font-size: 12px;
      overflow-x: auto;
      color: #cbd5e1;
      margin: 10px 0 0;
      white-space: pre;
    }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 10px;
    }}
    .endpoint-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 8px 0;
      border-bottom: 1px solid var(--border);
      font-size: 13px;
    }}
    .endpoint-row:last-child {{ border-bottom: none; }}
    .footer {{
      margin-top: 36px;
      padding-top: 18px;
      border-top: 1px solid var(--border);
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      font-size: 12.5px;
      color: var(--text-dim);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">AM</div>
        <div>
          <h1>Agentic Model Matrix</h1>
          <div class="brand-sub">CI-Automated SDLC Model Routing &amp; Coding Best Practices</div>
        </div>
      </div>
      <nav class="nav-links" aria-label="Primary links">
        <a class="nav-btn primary" href="./routing.json">routing.json</a>
        <a class="nav-btn" href="./stats.json">stats.json</a>
        <a class="nav-btn" href="./history.json">history.json</a>
        <a class="nav-btn" href="./llms.txt">llms.txt</a>
        <a class="nav-btn" href="./BEST_PRACTICES.md">BEST_PRACTICES.md</a>
        <a class="nav-btn" href="https://github.com/{html.escape(repo)}" target="_blank" rel="noopener">GitHub Repo</a>
      </nav>
    </header>

    <div class="hero">
      <div class="pill-row" id="hero-pills">
        <span class="pill cyan"><span class="dot"></span> Week {week_id}</span>
        <span class="pill emerald"><span class="dot"></span> Stage 5 Locked: Gemini on Antigravity</span>
        <span class="pill violet">Schema v{schema_version}</span>
        <span class="pill" id="pill-updated">Updated {generated_at}</span>
        <span class="pill" id="pill-hash">Hash {content_hash}</span>
      </div>
      <p>
        Live, schema-validated routing matrix mapping frontier models across 6 autonomous SDLC stages.
        Continuously probed and updated via PR-gated GitHub Actions, verified with zero-leak security scans,
        and published as both a human dashboard and a static JSON API for AI agents.
      </p>
    </div>

    <div class="kpi-grid" id="kpi-grid"></div>

    <section aria-labelledby="routing-heading">
      <div class="section-head">
        <div>
          <h2 id="routing-heading">6-Stage Model Routing Matrix</h2>
          <div class="section-sub">Click any filter or copy ready-to-run <code>agy</code> CLI commands. Stage 5 is hard-locked to Gemini models.</div>
        </div>
        <div class="controls">
          <button class="filter-btn active" data-filter="all">All Stages</button>
          <button class="filter-btn" data-filter="gemini">Gemini Primary</button>
          <button class="filter-btn" data-filter="claude">Claude Primary</button>
          <button class="filter-btn" data-filter="plan">mode=plan</button>
          <button class="filter-btn" data-filter="accept-edits">mode=accept-edits</button>
          <input id="stage-search" class="search-input" type="search" placeholder="Search stage, model, practice..." aria-label="Search stages" />
        </div>
      </div>
      <div class="stage-grid" id="stage-grid"></div>
    </section>

    <section class="two-col" aria-label="Changes and Model Distribution">
      <div class="panel">
        <h3>Latest Update &amp; Changes</h3>
        <div id="latest-changes"></div>
      </div>
      <div class="panel">
        <h3>Model Family &amp; Slot Distribution</h3>
        <div id="model-distribution"></div>
      </div>
    </section>

    <section class="two-col" aria-label="Evaluation Sources and Run History">
      <div class="panel">
        <h3>Evaluation Source Health</h3>
        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr>
                <th>Source</th>
                <th>Status</th>
                <th>Latency</th>
                <th>Last-Modified</th>
              </tr>
            </thead>
            <tbody id="sources-tbody"></tbody>
          </table>
        </div>
      </div>
      <div class="panel">
        <h3>Recent CI Update Timeline</h3>
        <div style="overflow-x:auto;">
          <table>
            <thead>
              <tr>
                <th>Timestamp (UTC)</th>
                <th>Week / Trigger</th>
                <th>Health</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody id="history-tbody"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="two-col" aria-label="Agent and Developer Integration">
      <div class="panel">
        <h3>Machine-Readable Endpoints (CORS-Enabled)</h3>
        <div id="endpoints-list"></div>
      </div>
      <div class="panel">
        <h3>Quick Integration Snippets</h3>
        <div class="tabs" id="snippet-tabs">
          <button class="filter-btn active" data-tab="curl">curl + jq</button>
          <button class="filter-btn" data-tab="python">Python</button>
          <button class="filter-btn" data-tab="submodule">Git Submodule</button>
          <button class="filter-btn" data-tab="agent">Agent Prompt</button>
        </div>
        <div style="display:flex; justify-content:flex-end;">
          <button class="copy-btn" id="copy-snippet-btn">Copy snippet</button>
        </div>
        <pre class="code-block" id="snippet-code"></pre>
      </div>
    </section>

    <footer class="footer">
      <div>
        Published automatically by GitHub Actions from <a href="https://github.com/{html.escape(repo)}" target="_blank" rel="noopener">{html.escape(repo)}</a>.
      </div>
      <div>
        <a href="./schema/routing.schema.json">JSON Schema</a> ·
        <a href="./CHANGELOG.md">Changelog</a> ·
        <a href="./BEST_PRACTICES.md">Full Playbook</a> ·
        <a href="./llms.txt">llms.txt</a>
      </div>
    </footer>
  </div>

  <script id="initial-data" type="application/json">{embedded_payload}</script>
  <script>
    (function () {{
      const fallback = JSON.parse(document.getElementById("initial-data").textContent);
      let state = {{
        routing: fallback.routing,
        stats: fallback.stats,
        history: fallback.history,
        filter: "all",
        query: "",
        activeTab: "curl"
      }};

      function esc(str) {{
        return String(str == null ? "" : str)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }}

      function relativeTime(isoStr) {{
        if (!isoStr) return "unknown";
        const diffMs = Date.now() - Date.parse(isoStr);
        if (isNaN(diffMs)) return isoStr;
        const mins = Math.floor(diffMs / 60000);
        if (mins < 1) return "just now";
        if (mins < 60) return mins + "m ago";
        const hrs = Math.floor(mins / 60);
        if (hrs < 48) return hrs + "h ago";
        const days = Math.floor(hrs / 24);
        return days + "d ago";
      }}

      function copyText(text, btn) {{
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(text).then(function () {{
            if (btn) {{
              const prev = btn.textContent;
              btn.textContent = "Copied!";
              setTimeout(function () {{ btn.textContent = prev; }}, 1200);
            }}
          }});
        }}
      }}

      function renderAll() {{
        const routing = state.routing;
        const stats = state.stats;
        const history = state.history;
        const metrics = (stats && stats.metrics) || (routing && routing.stats) || {{}};
        const repo = routing.repository || "maximusmaximus/agentic-model-matrix";
        const pagesUrl = (routing.pages_url || "{html.escape(pages_url)}").replace(/\\/+$/, "") + "/";

        const pillUpdated = document.getElementById("pill-updated");
        if (pillUpdated) {{
          pillUpdated.textContent = "Updated " + routing.generated_at + " (" + relativeTime(routing.generated_at) + ")";
        }}

        // KPI Grid
        const healthy = metrics.sources_healthy != null ? metrics.sources_healthy : 0;
        const totalSrc = metrics.sources_total != null ? metrics.sources_total : (routing.evaluation_sources || []).length;
        const healthPct = totalSrc > 0 ? Math.round((healthy / totalSrc) * 100) : 0;
        const avgLat = metrics.avg_source_latency_ms != null ? Math.round(metrics.avg_source_latency_ms) + " ms" : "n/a";
        const lastRun = (stats && stats.last_update) || {{}};

        const kpis = [
          {{
            label: "Last Updated",
            value: relativeTime(routing.generated_at),
            sub: routing.generated_at + " · " + (lastRun.trigger || "ci")
          }},
          {{
            label: "Source Health",
            value: healthy + " / " + totalSrc + " (" + healthPct + "%)",
            sub: "Avg probe latency: " + avgLat
          }},
          {{
            label: "Routing Coverage",
            value: (metrics.stages_count || routing.stages.length) + " Stages",
            sub: (metrics.unique_models_count || 0) + " unique models · " + (metrics.total_fallback_slots || 0) + " fallback slots"
          }},
          {{
            label: "CI Update History",
            value: (metrics.total_recorded_runs || (history.runs || []).length) + " Runs",
            sub: (metrics.total_routing_changes || 0) + " routing diff(s) tracked"
          }},
          {{
            label: "Stage 5 Compliance",
            value: "LOCKED · Gemini",
            sub: "Antigravity only · " + ((routing.stages.find(function (s) {{ return s.id === "app_build"; }}) || {{ fallback_chain: [] }}).fallback_chain.length) + " Gemini tiers"
          }}
        ];
        document.getElementById("kpi-grid").innerHTML = kpis.map(function (k) {{
          return '<div class="kpi"><div class="kpi-label">' + esc(k.label) + '</div><div class="kpi-value">' + esc(k.value) + '</div><div class="kpi-sub">' + esc(k.sub) + '</div></div>';
        }}).join("");

        // Stages
        const q = state.query.trim().toLowerCase();
        const filteredStages = (routing.stages || []).filter(function (s) {{
          if (state.filter === "gemini" && s.primary_model.toLowerCase().indexOf("gemini") === -1) return false;
          if (state.filter === "claude" && s.primary_model.toLowerCase().indexOf("claude") === -1) return false;
          if (state.filter === "plan" && s.cli_mode !== "plan") return false;
          if (state.filter === "accept-edits" && s.cli_mode !== "accept-edits") return false;
          if (q) {{
            const hay = JSON.stringify(s).toLowerCase();
            if (hay.indexOf(q) === -1) return false;
          }}
          return true;
        }});

        const stageGrid = document.getElementById("stage-grid");
        if (filteredStages.length === 0) {{
          stageGrid.innerHTML = '<div class="panel">No stages match your filter.</div>';
        }} else {{
          stageGrid.innerHTML = filteredStages.map(function (s) {{
            const isAppBuild = s.id === "app_build";
            const cliCmd = "agy -p --model " + s.primary_model + " --effort " + s.effort + " --mode " + s.cli_mode + ' "<task>"';
            const chainHtml = (s.fallback_chain || []).map(function (m, idx) {{
              return (idx > 0 ? '<span class="chain-arrow">→</span>' : '') +
                '<span class="chain-node' + (idx === 0 ? ' primary-node' : '') + '">' + esc(m) + '</span>';
            }}).join("");
            const criteriaHtml = (s.selection_criteria || []).map(function (c) {{
              return "<li>" + esc(c) + "</li>";
            }}).join("");
            const practicesHtml = (s.best_practices || []).map(function (p) {{
              return "<li>" + esc(p) + "</li>";
            }}).join("");
            return '<article class="stage-card' + (isAppBuild ? ' pinned' : '') + '">' +
              '<div class="stage-top">' +
                '<div>' +
                  '<div class="stage-num">STAGE ' + esc(s.order) + ' · ' + esc(s.id) + '</div>' +
                  '<h3 class="stage-title">' + esc(s.title) + '</h3>' +
                '</div>' +
                '<div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end;">' +
                  (isAppBuild ? '<span class="pill emerald">GEMINI LOCKED</span>' : '') +
                  '<span class="pill violet">effort=' + esc(s.effort) + '</span>' +
                  '<span class="pill cyan">' + esc(s.cli_mode) + '</span>' +
                '</div>' +
              '</div>' +
              '<div class="model-box">' +
                '<div class="model-primary">' + esc(s.primary_model) + '</div>' +
                '<div class="chain">' + chainHtml + '</div>' +
              '</div>' +
              '<div class="stage-lists">' +
                '<h4>Selection Criteria</h4><ul>' + criteriaHtml + '</ul>' +
                '<h4>Best Practices</h4><ul>' + practicesHtml + '</ul>' +
              '</div>' +
              '<div class="cmd-row">' +
                '<code class="cmd-code">' + esc(cliCmd) + '</code>' +
                '<button class="copy-btn" data-copy="' + esc(cliCmd) + '">Copy</button>' +
              '</div>' +
            '</article>';
          }}).join("");
        }}

        // Latest Changes
        const runs = (history && history.runs) || [];
        const latest = runs.length > 0 ? runs[0] : null;
        const changes = (latest && latest.changes) || routing.changes_since_previous || [];
        const latestEl = document.getElementById("latest-changes");
        if (latest) {{
          latestEl.innerHTML =
            '<div class="pill-row">' +
              '<span class="pill cyan">' + esc(latest.week_id) + '</span>' +
              '<span class="pill">' + esc(latest.timestamp) + '</span>' +
              '<span class="pill violet">' + esc(latest.trigger || "ci") + '</span>' +
              '<span class="pill">hash ' + esc((latest.content_hash || "").slice(0, 12)) + '</span>' +
            '</div>' +
            '<ul class="change-list">' +
              (changes.length ? changes.map(function (c) {{ return "<li>" + esc(c) + "</li>"; }}).join("") : "<li>Initial matrix baseline recorded.</li>") +
            '</ul>';
        }} else {{
          latestEl.innerHTML = '<p class="section-sub">No update history recorded yet.</p>';
        }}

        // Model Distribution
        const dist = (stats && stats.model_distribution) || {{}};
        const familySlots = dist.family_slot_counts || {{}};
        const totalSlots = Object.values(familySlots).reduce(function (a, b) {{ return a + b; }}, 0) || 1;
        const primaryCounts = dist.primary_models || {{}};
        const distRows = Object.keys(familySlots).sort(function (a, b) {{ return familySlots[b] - familySlots[a]; }}).map(function (fam) {{
          const count = familySlots[fam];
          const pct = Math.round((count / totalSlots) * 100);
          return '<div class="bar-row">' +
            '<div class="bar-meta"><span>' + esc(fam) + ' (all fallback slots)</span><span>' + count + ' / ' + totalSlots + ' (' + pct + '%)</span></div>' +
            '<div class="bar-track"><div class="bar-fill' + (fam === "gemini" ? " emerald" : "") + '" style="width:' + pct + '%"></div></div>' +
          '</div>';
        }}).join("");
        const primaryRows = Object.keys(primaryCounts).sort(function (a, b) {{ return primaryCounts[b] - primaryCounts[a]; }}).map(function (m) {{
          const count = primaryCounts[m];
          const pct = Math.round((count / (routing.stages.length || 1)) * 100);
          return '<div class="bar-row">' +
            '<div class="bar-meta"><span>Primary: ' + esc(m) + '</span><span>' + count + ' stage(s)</span></div>' +
            '<div class="bar-track"><div class="bar-fill" style="width:' + pct + '%"></div></div>' +
          '</div>';
        }}).join("");
        document.getElementById("model-distribution").innerHTML = distRows + '<div style="height:10px"></div>' + primaryRows;

        // Sources Health Table
        const sources = routing.evaluation_sources || [];
        document.getElementById("sources-tbody").innerHTML = sources.map(function (src) {{
          const isOk = src.healthy === true || String(src.status || "").indexOf("http_2") === 0;
          const isCfg = src.status === "configured";
          const pillCls = isOk ? "emerald" : (isCfg ? "amber" : "rose");
          const lat = src.latency_ms != null ? Math.round(src.latency_ms) + " ms" : "—";
          const lm = src.last_modified ? esc(src.last_modified) : '<span style="color:var(--text-dim)">not reported</span>';
          return '<tr>' +
            '<td><a href="' + esc(src.url) + '" target="_blank" rel="noopener"><code>' + esc(src.id) + '</code></a><div style="font-size:11.5px;color:var(--text-dim)">' + esc(src.kind) + '</div></td>' +
            '<td><span class="pill ' + pillCls + '">' + esc(src.status) + '</span></td>' +
            '<td style="font-family:var(--mono);white-space:nowrap;">' + esc(lat) + '</td>' +
            '<td style="font-family:var(--mono);font-size:11.5px;">' + lm + '</td>' +
          '</tr>';
        }}).join("");

        // History Timeline Table
        document.getElementById("history-tbody").innerHTML = runs.slice(0, 12).map(function (r) {{
          const firstChange = (r.changes && r.changes.length) ? r.changes[0] : "Matrix refreshed";
          const extra = (r.changes && r.changes.length > 1) ? " (+" + (r.changes.length - 1) + " more)" : "";
          const healthTxt = (r.sources_healthy != null && r.sources_total != null)
            ? (r.sources_healthy + "/" + r.sources_total)
            : "—";
          return '<tr>' +
            '<td style="font-family:var(--mono);font-size:12px;white-space:nowrap;">' + esc(r.timestamp) + '</td>' +
            '<td><code>' + esc(r.week_id) + '</code><div style="font-size:11px;color:var(--text-dim)">' + esc(r.trigger || "ci") + '</div></td>' +
            '<td><span class="pill emerald">' + esc(healthTxt) + '</span></td>' +
            '<td style="font-size:12.5px;color:var(--text-muted)">' + esc(firstChange + extra) + '</td>' +
          '</tr>';
        }}).join("");

        // Endpoints List
        const endpoints = [
          {{ label: "Routing Matrix (JSON)", url: pagesUrl + "routing.json" }},
          {{ label: "Live Stats & Health (JSON)", url: pagesUrl + "stats.json" }},
          {{ label: "Update History (JSON)", url: pagesUrl + "history.json" }},
          {{ label: "JSON Schema Contract", url: pagesUrl + "schema/routing.schema.json" }},
          {{ label: "Agent Discovery (llms.txt)", url: pagesUrl + "llms.txt" }},
          {{ label: "Engineering Playbook (MD)", url: pagesUrl + "BEST_PRACTICES.md" }},
          {{ label: "Raw GitHub Routing JSON", url: "https://raw.githubusercontent.com/" + repo + "/main/routing.json" }}
        ];
        document.getElementById("endpoints-list").innerHTML = endpoints.map(function (ep) {{
          return '<div class="endpoint-row">' +
            '<div><div style="font-weight:600">' + esc(ep.label) + '</div><a style="font-family:var(--mono);font-size:11.5px;word-break:break-all" href="' + esc(ep.url) + '" target="_blank" rel="noopener">' + esc(ep.url) + '</a></div>' +
            '<button class="copy-btn" data-copy="' + esc(ep.url) + '">Copy</button>' +
          '</div>';
        }}).join("");

        renderSnippet(pagesUrl, repo);

        // Bind copy buttons
        document.querySelectorAll("[data-copy]").forEach(function (btn) {{
          btn.onclick = function () {{
            copyText(btn.getAttribute("data-copy"), btn);
          }};
        }});
      }}

      function renderSnippet(pagesUrl, repo) {{
        const snippets = {{
          curl: [
            'curl -sS "' + pagesUrl + 'routing.json" | jq \\\\',
            '  \\x27.stages[] | select(.id == "app_build") | {{primary: .primary_model, fallbacks: .fallback_chain, effort, cli_mode}}\\x27'
          ].join("\\n"),
          python: [
            'import json, urllib.request',
            '',
            'URL = "' + pagesUrl + 'routing.json"',
            'with urllib.request.urlopen(URL, timeout=10) as r:',
            '    matrix = json.load(r)',
            '',
            'app_build = next(s for s in matrix["stages"] if s["id"] == "app_build")',
            'assert app_build["primary_provider"] == "antigravity"',
            'assert all("gemini" in m.lower() for m in app_build["fallback_chain"])',
            'print("Stage 5 chain:", app_build["fallback_chain"])'
          ].join("\\n"),
          submodule: [
            'git submodule add https://github.com/' + repo + '.git modules/model-matrix',
            'git submodule update --init --remote modules/model-matrix'
          ].join("\\n"),
          agent: [
            'Fetch ' + pagesUrl + 'llms.txt first, then load ' + pagesUrl + 'routing.json.',
            'Select the model and fallback_chain for your current SDLC stage.',
            'Hard rule: Stage 5 (app_build) MUST only use Gemini models on Antigravity.'
          ].join("\\n")
        }};
        const code = snippets[state.activeTab] || snippets.curl;
        document.getElementById("snippet-code").textContent = code;
        document.getElementById("copy-snippet-btn").onclick = function () {{
          copyText(code, this);
        }};
      }}

      // Filter controls
      document.querySelectorAll("[data-filter]").forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          document.querySelectorAll("[data-filter]").forEach(function (b) {{ b.classList.remove("active"); }});
          btn.classList.add("active");
          state.filter = btn.getAttribute("data-filter");
          renderAll();
        }});
      }});
      document.getElementById("stage-search").addEventListener("input", function (e) {{
        state.query = e.target.value;
        renderAll();
      }});
      document.querySelectorAll("[data-tab]").forEach(function (btn) {{
        btn.addEventListener("click", function () {{
          document.querySelectorAll("[data-tab]").forEach(function (b) {{ b.classList.remove("active"); }});
          btn.classList.add("active");
          state.activeTab = btn.getAttribute("data-tab");
          renderAll();
        }});
      }});

      renderAll();

      // Progressive live refresh when served over HTTP(S)
      if (window.location.protocol === "http:" || window.location.protocol === "https:") {{
        Promise.all([
          fetch("./routing.json", {{ cache: "no-store" }}).then(function (r) {{ return r.ok ? r.json() : null; }}),
          fetch("./stats.json", {{ cache: "no-store" }}).then(function (r) {{ return r.ok ? r.json() : null; }}),
          fetch("./history.json", {{ cache: "no-store" }}).then(function (r) {{ return r.ok ? r.json() : null; }})
        ]).then(function (res) {{
          if (res[0]) state.routing = res[0];
          if (res[1]) state.stats = res[1];
          if (res[2]) state.history = res[2];
          renderAll();
        }}).catch(function () {{ /* Keep embedded snapshot on offline load */ }});
      }}
    }})();
  </script>
</body>
</html>
"""


def _write_lf(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def build_site(root: Path) -> Path:
    root = root.resolve()
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "schema").mkdir(parents=True, exist_ok=True)

    routing = json.loads((root / "routing.json").read_text(encoding="utf-8"))
    stats = json.loads((root / "stats.json").read_text(encoding="utf-8"))
    history = json.loads((root / "history.json").read_text(encoding="utf-8"))

    # Disable Jekyll processing on GitHub Pages
    _write_lf(docs_dir / ".nojekyll", "")

    # Mirror machine-readable and markdown artifacts into docs/
    for rel in MIRROR_FILES:
        src = root / rel
        if src.exists():
            dst = docs_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)

    # Render interactive static dashboard
    index_html = render_index_html(routing, stats, history)
    index_path = docs_dir / "index.html"
    _write_lf(index_path, index_html)
    return docs_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build static GitHub Pages dashboard & API in docs/.")
    parser.add_argument("--root", default=".", help="Repository root directory")
    args = parser.parse_args()
    docs_dir = build_site(Path(args.root))
    print(f"SITE BUILT: {docs_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
