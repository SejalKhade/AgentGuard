"""
AgentGuard Dashboard
Professional, no emojis, full transparency on every calculation.
"""

import streamlit as st
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="AgentGuard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background: #0a0a0a;
    color: #d4d4d4;
}
.main .block-container { padding: 1.5rem 2rem; max-width: 1400px; }
h1,h2,h3,h4 { font-weight: 600; letter-spacing: -0.01em; }

.ag-header {
    border-bottom: 1px solid #1e1e1e;
    padding-bottom: 1.25rem;
    margin-bottom: 1.75rem;
}
.ag-title {
    font-size: 1.4rem;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.02em;
    font-family: 'IBM Plex Sans', sans-serif;
}
.ag-sub {
    font-size: 0.78rem;
    color: #555;
    font-family: 'IBM Plex Mono', monospace;
    margin-top: 0.2rem;
}

.metric-card {
    background: #111;
    border: 1px solid #1e1e1e;
    border-radius: 4px;
    padding: 1rem 1.25rem;
}
.metric-label {
    font-size: 0.68rem;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    margin-bottom: 0.3rem;
}
.metric-value {
    font-size: 1.8rem;
    font-weight: 700;
    font-family: 'IBM Plex Mono', monospace;
    color: #fff;
}
.metric-sub { font-size: 0.72rem; color: #444; margin-top: 0.2rem; }

.section-header {
    font-size: 0.7rem;
    font-family: 'IBM Plex Mono', monospace;
    color: #444;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 0.75rem 1rem;
    background: #111;
    border: 1px solid #1e1e1e;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-top: 1.5rem;
}
.section-body {
    background: #0d0d0d;
    border: 1px solid #1e1e1e;
    border-radius: 0 0 4px 4px;
    padding: 1.25rem;
    margin-bottom: 0.5rem;
}

.formula-box {
    background: #080808;
    border: 1px solid #1a1a1a;
    border-left: 2px solid #2a2a2a;
    border-radius: 3px;
    padding: 0.6rem 0.9rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.74rem;
    color: #666;
    margin: 0.6rem 0;
    white-space: pre-wrap;
}

.blast-0 { color: #4ade80; }
.blast-1 { color: #a3e635; }
.blast-2 { color: #fb923c; }
.blast-3 { color: #ef4444; }

.status-auto  { background:#0f2b1a;color:#4ade80;padding:.15rem .5rem;border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:.68rem;font-weight:600; }
.status-pend  { background:#2b1e0a;color:#fb923c;padding:.15rem .5rem;border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:.68rem;font-weight:600; }
.status-block { background:#2b0a0a;color:#ef4444;padding:.15rem .5rem;border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:.68rem;font-weight:600; }
.status-appv  { background:#0f1a2b;color:#60a5fa;padding:.15rem .5rem;border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:.68rem;font-weight:600; }

.action-table { width:100%;border-collapse:collapse;font-size:.82rem; }
.action-table th { text-align:left;padding:.5rem .75rem;background:#161616;color:#555;font-weight:500;font-size:.68rem;text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid #1e1e1e; }
.action-table td { padding:.55rem .75rem;border-bottom:1px solid #111;color:#bbb;vertical-align:top; }
.action-table tr:last-child td { border-bottom:none; }

.bar-outer { height:5px;background:#1a1a1a;border-radius:3px;width:120px;overflow:hidden; }
.bar-inner { height:100%;border-radius:3px; }

.guard-verified   { background:#0f2b1a;color:#4ade80;padding:.12rem .45rem;border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:.65rem;font-weight:600; }
.guard-approx     { background:#1e1a0a;color:#fbbf24;padding:.12rem .45rem;border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:.65rem;font-weight:600; }
.guard-unverified { background:#2b0a0a;color:#f87171;padding:.12rem .45rem;border-radius:3px;font-family:'IBM Plex Mono',monospace;font-size:.65rem;font-weight:600; }

.claude-box {
    background:#040f0a;
    border:1px solid #0f2b1a;
    border-left:2px solid #166534;
    border-radius:3px;
    padding:1rem 1.25rem;
    font-size:.82rem;
    color:#aaa;
    line-height:1.75;
    white-space:pre-wrap;
}
#MainMenu,footer,header{visibility:hidden;}
.stDeployButton{display:none;}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="font-size:.68rem;color:#444;text-transform:uppercase;letter-spacing:.1em;font-weight:600;margin-bottom:.75rem;font-family:\'IBM Plex Mono\',monospace">Configuration</div>', unsafe_allow_html=True)

    pipeline_choice = st.radio(
        "Pipeline",
        ["Direct Pipeline (No LLM)", "Claude-Augmented Pipeline"],
        help="Direct is fully deterministic. Claude pipeline adds interpretation."
    )

    anthropic_key = None
    if pipeline_choice == "Claude-Augmented Pipeline":
        st.markdown('<div style="font-size:.68rem;color:#444;text-transform:uppercase;letter-spacing:.1em;font-weight:600;margin:.75rem 0 .4rem;font-family:\'IBM Plex Mono\',monospace">Anthropic API Key</div>', unsafe_allow_html=True)
        anthropic_key = st.text_input(
            "API Key",
            type="password",
            placeholder="sk-ant-...",
            help="Used this session only. Never stored to disk."
        )
        if anthropic_key:
            st.markdown('<div style="font-size:.72rem;color:#4ade80;margin-top:.3rem">Key received. Not stored.</div>', unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#1a1a1a;margin:.75rem 0'>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:.68rem;color:#444;text-transform:uppercase;letter-spacing:.1em;font-weight:600;margin-bottom:.5rem;font-family:\'IBM Plex Mono\',monospace">Action Input</div>', unsafe_allow_html=True)

    input_mode = st.radio("Input mode", ["Sample actions (6 pre-loaded)", "Custom JSON"])

    custom_json = None
    if input_mode == "Custom JSON":
        custom_json = st.text_area(
            "Action JSON",
            height=200,
            placeholder='[{"name":"delete_table","target":"prod-db","agent_id":"my-agent","parameters":{}}]'
        )

    st.markdown("<hr style='border-color:#1a1a1a;margin:.75rem 0'>", unsafe_allow_html=True)
    run_btn = st.button("Run Pipeline", use_container_width=True, type="primary")

    st.markdown("<hr style='border-color:#1a1a1a;margin:.75rem 0'>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:.72rem;color:#333;line-height:1.6;font-family:'IBM Plex Mono',monospace">
    AgentGuard<br>
    Built by Sejal Khade<br>
    github.com/SejalKhade<br><br>
    Addresses the Dec 2025<br>
    AWS Kiro incident.
    </div>
    """, unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ag-header">
    <div class="ag-title">AgentGuard</div>
    <div class="ag-sub">Pre-Execution Risk Scorer for Agentic AI Actions &nbsp;/&nbsp; Blast Radius Classification &nbsp;/&nbsp; Human-in-Loop Enforcement</div>
</div>
""", unsafe_allow_html=True)


# ── Run pipeline ───────────────────────────────────────────────────────────────
if run_btn:
    from modules.audit_logger import AuditLogger
    AuditLogger.reset()

    try:
        if input_mode == "Sample actions (6 pre-loaded)":
            with open("data/sample_actions.json") as f:
                actions_input = json.load(f)
        else:
            if not custom_json:
                st.error("Paste valid JSON in the action input field.")
                st.stop()
            actions_input = json.loads(custom_json)

        with st.spinner("Running pipeline..."):
            if pipeline_choice == "Direct Pipeline (No LLM)":
                import pipeline_direct
                result = pipeline_direct.run(actions_input)
                claude_data = None
            else:
                if not anthropic_key:
                    st.error("Anthropic API key required for Claude pipeline.")
                    st.stop()
                import pipeline_claude
                full = pipeline_claude.run(actions_input, anthropic_key)
                result = full["direct_output"]
                claude_data = full

        st.session_state["result"] = result
        st.session_state["claude_data"] = claude_data
        st.session_state["pipeline"] = pipeline_choice

    except json.JSONDecodeError as e:
        st.error(f"JSON parse error: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Pipeline error: {e}")
        st.stop()


# ── Display ────────────────────────────────────────────────────────────────────
if "result" not in st.session_state:
    st.markdown("""
    <div style="text-align:center;padding:5rem 2rem;color:#222">
        <div style="font-size:1rem;font-weight:600;color:#333;margin-bottom:.6rem">
            Configure pipeline in the sidebar and click Run Pipeline
        </div>
        <div style="font-size:.78rem;color:#2a2a2a;line-height:1.7">
            AgentGuard intercepts agentic AI actions before execution, classifies them by blast radius,<br>
            and enforces human approval gates only on destructive and catastrophic operations.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


result     = st.session_state["result"]
claude_data = st.session_state.get("claude_data")
summary    = result["audit_summary"]
results    = result["results"]


# ── KPI Row ────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Actions</div>
        <div class="metric-value">{summary['total_actions']}</div>
        <div class="metric-sub">Intercepted this run</div>
    </div>""", unsafe_allow_html=True)

with c2:
    blocked = summary['blocked_or_pending']
    color = "#ef4444" if blocked > 0 else "#4ade80"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Blocked / Pending</div>
        <div class="metric-value" style="color:{color}">{blocked}</div>
        <div class="metric-sub">Require human approval</div>
    </div>""", unsafe_allow_html=True)

with c3:
    cat = summary['catastrophic_count']
    color = "#ef4444" if cat > 0 else "#4ade80"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Catastrophic</div>
        <div class="metric-value" style="color:{color}">{cat}</div>
        <div class="metric-sub">Kiro-pattern actions</div>
    </div>""", unsafe_allow_html=True)

with c4:
    rate = summary['block_rate_pct']
    color = "#fb923c" if rate > 0 else "#4ade80"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Block Rate</div>
        <div class="metric-value" style="color:{color}">{rate}%</div>
        <div class="metric-sub">Of all intercepted actions</div>
    </div>""", unsafe_allow_html=True)


# ── Formula Box ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="section-header">RISK SCORING FORMULA — FULL TRANSPARENCY</div>
<div class="section-body">
""", unsafe_allow_html=True)

st.markdown("""
<div class="formula-box">BLAST RADIUS = max(prefix_score, target_score, scope_score)
RISK SCORE   = (blast_radius / 3) * 100

PREFIX SCORE : Trie lookup on action name prefix — O(k) where k = prefix length
               get_/list_/describe_ = 0  |  update_/modify_/create_ = 1
               delete_/terminate_   = 2  |  recreate_/delete_all    = 3

TARGET SCORE : dev/test/sandbox = 0  |  staging/uat = 1
               prod/live/prd    = 2  |  global/all-regions = 3

SCOPE SCORE  : Regex match on parameters JSON
               'all', 'cascade', 'recursive', 'force' keywords escalate risk

GATE RULE    : gate_required if blast_radius >= 2 (DESTRUCTIVE or CATASTROPHIC)
               DESTRUCTIVE  = 1 approver required
               CATASTROPHIC = 2 approvers required (Senior + Peer)</div>
""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)


# ── Action Results Table ───────────────────────────────────────────────────────
st.markdown('<div class="section-header">ACTION-BY-ACTION CLASSIFICATION</div><div class="section-body">', unsafe_allow_html=True)

blast_colors = {0: "#4ade80", 1: "#a3e635", 2: "#fb923c", 3: "#ef4444"}

rows_html = ""
for r in results:
    c    = r["classification"]
    g    = r["gate"]
    br   = c["blast_radius"]
    col  = blast_colors.get(br, "#fff")
    bar  = int(c["risk_score"] * 1.2)

    status_html = {
        "AUTO_APPROVED": '<span class="status-auto">AUTO APPROVED</span>',
        "PENDING":       '<span class="status-pend">PENDING APPROVAL</span>',
        "BLOCKED":       '<span class="status-block">BLOCKED</span>',
        "APPROVED":      '<span class="status-appv">APPROVED</span>',
    }.get(g["status"], g["status"])

    rows_html += f"""
    <tr>
        <td style="font-family:'IBM Plex Mono',monospace;font-size:.75rem;color:#888">{r['action']['agent_id']}</td>
        <td style="font-weight:500;color:#ccc">{r['action']['name']}</td>
        <td style="color:#666;font-size:.78rem">{r['action']['target']}</td>
        <td style="color:{col};font-family:'IBM Plex Mono',monospace;font-weight:600">{c['blast_label']}</td>
        <td>
            <div style="display:flex;align-items:center;gap:.5rem">
                <div class="bar-outer"><div class="bar-inner" style="width:{bar}px;background:{col}"></div></div>
                <span style="color:{col};font-family:'IBM Plex Mono',monospace;font-size:.75rem">{c['risk_score']}</span>
            </div>
        </td>
        <td>{status_html}</td>
        <td style="font-size:.72rem;color:#555">{' + '.join(c.get('dominant_factors') or [c['dominant_factor']])}</td>
    </tr>"""

st.markdown(f"""
<table class="action-table">
<thead><tr>
    <th>Agent</th><th>Action</th><th>Target</th><th>Blast Radius</th><th>Risk Score</th><th>Gate</th><th>Top Factor</th>
</tr></thead>
<tbody>{rows_html}</tbody>
</table>""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)


# ── Per-Action Audit Trails ────────────────────────────────────────────────────
st.markdown('<div class="section-header">CALCULATION AUDIT TRAILS</div><div class="section-body">', unsafe_allow_html=True)

for r in results:
    c  = r["classification"]
    br = c["blast_radius"]
    col = blast_colors.get(br, "#fff")

    with st.expander(f"{r['action']['name']}  —  {c['blast_label']}  —  Score: {c['risk_score']}"):
        calc = c["calculation"]
        st.markdown(f"""
        **Action:** `{r['action']['name']}` on `{r['action']['target']}`

        | Component | Input | Score | Weight | Source |
        |---|---|---|---|---|
        | Prefix | `{calc['prefix']['normalized']}` | {calc['prefix']['score']} | 0.33 | Trie lookup — risk_scorer.py PREFIX_SCORES |
        | Target | `{calc['target']['matched_keyword']}` | {calc['target']['score']} | 0.33 | TARGET_SCORES table |
        | Scope | {calc['scope']['matched_pattern']} | {calc['scope']['score']} | 0.33 | Regex pattern match on parameters |
        | **Blast Radius** | max(above) | **{c['blast_radius']}** | | |
        | **Risk Score** | ({c['blast_radius']} / 3) x 100 | **{c['risk_score']}** | | |

        **Gate decision:** {r['gate']['status']}
        **Approvers needed:** {r['gate']['approvers_needed']}
        **Recommendation:** {c['recommendation']}

        **Gate reason:** {r['gate']['reason']}
        """)

st.markdown("</div>", unsafe_allow_html=True)


# ── Claude Section ─────────────────────────────────────────────────────────────
if claude_data and claude_data.get("claude", {}).get("success"):
    cl = claude_data["claude"]
    guard = claude_data.get("hallucination_guard", {})

    model_id = cl.get("model", "claude")
    st.markdown(f'<div class="section-header">CLAUDE INTERPRETATION — {model_id}</div><div class="section-body">', unsafe_allow_html=True)

    st.markdown(f'<div class="claude-box">{cl["text"]}</div>', unsafe_allow_html=True)

    if guard.get("evaluation_performed"):
        st.markdown("<hr style='border-color:#0f2b1a;margin:1rem 0'>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:.68rem;color:#444;text-transform:uppercase;letter-spacing:.1em;font-family:\'IBM Plex Mono\',monospace;margin-bottom:.75rem">Hallucination Guard — Claim Verification</div>', unsafe_allow_html=True)

        rel = guard["reliability_score"]
        status = guard["overall_status"]
        scol = "#4ade80" if status == "RELIABLE" else "#fbbf24" if "PARTIAL" in status else "#ef4444"

        g1, g2, g3, g4 = st.columns(4)
        with g1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Reliability</div><div class="metric-value" style="font-size:1.5rem;color:{scol}">{rel}%</div><div class="metric-sub">{status}</div></div>', unsafe_allow_html=True)
        with g2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Verified</div><div class="metric-value" style="color:#4ade80;font-size:1.5rem">{guard["verified"]}</div><div class="metric-sub">In source data</div></div>', unsafe_allow_html=True)
        with g3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Approximations</div><div class="metric-value" style="color:#fbbf24;font-size:1.5rem">{guard["approximations"]}</div><div class="metric-sub">Within 15%</div></div>', unsafe_allow_html=True)
        with g4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">Unverified</div><div class="metric-value" style="color:#ef4444;font-size:1.5rem">{guard["unverified"]}</div><div class="metric-sub">Not in source</div></div>', unsafe_allow_html=True)

        claims = guard.get("claim_results", [])
        if claims:
            with st.expander(f"Claim verification table ({len(claims)} claims)"):
                rows = ""
                for cl_r in claims:
                    v = cl_r["verification"]
                    s = v["status"]
                    badge = (
                        f'<span class="guard-verified">{s}</span>' if s == "VERIFIED" else
                        f'<span class="guard-unverified">{s}</span>' if s == "UNVERIFIED" else
                        f'<span class="guard-approx">{s}</span>'
                    )
                    rows += f"""<tr>
                        <td style="font-family:'IBM Plex Mono',monospace;color:#888">{cl_r['claimed_number']}{cl_r['unit']}</td>
                        <td style="font-size:.72rem;color:#555">{cl_r['context'][:80]}</td>
                        <td>{badge}</td>
                        <td style="font-family:'IBM Plex Mono',monospace;font-size:.7rem;color:#444">{v.get('matched_value','—')}</td>
                        <td style="font-size:.7rem;color:#333">{v.get('source_path','—')}</td>
                    </tr>"""

                st.markdown(f"""
                <table class="action-table">
                <thead><tr><th>Claimed</th><th>Context</th><th>Status</th><th>Source Value</th><th>Source Path</th></tr></thead>
                <tbody>{rows}</tbody></table>
                """, unsafe_allow_html=True)

        st.markdown(f'<div style="margin-top:.75rem;font-size:.7rem;color:#333;font-family:\'IBM Plex Mono\',monospace">{guard["methodology"]}</div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

elif claude_data and not claude_data.get("claude", {}).get("success"):
    st.error(f"Claude error: {claude_data['claude'].get('error')}")


# ── Raw JSON ───────────────────────────────────────────────────────────────────
with st.expander("Raw pipeline output (JSON)"):
    st.code(json.dumps(result, indent=2, default=str), language="json")
