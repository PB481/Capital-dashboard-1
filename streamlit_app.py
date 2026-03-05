"""
Fund Administration — Client Pricing Model

Interactive Streamlit application for modelling fund administration fees,
negotiation scenarios, and portfolio-level economics.

Requirements:
pip install streamlit plotly pandas numpy

Run:
streamlit run fund_admin_pricing_app.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import json

# ──────────────────────────────────────────────────────────────────────
# PAGE CONFIG & THEME
# ──────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="FA Pricing Model",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark financial theme colours
THEME = {
    "bg": "#0a0e17",
    "card": "#111827",
    "border": "#1e293b",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "dim": "#64748b",
    "accent": "#3b82f6",
    "green": "#10b981",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "purple": "#8b5cf6",
    "cyan": "#06b6d4",
    "chart_palette": [
        "#3b82f6", "#8b5cf6", "#06b6d4", "#10b981",
        "#f59e0b", "#ef4444", "#ec4899",
    ],
}

# Inject custom CSS for dark styling
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background-color: #0a0e17;
        color: #e2e8f0;
    }
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #1e293b;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] label {
        color: #94a3b8 !important;
    }
    /* Metric cards */
    [data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
    }
    [data-testid="stMetricLabel"] p {
        color: #64748b !important;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-size: 0.72rem !important;
        font-weight: 600;
    }
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
    }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #111827;
        border-radius: 10px;
        padding: 4px;
        border: 1px solid #1e293b;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #94a3b8;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: #3b82f6 !important;
        color: white !important;
    }
    /* Tables */
    .stDataFrame {
        border: 1px solid #1e293b;
        border-radius: 10px;
    }
    /* Expander */
    .streamlit-expanderHeader {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 8px;
    }
    /* Selectbox / inputs */
    .stSelectbox > div > div,
    .stMultiSelect > div > div,
    .stNumberInput > div > div > input {
        background: #111827 !important;
        border-color: #1e293b !important;
        color: #e2e8f0 !important;
    }
    /* Narrative info boxes */
    .narrative-box {
        background: linear-gradient(135deg, #111827 0%, #0f1629 100%);
        border: 1px solid #1e293b;
        border-left: 3px solid #3b82f6;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 12px 0;
        font-size: 0.88rem;
        line-height: 1.7;
        color: #94a3b8;
    }
    .narrative-box strong {
        color: #e2e8f0;
    }
    /* Section headers */
    .section-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #e2e8f0;
        margin: 24px 0 12px;
        letter-spacing: 0.3px;
    }
    /* Scenario cards */
    .scenario-card {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 18px;
        text-align: center;
    }
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>

<link href="[https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap](https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap)" rel="stylesheet">
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# DATA MODELS
# ──────────────────────────────────────────────────────────────────────

FUND_TYPES = {
    "UCITS Equity":        {"complexity": 1.00, "base_aum": 500},
    "UCITS Fixed Income":  {"complexity": 1.15, "base_aum": 750},
    "UCITS Money Market":  {"complexity": 0.85, "base_aum": 1000},
    "UCITS Multi-Asset":   {"complexity": 1.30, "base_aum": 400},
    "UCITS ETF":           {"complexity": 1.25, "base_aum": 600},
    "AIF Private Equity":  {"complexity": 1.60, "base_aum": 200},
    "AIF Real Estate":     {"complexity": 1.50, "base_aum": 300},
    "AIF Hedge Fund":      {"complexity": 1.75, "base_aum": 250},
    "AIF Infrastructure":  {"complexity": 1.55, "base_aum": 350},
}

SERVICE_MODULES = {
    "NAV Calculation":       {"bps": 1.5, "required": True,  "desc": "Daily/weekly NAV production, pricing, P&L"},
    "Transfer Agency":       {"bps": 1.0, "required": False, "desc": "Investor servicing, subscriptions, redemptions"},
    "Regulatory Compliance": {"bps": 0.8, "required": True,  "desc": "UCITS/AIFMD limits, CBI reporting, EMIR"},
    "Client Reporting":      {"bps": 0.6, "required": False, "desc": "Factsheets, investor comms, board packs"},
    "Tax Services":          {"bps": 0.5, "required": False, "desc": "WHT reclaims, tax reporting, FATCA/CRS"},
    "Depositary Lite":       {"bps": 0.4, "required": False, "desc": "Cashflow monitoring, asset verification"},
    "Risk Analytics":        {"bps": 0.7, "required": False, "desc": "VaR, stress testing, liquidity monitoring"},
    "ESG / SFDR Reporting":  {"bps": 0.55,"required": False, "desc": "SFDR Art 8/9, PAI indicators, taxonomy"},
}

VOLUME_TIERS = [
    (0,     500,    0.00),
    (500,   2000,   0.08),
    (2000,  5000,   0.15),
    (5000,  15000,  0.22),
    (15000, 1e9,    0.30),
]

NEGOTIATION_SCENARIOS = {
    "Standard":         {"discount": 0.00, "color": THEME["accent"], "desc": "Rack rate — full pricing with volume discounts only"},
    "Competitive Bid":  {"discount": 0.12, "color": THEME["amber"],  "desc": "2–3 administrators shortlisted; typical 12% reduction"},
    "Strategic Win":    {"discount": 0.20, "color": THEME["purple"], "desc": "Anchor mandate / marquee client; 20% reduction"},
    "Retention":        {"discount": 0.25, "color": THEME["red"],    "desc": "At-risk relationship; defensive posture — use sparingly"},
}

NAV_FREQ_MULTIPLIER = {"Daily": 1.0, "Weekly": 0.85, "Monthly": 0.70}

# ──────────────────────────────────────────────────────────────────────
# PRICING ENGINE
# ──────────────────────────────────────────────────────────────────────

def get_volume_discount(aum_mn: float) -> float:
    for lo, hi, disc in VOLUME_TIERS:
        if lo <= aum_mn < hi:
            return disc
    return VOLUME_TIERS[-1][2]

def calculate_pricing(
    fund_type: str,
    aum_mn: float,
    selected_services: List[str],
    scenario: str = "Standard",
    custom_discount_pct: float = 0.0,
    share_classes: int = 3,
    nav_frequency: str = "Daily",
    term_years: int = 3,
) -> dict:
    """Core pricing engine — mirrors the React model exactly."""
    complexity = FUND_TYPES[fund_type]["complexity"]

    # Aggregate base bps from selected services
    total_bps = 0.0
    svc_breakdown = []
    for svc_name in selected_services:
        svc = SERVICE_MODULES[svc_name]
        adj_bps = svc["bps"] * complexity
        total_bps += adj_bps
        svc_breakdown.append({"service": svc_name, "base_bps": svc["bps"], "adjusted_bps": adj_bps})

    # NAV frequency multiplier
    freq_mult = NAV_FREQ_MULTIPLIER.get(nav_frequency, 1.0)
    total_bps *= freq_mult

    # Share class surcharge (first 3 included)
    extra_classes = max(0, share_classes - 3)
    sc_surcharge = extra_classes * 0.08 * complexity
    total_bps += sc_surcharge

    # Discounts
    vol_disc = get_volume_discount(aum_mn)
    nego_disc = NEGOTIATION_SCENARIOS[scenario]["discount"]
    custom_disc = custom_discount_pct / 100.0
    combined_disc = 1 - (1 - vol_disc) * (1 - nego_disc) * (1 - custom_disc)

    # Term commitment discount
    term_disc = 0.05 if term_years >= 5 else 0.03 if term_years >= 3 else 0.0
    final_disc = 1 - (1 - combined_disc) * (1 - term_disc)

    effective_bps = total_bps * (1 - final_disc)

    # Revenue (with minimum floor)
    min_fee_mn = 0.05  # $50K
    raw_revenue = (aum_mn * effective_bps) / 10_000
    annual_revenue = max(raw_revenue, min_fee_mn)
    min_fee_applied = raw_revenue < min_fee_mn

    # Cost estimation
    headcount = max(1, int(np.ceil(aum_mn / 800))) + (1 if complexity > 1.3 else 0) + len(selected_services) // 3
    cost_per_head = 0.085  # $85K
    annual_cost = headcount * cost_per_head

    margin = (annual_revenue - annual_cost) / annual_revenue if annual_revenue > 0 else 0
    contract_value = annual_revenue * term_years

    return {
        "gross_bps": total_bps,
        "effective_bps": effective_bps,
        "annual_revenue_mn": annual_revenue,
        "annual_cost_mn": annual_cost,
        "margin": margin,
        "contract_value_mn": contract_value,
        "headcount": headcount,
        "service_breakdown": svc_breakdown,
        "volume_discount": vol_disc,
        "nego_discount": nego_disc,
        "term_discount": term_disc,
        "final_discount": final_disc,
        "share_class_surcharge": sc_surcharge,
        "min_fee_applied": min_fee_applied,
        "term_years": term_years,
    }

# ──────────────────────────────────────────────────────────────────────
# FORMATTING HELPERS
# ──────────────────────────────────────────────────────────────────────

def fmt_usd(mn: float) -> str:
    val = mn * 1e6
    if abs(val) >= 1e9:
        return f"${val/1e9:,.2f}B"
    if abs(val) >= 1e6:
        return f"${val/1e6:,.2f}M"
    if abs(val) >= 1e3:
        return f"${val/1e3:,.1f}K"
    return f"${val:,.0f}"

def fmt_bps(bps: float) -> str:
    return f"{bps:.2f} bps"

def fmt_pct(pct: float) -> str:
    return f"{pct*100:.1f}%"

def narrative(text: str):
    st.markdown(f'<div class="narrative-box">{text}</div>', unsafe_allow_html=True)

def section_header(icon: str, title: str):
    st.markdown(f'<div class="section-header">{icon} {title}</div>', unsafe_allow_html=True)

def plotly_dark_layout(fig, height=350):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=THEME["card"],
        plot_bgcolor=THEME["card"],
        font=dict(family="IBM Plex Sans, sans-serif", color=THEME["muted"], size=12),
        margin=dict(l=40, r=20, t=40, b=40),
        height=height,
        legend=dict(font=dict(size=11)),
    )
    fig.update_xaxes(gridcolor=THEME["border"], zerolinecolor=THEME["border"])
    fig.update_yaxes(gridcolor=THEME["border"], zerolinecolor=THEME["border"])
    return fig

# ──────────────────────────────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────────────────────────────

st.markdown("""
<div style="border-bottom: 1px solid #1e293b; padding-bottom: 16px; margin-bottom: 20px;">
    <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
        <div style="width:8px; height:8px; border-radius:50%; background:#10b981; box-shadow:0 0 8px #10b981;"></div>
        <span style="font-size:0.7rem; color:#64748b; text-transform:uppercase; letter-spacing:2px; font-weight:600;">Fund Administration</span>
    </div>
    <h1 style="margin:0 0 4px; font-size:1.7rem; font-weight:700; letter-spacing:-0.5px;">Client Pricing Model</h1>
    <p style="margin:0; font-size:0.85rem; color:#94a3b8;">
        Fee structuring engine for Irish-domiciled UCITS & AIF fund administration mandates
    </p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────
# SIDEBAR — FUND CONFIGURATOR
# ──────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📋 Fund Configuration")

    fund_type = st.selectbox(
        "Fund Type",
        options=list(FUND_TYPES.keys()),
        format_func=lambda x: f"{x}  (×{FUND_TYPES[x]['complexity']:.2f})",
        help="Complexity multiplier adjusts base rates for operational intensity.",
    )

    aum_mn = st.slider(
        "AUM ($M)",
        min_value=50, max_value=25000, value=500, step=50,
        help="Volume discounts apply at $500M, $2B, $5B, and $15B thresholds.",
    )

    col1, col2 = st.columns(2)
    with col1:
        nav_frequency = st.selectbox("NAV Frequency", ["Daily", "Weekly", "Monthly"])
    with col2:
        share_classes = st.number_input("Share Classes", min_value=1, max_value=30, value=3)

    col3, col4 = st.columns(2)
    with col3:
        term_years = st.number_input("Term (Years)", min_value=1, max_value=10, value=3)
    with col4:
        custom_discount = st.number_input("Custom Disc. %", min_value=0.0, max_value=40.0, value=0.0, step=0.5)

    st.markdown("---")
    st.markdown("### 🧩 Service Modules")

    # Required services are always on
    required = [k for k, v in SERVICE_MODULES.items() if v["required"]]
    optional = [k for k, v in SERVICE_MODULES.items() if not v["required"]]

    selected_optional = st.multiselect(
        "Optional Services",
        options=optional,
        default=["Transfer Agency", "Client Reporting"],
        help="Required services (NAV, Compliance) are always included.",
    )
    selected_services = required + selected_optional

    # Show selected services with rates
    for svc in selected_services:
        info = SERVICE_MODULES[svc]
        tag = " 🔒" if info["required"] else ""
        st.caption(f"• {svc}{tag} — {info['bps']:.1f} bps base — _{info['desc']}_")

    st.markdown("---")
    st.markdown("### 🤝 Negotiation Scenario")

    scenario = st.radio(
        "Select scenario",
        options=list(NEGOTIATION_SCENARIOS.keys()),
        format_func=lambda x: f"{x} ({'-' + fmt_pct(NEGOTIATION_SCENARIOS[x]['discount']) if NEGOTIATION_SCENARIOS[x]['discount'] > 0 else 'Rack Rate'})",
        help="Each scenario models a different competitive posture for fee discussions.",
    )

# ──────────────────────────────────────────────────────────────────────
# COMPUTE PRICING
# ──────────────────────────────────────────────────────────────────────

pricing = calculate_pricing(
    fund_type=fund_type,
    aum_mn=aum_mn,
    selected_services=selected_services,
    scenario=scenario,
    custom_discount_pct=custom_discount,
    share_classes=share_classes,
    nav_frequency=nav_frequency,
    term_years=term_years,
)

# ──────────────────────────────────────────────────────────────────────
# TABS
# ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "💰 Pricing Summary",
    "📈 Sensitivity Analysis",
    "⚔️ Negotiation Scenarios",
    "📋 Portfolio View",
])

# ══════════════════════════════════════════════════════════════════════
# TAB 1: PRICING SUMMARY
# ══════════════════════════════════════════════════════════════════════

with tab1:
    narrative(
        "<strong>How to read this:</strong> The metrics below show the output of "
        "the pricing engine for your configured fund. The effective rate is the "
        "all-in fee after all discount layers are applied. Margin is estimated "
        "using a simplified FTE cost model ($85K fully-loaded per head, Ireland-based). "
        "The discount waterfall decomposes each layer so you can see where fee "
        "compression is coming from."
    )

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Annual Revenue", fmt_usd(pricing["annual_revenue_mn"]),
                   delta="Min fee applied" if pricing["min_fee_applied"] else None,
                   delta_color="off")
    with c2:
        st.metric("Effective Rate", fmt_bps(pricing["effective_bps"]),
                   delta=f"↓ from {fmt_bps(pricing['gross_bps'])} gross")
    with c3:
        margin_color = "normal" if pricing["margin"] > 0.3 else "off"
        st.metric("Est. Margin", fmt_pct(pricing["margin"]),
                   delta=f"{pricing['headcount']} FTE estimated", delta_color="off")
    with c4:
        st.metric("Contract Value", fmt_usd(pricing["contract_value_mn"]),
                   delta=f"{pricing['term_years']}-year term", delta_color="off")

    # ── Discount Waterfall ────────────────────────────────────────────
    section_header("📉", "Discount Waterfall")

    waterfall_items = [
        ("Gross Rate", pricing["gross_bps"], THEME["muted"]),
        (f"Volume Discount ({fmt_pct(pricing['volume_discount'])})",
         -pricing["gross_bps"] * pricing["volume_discount"], THEME["cyan"]),
        (f"Negotiation ({fmt_pct(pricing['nego_discount'])})",
         -pricing["gross_bps"] * (1 - pricing["volume_discount"]) * pricing["nego_discount"],
         THEME["amber"]),
    ]
    if custom_discount > 0:
        waterfall_items.append((
            f"Custom ({custom_discount}%)",
            -pricing["gross_bps"] * (custom_discount / 100) * 0.5,
            THEME["purple"],
        ))
    if pricing["term_discount"] > 0:
        waterfall_items.append((
            f"Term Discount ({fmt_pct(pricing['term_discount'])})",
            -pricing["gross_bps"] * pricing["term_discount"] * 0.5,
            THEME["green"],
        ))
    waterfall_items.append(("Effective Rate", pricing["effective_bps"], THEME["green"]))

    fig_wf = go.Figure(go.Waterfall(
        x=[w[0] for w in waterfall_items],
        y=[w[1] for w in waterfall_items],
        measure=["absolute"] + ["relative"] * (len(waterfall_items) - 2) + ["total"],
        textposition="outside",
        text=[f"{abs(w[1]):.2f}" for w in waterfall_items],
        connector=dict(line=dict(color=THEME["border"])),
        increasing=dict(marker=dict(color=THEME["green"])),
        decreasing=dict(marker=dict(color=THEME["red"])),
        totals=dict(marker=dict(color=THEME["green"])),
    ))
    fig_wf.update_layout(title="Fee Rate Waterfall (bps)", showlegend=False)
    plotly_dark_layout(fig_wf, height=380)
    st.plotly_chart(fig_wf, use_container_width=True)

    # ── Service Breakdown ─────────────────────────────────────────────
    col_left, col_right = st.columns(2)

    with col_left:
        section_header("🧩", "Fee Composition by Service")
        svc_df = pd.DataFrame(pricing["service_breakdown"])
        fig_pie = go.Figure(go.Pie(
            labels=svc_df["service"],
            values=svc_df["adjusted_bps"],
            hole=0.45,
            marker=dict(colors=THEME["chart_palette"][:len(svc_df)]),
            textinfo="label+percent",
            textfont=dict(size=11),
        ))
        fig_pie.update_layout(title="Adjusted bps by Service")
        plotly_dark_layout(fig_pie, height=340)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_right:
        section_header("💰", "Revenue vs Cost")
        fig_econ = go.Figure()
        fig_econ.add_trace(go.Bar(
            x=["Revenue", "Cost"],
            y=[pricing["annual_revenue_mn"], pricing["annual_cost_mn"]],
            marker_color=[THEME["green"], THEME["red"]],
            text=[fmt_usd(pricing["annual_revenue_mn"]), fmt_usd(pricing["annual_cost_mn"])],
            textposition="outside",
        ))
        fig_econ.update_layout(title="Annual Economics ($M)", yaxis_title="$M")
        plotly_dark_layout(fig_econ, height=340)
        st.plotly_chart(fig_econ, use_container_width=True)

    # ── Service detail table ──────────────────────────────────────────
    with st.expander("📊 Detailed Service Breakdown"):
        detail_df = pd.DataFrame(pricing["service_breakdown"])
        detail_df.columns = ["Service", "Base Rate (bps)", "Adjusted Rate (bps)"]
        detail_df["Adjusted Rate (bps)"] = detail_df["Adjusted Rate (bps)"].round(3)
        st.dataframe(detail_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════
# TAB 2: SENSITIVITY ANALYSIS
# ══════════════════════════════════════════════════════════════════════

with tab2:
    narrative(
        "<strong>AUM Sensitivity Analysis:</strong> These charts show how revenue, "
        "effective rate, and margin behave as AUM scales — holding all other parameters "
        "constant. The step-function in the effective rate reflects volume tier thresholds "
        "at $500M, $2B, $5B, and $15B. The margin curve reveals FA operating leverage: "
        "fixed FTE costs amortise over larger AUM, driving margin expansion at scale."
    )

    aum_points = [50, 100, 250, 500, 750, 1000, 1500, 2000, 3000, 5000, 7500, 10000, 15000, 20000, 25000]
    sensitivity_data = []
    for a in aum_points:
        p = calculate_pricing(fund_type, a, selected_services, scenario,
                              custom_discount, share_classes, nav_frequency, term_years)
        sensitivity_data.append({
            "AUM ($M)": a,
            "Annual Revenue ($M)": round(p["annual_revenue_mn"], 4),
            "Effective Rate (bps)": round(p["effective_bps"], 3),
            "Margin": round(p["margin"], 4),
            "Headcount": p["headcount"],
        })
    sens_df = pd.DataFrame(sensitivity_data)

    # Revenue & Rate chart
    section_header("📈", "Revenue & Effective Rate by AUM")
    fig_sens = make_subplots(specs=[[{"secondary_y": True}]])
    fig_sens.add_trace(
        go.Scatter(x=sens_df["AUM ($M)"], y=sens_df["Annual Revenue ($M)"],
                   name="Annual Revenue ($M)", fill="tozeroy",
                   fillcolor=f"rgba(16,185,129,0.15)",
                   line=dict(color=THEME["green"], width=2.5)),
        secondary_y=False,
    )
    fig_sens.add_trace(
        go.Scatter(x=sens_df["AUM ($M)"], y=sens_df["Effective Rate (bps)"],
                   name="Effective Rate (bps)", line=dict(color=THEME["accent"], width=2.5, dash="dot"),
                   mode="lines+markers", marker=dict(size=5)),
        secondary_y=True,
    )
    fig_sens.update_yaxes(title_text="Revenue ($M)", secondary_y=False)
    fig_sens.update_yaxes(title_text="Effective Rate (bps)", secondary_y=True)
    fig_sens.update_xaxes(title_text="AUM ($M)")
    fig_sens.update_layout(title="Revenue Growth & Rate Compression")
    plotly_dark_layout(fig_sens, height=400)
    st.plotly_chart(fig_sens, use_container_width=True)

    # Margin curve
    section_header("📊", "Margin Curve")
    narrative(
        "<strong>Margin trajectory:</strong> At low AUM, the minimum fee floor ($50K) "
        "protects revenue but margins are thin. Beyond $1B, margins typically stabilise "
        "at 35–50%. At very high AUM, aggressive volume discounts can compress margins "
        "— a dynamic to monitor in large mandate negotiations."
    )
    fig_margin = go.Figure()
    fig_margin.add_trace(go.Scatter(
        x=sens_df["AUM ($M)"], y=sens_df["Margin"],
        fill="tozeroy", fillcolor="rgba(16,185,129,0.12)",
        line=dict(color=THEME["green"], width=2.5),
        mode="lines+markers", marker=dict(size=5),
        name="Estimated Margin",
    ))
    # 30% and 15% reference lines
    fig_margin.add_hline(y=0.30, line_dash="dash", line_color=THEME["amber"],
                         annotation_text="Target (30%)", annotation_font_color=THEME["amber"])
    fig_margin.add_hline(y=0.15, line_dash="dash", line_color=THEME["red"],
                         annotation_text="Floor (15%)", annotation_font_color=THEME["red"])
    fig_margin.update_layout(title="Margin by AUM Scale",
                             xaxis_title="AUM ($M)", yaxis_title="Margin",
                             yaxis_tickformat=".0%", yaxis_range=[0, 0.7])
    plotly_dark_layout(fig_margin, height=380)
    st.plotly_chart(fig_margin, use_container_width=True)

    # Volume tier table
    section_header("🏷️", "Volume Discount Schedule")
    tier_data = []
    for lo, hi, disc in VOLUME_TIERS:
        hi_label = f"${hi/1000:.0f}B" if hi >= 1000 and hi < 1e9 else (f"${hi:.0f}M" if hi < 1000 else "∞")
        lo_label = f"${lo/1000:.0f}B" if lo >= 1000 else f"${lo:.0f}M"
        current = "◀ CURRENT" if lo <= aum_mn < hi else ""
        tier_data.append({
            "AUM Range": f"{lo_label} – {hi_label}",
            "Volume Discount": f"{disc*100:.0f}%" if disc > 0 else "—",
            "Status": current,
        })
    st.dataframe(pd.DataFrame(tier_data), use_container_width=True, hide_index=True)

    with st.expander("📋 Full Sensitivity Data Table"):
        st.dataframe(sens_df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════
# TAB 3: NEGOTIATION SCENARIOS
# ══════════════════════════════════════════════════════════════════════

with tab3:
    narrative(
        "<strong>Negotiation Playbook:</strong> Each scenario models a different "
        "competitive posture. <em>Standard</em> is your rack rate. <em>Competitive Bid</em> "
        "(–12%) is typical when 2–3 administrators are shortlisted. <em>Strategic Win</em> "
        "(–20%) is reserved for anchor mandates that bring platform credibility. "
        "<em>Retention</em> (–25%) is the defensive position for at-risk relationships — "
        "use sparingly and with commercial approval."
    )

    # Compute all scenarios
    scenario_results = {}
    for sc_name, sc_info in NEGOTIATION_SCENARIOS.items():
        p = calculate_pricing(fund_type, aum_mn, selected_services, sc_name,
                              custom_discount, share_classes, nav_frequency, term_years)
        scenario_results[sc_name] = p

    # Scenario cards
    cols = st.columns(4)
    for i, (sc_name, sc_info) in enumerate(NEGOTIATION_SCENARIOS.items()):
        p = scenario_results[sc_name]
        with cols[i]:
            border_color = sc_info["color"]
            st.markdown(f"""
            <div style="background:#111827; border:1px solid #1e293b; border-top:3px solid {border_color};
                        border-radius:10px; padding:18px; text-align:center;">
                <div style="font-size:0.85rem; font-weight:700; color:{border_color}; margin-bottom:10px;">
                    {sc_name}
                </div>
                <div style="font-size:1.4rem; font-weight:700; color:#e2e8f0;
                            font-family:'JetBrains Mono',monospace; margin-bottom:4px;">
                    {fmt_usd(p['annual_revenue_mn'])}
                </div>
                <div style="font-size:0.78rem; color:#94a3b8; margin-bottom:6px;">
                    {fmt_bps(p['effective_bps'])} · {fmt_pct(p['margin'])} margin
                </div>
                <div style="font-size:0.72rem; color:#64748b;">
                    Contract: {fmt_usd(p['contract_value_mn'])}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")

    # Comparison bar chart
    section_header("📊", "Revenue by Scenario")
    fig_sc = go.Figure()
    sc_names = list(scenario_results.keys())
    sc_revenues = [scenario_results[s]["annual_revenue_mn"] for s in sc_names]
    sc_colors = [NEGOTIATION_SCENARIOS[s]["color"] for s in sc_names]
    fig_sc.add_trace(go.Bar(
        x=sc_names, y=sc_revenues,
        marker_color=sc_colors,
        text=[fmt_usd(r) for r in sc_revenues],
        textposition="outside",
    ))
    fig_sc.update_layout(title="Annual Revenue Comparison", yaxis_title="Revenue ($M)")
    plotly_dark_layout(fig_sc, height=380)
    st.plotly_chart(fig_sc, use_container_width=True)

    # Walk-away analysis
    section_header("🎯", "Walk-Away Analysis")
    narrative(
        "<strong>Key negotiation thresholds:</strong> These figures give you the "
        "anchor points for any fee discussion. The per-bps impact quantifies the "
        "annual revenue cost of every basis point conceded. The floor price is the "
        "rate at which margin drops to 15% — below this, escalate before agreeing. "
        "The breakeven rate is your absolute minimum."
    )

    bps_impact = (aum_mn * 1) / 10_000  # revenue impact per 1 bps ($M)
    floor_bps = (pricing["annual_cost_mn"] / aum_mn * 10_000 / 0.85) if aum_mn > 0 else 0
    breakeven_bps = (pricing["annual_cost_mn"] / aum_mn * 10_000) if aum_mn > 0 else 0
    retention_rev = scenario_results.get("Retention", {}).get("annual_revenue_mn", 0)
    standard_rev = scenario_results.get("Standard", {}).get("annual_revenue_mn", 0)
    revenue_at_risk = standard_rev - retention_rev

    w1, w2, w3, w4 = st.columns(4)
    with w1:
        st.metric("Per 1 bps Concession", fmt_usd(bps_impact), delta="Annual impact", delta_color="off")
    with w2:
        st.metric("Floor Price (15% margin)", fmt_bps(floor_bps), delta="Minimum viable rate", delta_color="off")
    with w3:
        st.metric("Breakeven Rate", fmt_bps(breakeven_bps), delta="$0 margin", delta_color="off")
    with w4:
        st.metric("Revenue at Risk", fmt_usd(revenue_at_risk), delta="Standard vs Retention", delta_color="off")

    # Scenario comparison table
    with st.expander("📋 Full Scenario Comparison Table"):
        comp_data = []
        for sc_name in sc_names:
            p = scenario_results[sc_name]
            comp_data.append({
                "Scenario": sc_name,
                "Discount": fmt_pct(NEGOTIATION_SCENARIOS[sc_name]["discount"]),
                "Effective Rate": fmt_bps(p["effective_bps"]),
                "Annual Revenue": fmt_usd(p["annual_revenue_mn"]),
                "Margin": fmt_pct(p["margin"]),
                "Contract Value": fmt_usd(p["contract_value_mn"]),
                "Headcount": p["headcount"],
            })
        st.dataframe(pd.DataFrame(comp_data), use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════
# TAB 4: PORTFOLIO VIEW
# ══════════════════════════════════════════════════════════════════════

with tab4:
    narrative(
        "<strong>Portfolio View:</strong> This shows blended economics across a "
        "multi-fund client relationship. Individual fund margins vary, but the "
        "relationship-level blended rate and composite margin determine commercial "
        "viability. Use this to identify cross-sell opportunities, margin dilution "
        "risks, and to prepare for relationship-level fee reviews."
    )

    # Default portfolio (editable via session state)
    if "portfolio" not in st.session_state:
        st.session_state.portfolio = [
            {"name": "Global Equity UCITS", "type": "UCITS Equity", "aum": 800,
             "services": ["NAV Calculation", "Regulatory Compliance", "Transfer Agency", "Client Reporting"],
             "scenario": "Standard", "classes": 5, "freq": "Daily", "term": 5},
            {"name": "Euro Corp Bond", "type": "UCITS Fixed Income", "aum": 1200,
             "services": ["NAV Calculation", "Regulatory Compliance", "Client Reporting", "Tax Services"],
             "scenario": "Standard", "classes": 4, "freq": "Daily", "term": 5},
            {"name": "PE Growth Fund III", "type": "AIF Private Equity", "aum": 350,
             "services": ["NAV Calculation", "Regulatory Compliance", "Client Reporting", "Tax Services", "Risk Analytics"],
             "scenario": "Competitive Bid", "classes": 2, "freq": "Monthly", "term": 7},
        ]

    portfolio = st.session_state.portfolio

    # Add new fund
    section_header("➕", "Add Fund to Portfolio")
    with st.expander("Add a new fund"):
        ac1, ac2, ac3 = st.columns(3)
        with ac1:
            new_name = st.text_input("Fund Name", value="New Fund")
            new_type = st.selectbox("Type", list(FUND_TYPES.keys()), key="new_type")
        with ac2:
            new_aum = st.number_input("AUM ($M)", min_value=10, max_value=30000, value=500, key="new_aum")
            new_classes = st.number_input("Share Classes", min_value=1, max_value=30, value=3, key="new_classes")
        with ac3:
            new_freq = st.selectbox("NAV Freq", ["Daily", "Weekly", "Monthly"], key="new_freq")
            new_term = st.number_input("Term (yrs)", min_value=1, max_value=10, value=3, key="new_term")

        new_scenario = st.selectbox("Scenario", list(NEGOTIATION_SCENARIOS.keys()), key="new_scenario")
        required_svcs = [k for k, v in SERVICE_MODULES.items() if v["required"]]
        optional_svcs = [k for k, v in SERVICE_MODULES.items() if not v["required"]]
        new_optional = st.multiselect("Optional Services", optional_svcs, default=["Transfer Agency"], key="new_svcs")
        new_services = required_svcs + new_optional

        if st.button("➕ Add to Portfolio", type="primary"):
            st.session_state.portfolio.append({
                "name": new_name, "type": new_type, "aum": new_aum,
                "services": new_services, "scenario": new_scenario,
                "classes": new_classes, "freq": new_freq, "term": new_term,
            })
            st.rerun()

    # Compute portfolio pricing
    port_results = []
    for fund in portfolio:
        p = calculate_pricing(
            fund["type"], fund["aum"], fund["services"], fund["scenario"],
            0.0, fund["classes"], fund["freq"], fund["term"],
        )
        port_results.append({"fund": fund, "pricing": p})

    total_aum = sum(f["fund"]["aum"] for f in port_results)
    total_rev = sum(f["pricing"]["annual_revenue_mn"] for f in port_results)
    total_cost = sum(f["pricing"]["annual_cost_mn"] for f in port_results)
    total_contract = sum(f["pricing"]["contract_value_mn"] for f in port_results)
    blended_bps = (total_rev / total_aum * 10_000) if total_aum > 0 else 0
    blended_margin = (total_rev - total_cost) / total_rev if total_rev > 0 else 0

    # Portfolio KPIs
    pk1, pk2, pk3, pk4 = st.columns(4)
    with pk1:
        st.metric("Total AUM", fmt_usd(total_aum))
    with pk2:
        st.metric("Total Revenue", fmt_usd(total_rev), delta=f"Blended {fmt_bps(blended_bps)}", delta_color="off")
    with pk3:
        st.metric("Blended Margin", fmt_pct(blended_margin))
    with pk4:
        st.metric("Total Contract Value", fmt_usd(total_contract))

    # Fund detail table
    section_header("📋", "Fund-Level Detail")
    table_data = []
    for pr in port_results:
        f, p = pr["fund"], pr["pricing"]
        table_data.append({
            "Fund": f["name"],
            "Type": f["type"],
            "AUM": fmt_usd(f["aum"]),
            "Eff. Rate": fmt_bps(p["effective_bps"]),
            "Revenue": fmt_usd(p["annual_revenue_mn"]),
            "Margin": fmt_pct(p["margin"]),
            "Term": f"{f['term']}Y",
            "Scenario": f["scenario"],
        })
    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

    # Revenue composition chart
    section_header("📊", "Revenue & Cost Composition")
    fig_port = go.Figure()
    fund_names = [pr["fund"]["name"] for pr in port_results]
    fig_port.add_trace(go.Bar(
        x=fund_names,
        y=[pr["pricing"]["annual_revenue_mn"] for pr in port_results],
        name="Revenue", marker_color=THEME["green"],
    ))
    fig_port.add_trace(go.Bar(
        x=fund_names,
        y=[pr["pricing"]["annual_cost_mn"] for pr in port_results],
        name="Cost", marker_color=THEME["red"], opacity=0.6,
    ))
    fig_port.update_layout(title="Revenue vs Cost by Fund", barmode="group",
                           yaxis_title="$M")
    plotly_dark_layout(fig_port, height=380)
    st.plotly_chart(fig_port, use_container_width=True)

    # AUM allocation pie
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        section_header("🥧", "AUM Allocation")
        fig_aum_pie = go.Figure(go.Pie(
            labels=fund_names,
            values=[pr["fund"]["aum"] for pr in port_results],
            hole=0.4, marker=dict(colors=THEME["chart_palette"][:len(fund_names)]),
        ))
        fig_aum_pie.update_layout(title="AUM Distribution")
        plotly_dark_layout(fig_aum_pie, height=320)
        st.plotly_chart(fig_aum_pie, use_container_width=True)

    with col_p2:
        section_header("🥧", "Revenue Contribution")
        fig_rev_pie = go.Figure(go.Pie(
            labels=fund_names,
            values=[pr["pricing"]["annual_revenue_mn"] for pr in port_results],
            hole=0.4, marker=dict(colors=THEME["chart_palette"][:len(fund_names)]),
        ))
        fig_rev_pie.update_layout(title="Revenue Distribution")
        plotly_dark_layout(fig_rev_pie, height=320)
        st.plotly_chart(fig_rev_pie, use_container_width=True)

    # Remove funds
    if len(portfolio) > 0:
        with st.expander("🗑️ Remove a fund from portfolio"):
            remove_idx = st.selectbox(
                "Select fund to remove",
                range(len(portfolio)),
                format_func=lambda i: portfolio[i]["name"],
            )
            if st.button("Remove Fund", type="secondary"):
                st.session_state.portfolio.pop(remove_idx)
                st.rerun()

# ──────────────────────────────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("""
<div style="display:flex; justify-content:space-between; font-size:0.72rem; color:#64748b; padding:8px 0;">
    <span>FA Pricing Model · For internal commercial use · Fund Administration Product Team</span>
    <span>Model assumptions are illustrative. Actual pricing requires commercial approval.</span>
</div>
""", unsafe_allow_html=True)