"""
Supply Chain Intelligence — interactive visualizations.

Three core visualizations per sector:
1. Supply Chain Flow (Sankey diagram) — how materials/products flow
2. Revenue Breakdown (horizontal bars) — how each company earns money
3. Cost Structure (horizontal bars) — what each company spends on

This page uses Plotly for all charts. Data comes from config/supply_chain_data.py
which is a curated, relatively static dataset (only changes on major business shifts).
"""

import streamlit as st
import plotly.graph_objects as go

from config.sectors import SECTORS
from config.supply_chain_data import SUPPLY_CHAIN_DATA, get_supply_chain
from ui.components import SECTOR_COLORS


# ── Color palette ─────────────────────────────────────────────────

_LAYER_COLORS = {
    "Raw Materials & IP":       "#B0BEC5",
    "Fabrication":              "#64B5F6",
    "Chip Design":              "#81C784",
    "Server Assembly":          "#FFB74D",
    "Cloud & AI Platforms":     "#CE93D8",
    "Energy Infrastructure":    "#F06292",
    "Components & Propulsion":  "#B0BEC5",
    "Launch Vehicles":          "#64B5F6",
    "Satellite & Space Systems":"#81C784",
    "Communications & Services":"#FFB74D",
    "Test & Measurement":       "#B0BEC5",
    "Optical Components":       "#64B5F6",
    "Network Platforms":        "#81C784",
    "Data Center Networking":   "#FFB74D",
}

_SEGMENT_COLORS = [
    "#5C9CE6", "#C8A951", "#81C784", "#F06292", "#CE93D8",
    "#FFB74D", "#64B5F6", "#EF5350", "#26A69A", "#AB47BC",
]

_COST_COLORS = [
    "#E57373", "#F06292", "#BA68C8", "#9575CD", "#7986CB",
    "#64B5F6", "#4FC3F7", "#4DD0E1", "#4DB6AC", "#81C784",
]


# ═══════════════════════════════════════════════════════════════════
# PAGE ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def render():
    st.markdown('<h2 style="font-family:Manrope,sans-serif;font-weight:800;'
                'letter-spacing:-0.03em;color:#0f172a">Supply Chain Intelligence</h2>',
                unsafe_allow_html=True)
    st.caption(
        "How companies earn revenue, what they spend on, and how the supply chain flows. "
        "This data is curated from 10-K filings and public disclosures."
    )

    # ── Sector selector ───────────────────────────────────────────
    sector_options = {sid: data["sector_name"] for sid, data in SUPPLY_CHAIN_DATA.items()}
    col1, _ = st.columns([2, 4])
    with col1:
        selected_id = st.selectbox(
            "Select Sector",
            list(sector_options.keys()),
            format_func=lambda x: sector_options[x],
            label_visibility="collapsed",
        )

    sector = get_supply_chain(selected_id)
    if not sector:
        st.error("Sector data not found.")
        return

    st.markdown(f'<h3 style="font-family:Manrope,sans-serif;font-weight:800;'
                f'letter-spacing:-0.02em;color:#0f172a">{sector["sector_name"]}</h3>',
                unsafe_allow_html=True)
    st.caption(sector["description"])

    # ── Supply Chain Flow (Sankey) ────────────────────
    with st.container(border=True):
        st.markdown('<span class="section-title">Supply Chain Flow</span>',
                    unsafe_allow_html=True)
        st.caption("How materials, components, and products flow from upstream to downstream")
        _render_sankey(sector)

    st.write("")

    # ── Company deep-dive selector ────────────────────────────────
    companies = sector["companies"]
    tickers = list(companies.keys())
    names = [f"{t} — {companies[t]['name']}" for t in tickers]

    col_sel, _ = st.columns([3, 3])
    with col_sel:
        selected_company = st.selectbox(
            "Select Company",
            tickers,
            format_func=lambda t: f"{t} — {companies[t]['name']}",
            key=f"sc_company_{selected_id}",
        )

    company = companies[selected_company]

    # ── Revenue + Cost side by side ───────────────────────────────
    col_rev, col_cost = st.columns(2)

    with col_rev:
        with st.container(border=True):
            st.markdown(f'<span class="section-title">{selected_company} Revenue Breakdown</span>',
                        unsafe_allow_html=True)
            st.caption(f"{company['name']} — How they earn money")
            _render_revenue_chart(company, selected_company)

    with col_cost:
        with st.container(border=True):
            st.markdown(f'<span class="section-title">{selected_company} Cost Structure</span>',
                        unsafe_allow_html=True)
            st.caption(f"Where {selected_company}'s money goes — key inputs & investments")
            _render_cost_chart(company, selected_company)

    st.write("")

    # ── Product & Relationship cards ──────────────────────────────
    with st.container(border=True):
        st.markdown(f'<span class="section-title">{selected_company} at a Glance</span>',
                    unsafe_allow_html=True)
        _render_company_card(company, selected_company, sector)

    st.write("")

    # ── All companies overview ────────────────────────────────────
    with st.container(border=True):
        st.markdown('<span class="section-title">Sector Revenue Comparison</span>',
                    unsafe_allow_html=True)
        st.caption("Largest revenue segment per company — which products dominate")
        _render_sector_comparison(sector)


# ═══════════════════════════════════════════════════════════════════
# SANKEY DIAGRAM — Supply Chain Flow
# ═══════════════════════════════════════════════════════════════════

def _render_sankey(sector: dict):
    """Build and render a Sankey diagram from the sector's key_flows."""
    flows = sector.get("key_flows", [])
    if not flows:
        st.caption("No flow data available.")
        return

    companies = sector.get("companies", {})

    # Build unique node list
    nodes_set = []
    node_index = {}

    def _get_idx(name: str) -> int:
        if name not in node_index:
            node_index[name] = len(nodes_set)
            nodes_set.append(name)
        return node_index[name]

    sources, targets, values, labels = [], [], [], []
    for f in flows:
        src_idx = _get_idx(f["from"])
        tgt_idx = _get_idx(f["to"])
        sources.append(src_idx)
        targets.append(tgt_idx)
        values.append(f.get("value", 10))
        labels.append(f.get("label", ""))

    # Color nodes by layer
    node_colors = []
    for n in nodes_set:
        if n in companies:
            layer = companies[n].get("layer", "")
            node_colors.append(_LAYER_COLORS.get(layer, "#C8A951"))
        elif n in ("End Users", "end_users"):
            node_colors.append("#66BB6A")
        elif n in ("Telecom", "Cloud", "NASA", "DOD", "DOD/NASA", "Apple"):
            node_colors.append("#FFB74D")
        else:
            node_colors.append("#B0BEC5")

    # Link colors (lighter version of source)
    link_colors = []
    for s in sources:
        base = node_colors[s]
        # Make it semi-transparent
        link_colors.append(base.replace("#", "rgba(") if "#" in base else base)

    # Convert hex to rgba for links
    link_rgba = []
    for s in sources:
        c = node_colors[s]
        try:
            r = int(c[1:3], 16)
            g = int(c[3:5], 16)
            b = int(c[5:7], 16)
            link_rgba.append(f"rgba({r},{g},{b},0.3)")
        except (ValueError, IndexError):
            link_rgba.append("rgba(200,169,81,0.3)")

    fig = go.Figure(data=[go.Sankey(
        arrangement="snap",
        node=dict(
            pad=20,
            thickness=25,
            line=dict(color="#E8E4DE", width=1),
            label=nodes_set,
            color=node_colors,
            hovertemplate="%{label}<extra></extra>",
        ),
        link=dict(
            source=sources,
            target=targets,
            value=values,
            label=labels,
            color=link_rgba,
            hovertemplate="%{source.label} → %{target.label}<br>%{label}<extra></extra>",
        ),
    )])

    fig.update_layout(
        font=dict(size=12, family="Inter, system-ui, sans-serif"),
        margin=dict(l=10, r=10, t=10, b=10),
        height=480,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # Legend for layers
    layers = sector.get("chain_layers", [])
    if layers:
        legend_html = '<div style="display:flex;gap:16px;flex-wrap:wrap;justify-content:center;margin-top:-8px">'
        for layer in layers:
            color = layer.get("color", "#999")
            legend_html += (
                f'<span style="display:inline-flex;align-items:center;gap:4px;font-size:0.78rem">'
                f'<span style="width:10px;height:10px;border-radius:3px;background:{color}"></span>'
                f'{layer["name"]}</span>'
            )
        legend_html += '</div>'
        st.markdown(legend_html, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════
# REVENUE BREAKDOWN — Horizontal Bar
# ═══════════════════════════════════════════════════════════════════

def _render_revenue_chart(company: dict, ticker: str):
    """Horizontal bar chart of revenue segments."""
    segments = company.get("revenue_segments", {})
    if not segments:
        st.caption("No revenue data available.")
        return

    names = list(segments.keys())
    pcts = [segments[n]["pct"] for n in names]
    descs = [segments[n]["description"] for n in names]

    # Sort by percentage descending
    sorted_data = sorted(zip(pcts, names, descs), reverse=True)
    pcts = [d[0] for d in sorted_data]
    names = [d[1] for d in sorted_data]
    descs = [d[2] for d in sorted_data]

    # Reverse for horizontal bar (top = highest)
    pcts_r = list(reversed(pcts))
    names_r = list(reversed(names))
    descs_r = list(reversed(descs))
    colors_r = list(reversed(_SEGMENT_COLORS[:len(names)]))

    fig = go.Figure(go.Bar(
        x=pcts_r,
        y=names_r,
        orientation='h',
        text=[f"{p}%" for p in pcts_r],
        textposition='auto',
        textfont=dict(color="white", size=13, family="system-ui"),
        marker=dict(
            color=colors_r,
            line=dict(width=0),
            cornerradius=4,
        ),
        hovertemplate="<b>%{y}</b><br>%{x}% of revenue<br>%{customdata}<extra></extra>",
        customdata=descs_r,
    ))

    fig.update_layout(
        xaxis=dict(
            title="% of Total Revenue",
            range=[0, max(pcts) + 10],
            showgrid=True,
            gridcolor="rgba(0,0,0,0.05)",
        ),
        yaxis=dict(title="", tickfont=dict(size=11)),
        margin=dict(l=10, r=20, t=10, b=40),
        height=max(250, len(names) * 48 + 60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.25,
    )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # Detail table below chart
    for i, (name, pct, desc) in enumerate(zip(names, pcts, descs)):
        color = _SEGMENT_COLORS[i % len(_SEGMENT_COLORS)]
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:6px">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{color};'
            f'margin-top:6px;flex-shrink:0"></span>'
            f'<div><span style="font-weight:600;font-size:0.85rem">{name}</span> '
            f'<span style="color:#9C9C9C;font-size:0.8rem">({pct}%)</span><br>'
            f'<span style="font-size:0.78rem;color:#666">{desc}</span></div></div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════
# COST STRUCTURE — Horizontal Bar
# ═══════════════════════════════════════════════════════════════════

def _render_cost_chart(company: dict, ticker: str):
    """Horizontal bar chart of cost inputs."""
    costs = company.get("cost_inputs", {})
    if not costs:
        st.caption("No cost data available.")
        return

    names = list(costs.keys())
    pcts = [costs[n]["pct"] for n in names]
    sources = [costs[n]["source"] for n in names]

    # Sort by percentage descending
    sorted_data = sorted(zip(pcts, names, sources), reverse=True)
    pcts = [d[0] for d in sorted_data]
    names = [d[1] for d in sorted_data]
    sources = [d[2] for d in sorted_data]

    # Reverse for horizontal bar
    pcts_r = list(reversed(pcts))
    names_r = list(reversed(names))
    sources_r = list(reversed(sources))
    colors_r = list(reversed(_COST_COLORS[:len(names)]))

    fig = go.Figure(go.Bar(
        x=pcts_r,
        y=names_r,
        orientation='h',
        text=[f"{p}%" for p in pcts_r],
        textposition='auto',
        textfont=dict(color="white", size=13, family="system-ui"),
        marker=dict(
            color=colors_r,
            line=dict(width=0),
            cornerradius=4,
        ),
        hovertemplate="<b>%{y}</b><br>%{x}% of costs<br>Source: %{customdata}<extra></extra>",
        customdata=sources_r,
    ))

    fig.update_layout(
        xaxis=dict(
            title="% of Total Costs",
            range=[0, max(pcts) + 10],
            showgrid=True,
            gridcolor="rgba(0,0,0,0.05)",
        ),
        yaxis=dict(title="", tickfont=dict(size=11)),
        margin=dict(l=10, r=20, t=10, b=40),
        height=max(250, len(names) * 48 + 60),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.25,
    )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # Detail table
    for i, (name, pct, source) in enumerate(zip(names, pcts, sources)):
        color = _COST_COLORS[i % len(_COST_COLORS)]
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:6px">'
            f'<span style="width:8px;height:8px;border-radius:50%;background:{color};'
            f'margin-top:6px;flex-shrink:0"></span>'
            f'<div><span style="font-weight:600;font-size:0.85rem">{name}</span> '
            f'<span style="color:#9C9C9C;font-size:0.8rem">({pct}%)</span><br>'
            f'<span style="font-size:0.78rem;color:#666">Source: {source}</span></div></div>',
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════
# COMPANY CARD — Products, relationships, role
# ═══════════════════════════════════════════════════════════════════

def _render_company_card(company: dict, ticker: str, sector: dict):
    """Render a card showing products, upstream/downstream relationships."""
    companies = sector.get("companies", {})

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Role in Supply Chain**")
        layer = company.get("layer", "Unknown")
        layer_color = _LAYER_COLORS.get(layer, "#C8A951")
        st.markdown(
            f'<span style="display:inline-block;background:{layer_color};color:white;'
            f'padding:4px 14px;border-radius:20px;font-size:0.82rem;font-weight:600">'
            f'{layer}</span>',
            unsafe_allow_html=True,
        )
        st.write("")
        st.markdown("**Key Products**")
        for p in company.get("products", []):
            st.markdown(f"• {p}")

    with col2:
        st.markdown("**Supplies To** (Downstream)")
        for target in company.get("supplies_to", []):
            if target in companies:
                name = companies[target]["name"]
                st.markdown(f"→ **{target}** — {name}")
            else:
                label = target.replace("_", " ").title()
                st.markdown(f"→ *{label}*")

    with col3:
        st.markdown("**Receives From** (Upstream)")
        for source in company.get("receives_from", []):
            if source in companies:
                name = companies[source]["name"]
                st.markdown(f"← **{source}** — {name}")
            else:
                label = source.replace("_", " ").title()
                st.markdown(f"← *{label}*")


# ═══════════════════════════════════════════════════════════════════
# SECTOR COMPARISON — All companies, top segment
# ═══════════════════════════════════════════════════════════════════

def _render_sector_comparison(sector: dict):
    """Grouped bar chart showing all companies' biggest revenue segment."""
    companies = sector.get("companies", {})

    tickers = []
    segment_names = []
    segment_pcts = []
    colors = []

    for i, (ticker, data) in enumerate(companies.items()):
        segments = data.get("revenue_segments", {})
        if not segments:
            continue
        # Get the top segment
        top_name = max(segments, key=lambda k: segments[k]["pct"])
        top_pct = segments[top_name]["pct"]

        tickers.append(ticker)
        segment_names.append(top_name)
        segment_pcts.append(top_pct)
        colors.append(_SEGMENT_COLORS[i % len(_SEGMENT_COLORS)])

    if not tickers:
        st.caption("No data.")
        return

    fig = go.Figure(go.Bar(
        x=tickers,
        y=segment_pcts,
        text=[f"{p}%<br><span style='font-size:9px'>{n}</span>"
              for p, n in zip(segment_pcts, segment_names)],
        textposition='outside',
        marker=dict(
            color=colors,
            line=dict(width=0),
            cornerradius=6,
        ),
        hovertemplate="<b>%{x}</b><br>%{customdata}: %{y}%<extra></extra>",
        customdata=segment_names,
    ))

    fig.update_layout(
        yaxis=dict(
            title="% of Revenue",
            range=[0, 110],
            showgrid=True,
            gridcolor="rgba(0,0,0,0.05)",
        ),
        xaxis=dict(title="", tickfont=dict(size=12, weight=700)),
        margin=dict(l=40, r=20, t=10, b=40),
        height=350,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        bargap=0.35,
    )

    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
