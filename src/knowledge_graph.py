"""
knowledge_graph.py
Builds a per-query interactive knowledge graph from computed insights (not raw data).
Uses pyvis to generate self-contained HTML rendered in Streamlit via st.components.v1.html().

Node types:
  metric     → purple (#42145F) — central node
  period     → light purple (#7340a0)
  entity     → violet (#5a2d7a)
  delta      → green (#1B5E20) or red (#B71C1C) based on direction
  contributor → pale lavender (#EDE7F6) with dark text
  winner     → dark green (#1B5E20)
  loser      → dark red (#B71C1C)
"""

import json


def build_change_graph(change_result: dict) -> str:
    """
    Build a pyvis knowledge graph for a change_result dict.
    Returns a self-contained HTML string, or a fallback SVG if pyvis unavailable.
    """
    try:
        from pyvis.network import Network
    except ImportError:
        return _fallback_html("pyvis not installed — run: pip install pyvis==0.3.2")

    net = _create_base_network()

    metric_label = change_result.get("metric_label", "Metric")
    pa = change_result.get("period_a", {})
    pb = change_result.get("period_b", {})
    direction = change_result.get("direction", "change")
    pct = change_result.get("pct_change", 0)
    abs_change = change_result.get("absolute_change", 0)
    unit = change_result.get("metric_unit", "")

    # ── Central metric node ───────────────────────────────────────────────────
    metric_id = "metric"
    net.add_node(
        metric_id,
        label=metric_label,
        title=f"Metric: {metric_label} ({unit})",
        color={"background": "#42145F", "border": "#2E0052", "highlight": {"background": "#6A0DAD"}},
        font={"color": "#FFFFFF", "size": 16, "bold": True},
        size=45,
        shape="ellipse",
    )

    # ── Period A node ─────────────────────────────────────────────────────────
    pa_id = "period_a"
    pa_val = pa.get("value", 0)
    pa_label = pa.get("label", "Before")
    net.add_node(
        pa_id,
        label=f"{pa_label}\n{_fmt(pa_val, unit)}",
        title=f"Period A: {pa_label} = {_fmt(pa_val, unit)}",
        color={"background": "#7340a0", "border": "#6A0DAD"},
        font={"color": "#FFFFFF", "size": 13},
        size=32,
        shape="box",
    )
    net.add_edge(pa_id, metric_id, label="baseline", color="#7340a0", width=2, dashes=False)

    # ── Period B node ─────────────────────────────────────────────────────────
    pb_id = "period_b"
    pb_val = pb.get("value", 0)
    pb_label = pb.get("label", "After")
    net.add_node(
        pb_id,
        label=f"{pb_label}\n{_fmt(pb_val, unit)}",
        title=f"Period B: {pb_label} = {_fmt(pb_val, unit)}",
        color={"background": "#42145F", "border": "#2E0052"},
        font={"color": "#FFFFFF", "size": 13},
        size=32,
        shape="box",
    )
    net.add_edge(pb_id, metric_id, label="current", color="#42145F", width=2, dashes=False)

    # ── Delta node ────────────────────────────────────────────────────────────
    delta_id = "delta"
    delta_color = "#1B5E20" if direction == "increase" else "#B71C1C"
    delta_sign = "+" if abs_change >= 0 else ""
    net.add_node(
        delta_id,
        label=f"{delta_sign}{pct:.1f}%\n{delta_sign}{_fmt(abs_change, unit)}",
        title=f"{direction.capitalize()}: {delta_sign}{pct:.1f}% ({delta_sign}{_fmt(abs_change, unit)})",
        color={"background": delta_color, "border": delta_color},
        font={"color": "#FFFFFF", "size": 12},
        size=28,
        shape="diamond",
    )
    net.add_edge(
        pa_id, pb_id,
        label=f"{delta_sign}{pct:.1f}%",
        color=delta_color,
        width=3,
        dashes=True,
    )
    net.add_edge(delta_id, metric_id, label=direction, color=delta_color, width=2)

    # ── Top contributor nodes (up to 5) ───────────────────────────────────────
    contributors = change_result.get("contributors", [])[:5]
    for i, c in enumerate(contributors):
        c_id = f"contrib_{i}"
        entity = c.get("entity", f"Entity {i+1}")
        dim = c.get("dimension", "")
        delta = c.get("delta", 0)
        pct_contrib = c.get("pct_of_total_change", 0)
        c_sign = "+" if delta >= 0 else ""
        c_color = "#2E7D32" if delta >= 0 else "#C62828"
        c_border = "#1B5E20" if delta >= 0 else "#B71C1C"

        node_size = max(18, min(30, int(abs(pct_contrib) * 0.5 + 15)))

        net.add_node(
            c_id,
            label=f"{entity}\n({dim})\n{c_sign}{pct_contrib:.1f}%",
            title=(
                f"{entity} [{dim}]\n"
                f"Delta: {c_sign}{_fmt(delta, '')}\n"
                f"Share of change: {c_sign}{pct_contrib:.1f}%"
            ),
            color={"background": "#EDE7F6", "border": c_border},
            font={"color": c_color, "size": 11},
            size=node_size,
            shape="ellipse",
        )
        edge_label = f"{c_sign}{pct_contrib:.1f}% of change"
        net.add_edge(
            c_id, delta_id,
            label=edge_label,
            color=c_color,
            width=max(1, int(abs(pct_contrib) / 20) + 1),
            dashes=False,
        )

    return _render_to_html(net, title=f"Change in {metric_label}")


def build_compare_graph(compare_result: dict) -> str:
    """
    Build a pyvis knowledge graph for a compare_result dict.
    Returns a self-contained HTML string.
    """
    try:
        from pyvis.network import Network
    except ImportError:
        return _fallback_html("pyvis not installed — run: pip install pyvis==0.3.2")

    net = _create_base_network()

    metric_label = compare_result.get("metric_label", "Metric")
    unit = compare_result.get("metric_unit", "")
    ea = compare_result.get("entity_a", {})
    eb = compare_result.get("entity_b", {})
    winner = compare_result.get("winner", "")
    pct_diff = compare_result.get("pct_diff", 0)
    abs_diff = compare_result.get("absolute_diff", 0)

    # ── Central metric node ───────────────────────────────────────────────────
    net.add_node(
        "metric",
        label=metric_label,
        title=f"Metric: {metric_label} ({unit})",
        color={"background": "#42145F", "border": "#2E0052"},
        font={"color": "#FFFFFF", "size": 16, "bold": True},
        size=45,
        shape="ellipse",
    )

    # ── Entity A node ─────────────────────────────────────────────────────────
    ea_label = ea.get("label", "A")
    ea_val = ea.get("value", 0)
    is_ea_winner = ea_label == winner
    ea_bg = "#1B5E20" if is_ea_winner else "#B71C1C"
    ea_border = "#0D3A14" if is_ea_winner else "#7B1111"
    ea_badge = " (Winner)" if is_ea_winner else ""

    net.add_node(
        "entity_a",
        label=f"{ea_label}{ea_badge}\n{_fmt(ea_val, unit)}",
        title=f"{ea_label}: {_fmt(ea_val, unit)}",
        color={"background": ea_bg, "border": ea_border},
        font={"color": "#FFFFFF", "size": 13},
        size=35,
        shape="box",
    )
    net.add_edge(
        "entity_a", "metric",
        label="contributes",
        color=ea_bg,
        width=3,
    )

    # ── Entity B node ─────────────────────────────────────────────────────────
    eb_label = eb.get("label", "B")
    eb_val = eb.get("value", 0)
    is_eb_winner = eb_label == winner
    eb_bg = "#1B5E20" if is_eb_winner else "#B71C1C"
    eb_border = "#0D3A14" if is_eb_winner else "#7B1111"
    eb_badge = " (Winner)" if is_eb_winner else ""

    net.add_node(
        "entity_b",
        label=f"{eb_label}{eb_badge}\n{_fmt(eb_val, unit)}",
        title=f"{eb_label}: {_fmt(eb_val, unit)}",
        color={"background": eb_bg, "border": eb_border},
        font={"color": "#FFFFFF", "size": 13},
        size=35,
        shape="box",
    )
    net.add_edge(
        "entity_b", "metric",
        label="contributes",
        color=eb_bg,
        width=3,
    )

    # ── Difference edge between entities ─────────────────────────────────────
    diff_sign = "+" if abs_diff >= 0 else ""
    net.add_edge(
        "entity_a", "entity_b",
        label=f"diff: {diff_sign}{pct_diff:.1f}%",
        color="#5a2d7a",
        width=2,
        dashes=True,
    )

    # ── Sub-breakdown nodes for winner ────────────────────────────────────────
    sub = compare_result.get("sub_breakdown_winner", [])[:3]
    winner_node_id = "entity_a" if is_ea_winner else "entity_b"
    for i, s in enumerate(sub):
        sub_id = f"sub_{i}"
        s_entity = s.get("entity", f"Sub {i+1}")
        s_dim = s.get("dimension", "")
        s_share = s.get("share_pct", 0)

        net.add_node(
            sub_id,
            label=f"{s_entity}\n{s_share:.1f}%",
            title=f"{s_entity} ({s_dim}): {s_share:.1f}% of {winner}",
            color={"background": "#EDE7F6", "border": "#42145F"},
            font={"color": "#42145F", "size": 10},
            size=max(15, int(s_share * 0.3 + 14)),
            shape="ellipse",
        )
        net.add_edge(
            sub_id, winner_node_id,
            label="explains",
            color="#7340a0",
            width=1,
            dashes=False,
        )

    return _render_to_html(net, title=f"Compare: {ea.get('label', 'A')} vs {eb.get('label', 'B')}")


def _create_base_network():
    """Return a pyvis Network with DataWitness visual configuration."""
    from pyvis.network import Network

    net = Network(
        height="380px",
        width="100%",
        bgcolor="#FAFAFA",
        font_color="#212121",
        directed=True,
    )
    net.set_options(json.dumps({
        "physics": {"enabled": False},
        "interaction": {
            "hover": True,
            "tooltipDelay": 100,
            "navigationButtons": False,
            "keyboard": False,
        },
        "nodes": {
            "font": {"size": 12, "face": "Arial"},
            "borderWidth": 2,
        },
        "edges": {
            "font": {"size": 10, "face": "Arial", "align": "middle"},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.7}},
            "smooth": {"type": "curvedCW", "roundness": 0.2},
        },
        "layout": {
            "improvedLayout": True,
            "hierarchical": {
                "enabled": True,
                "direction": "UD",
                "sortMethod": "hubsize",
                "nodeSpacing": 120,
                "levelSeparation": 100,
            },
        },
    }))
    return net


def _render_to_html(net, title: str = "Knowledge Graph") -> str:
    """Generate self-contained HTML from the pyvis network."""
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        tmp_path = f.name

    try:
        net.save_graph(tmp_path)
        with open(tmp_path, "r", encoding="utf-8") as f:
            html = f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    # Inject a title banner
    banner = (
        f'<div style="font-family:Arial;font-size:13px;color:#42145F;'
        f'padding:6px 12px;background:#EDE7F6;border-radius:4px;margin-bottom:4px;">'
        f'<strong>Reasoning Graph:</strong> {title}</div>'
    )
    html = html.replace("<body>", f"<body>{banner}", 1)
    return html


def _fmt(value: float, unit: str) -> str:
    """Format a number for display in a graph node label."""
    if unit in ("USD", "$"):
        if abs(value) >= 1_000_000:
            return f"${value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"${value/1_000:.1f}K"
        return f"${value:,.0f}"
    elif unit == "percent":
        return f"{value:.1f}%"
    elif unit == "count":
        return f"{value:,.0f}"
    else:
        if abs(value) >= 1_000_000:
            return f"{value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"{value/1_000:.1f}K"
        return f"{value:,.2f}"


# ── JSON graph builder (vis-network / React frontend) ────────────────────────

def build_graph_json(result: dict) -> dict:
    """Return vis-network-compatible JSON dict {nodes, edges} from any result."""
    if result.get("type") == "change":
        return _change_graph_json(result)
    elif result.get("type") == "compare":
        return _compare_graph_json(result)
    return {"nodes": [], "edges": []}


def _change_graph_json(r: dict) -> dict:
    nodes, edges = [], []
    ml = r.get("metric_label", "Metric")
    unit = r.get("metric_unit", "")
    pa = r.get("period_a", {})
    pb = r.get("period_b", {})
    direction = r.get("direction", "change")
    pct = r.get("pct_change", 0)
    abs_chg = r.get("absolute_change", 0)
    sign = "+" if abs_chg >= 0 else ""
    dc = "#16a34a" if direction == "increase" else "#dc2626"

    nodes.append({
        "id": "metric", "label": ml,
        "color": {"background": "#7c3aed", "border": "#a78bfa", "highlight": {"background": "#8b5cf6"}},
        "font": {"color": "#ffffff", "size": 18, "bold": True},
        "shape": "ellipse", "size": 55,
        "title": f"Metric: {ml} ({unit})",
        "metadata": {"nodeType": "metric", "name": ml, "unit": unit,
                     "description": "Central metric being analyzed"},
    })

    pa_val = pa.get("value", 0)
    pa_label = pa.get("label", "Before")
    nodes.append({
        "id": "period_a",
        "label": f"{pa_label}\n{_fmt(pa_val, unit)}",
        "color": {"background": "#0ea5e9", "border": "#38bdf8"},
        "font": {"color": "#ffffff", "size": 14, "bold": True},
        "shape": "box", "size": 35,
        "title": f"Period A: {pa_label} = {_fmt(pa_val, unit)}",
        "metadata": {"nodeType": "period", "period": "A", "label": pa_label,
                     "value": pa_val, "formattedValue": _fmt(pa_val, unit), "unit": unit},
    })
    edges.append({"from": "period_a", "to": "metric", "label": "baseline",
                  "color": {"color": "#7340a0"}, "width": 2, "arrows": "to", "dashes": False})

    pb_val = pb.get("value", 0)
    pb_label = pb.get("label", "After")
    nodes.append({
        "id": "period_b",
        "label": f"{pb_label}\n{_fmt(pb_val, unit)}",
        "color": {"background": "#3b82f6", "border": "#60a5fa"},
        "font": {"color": "#ffffff", "size": 14, "bold": True},
        "shape": "box", "size": 35,
        "title": f"Period B: {pb_label} = {_fmt(pb_val, unit)}",
        "metadata": {"nodeType": "period", "period": "B", "label": pb_label,
                     "value": pb_val, "formattedValue": _fmt(pb_val, unit), "unit": unit},
    })
    edges.append({"from": "period_b", "to": "metric", "label": "current",
                  "color": {"color": "#42145F"}, "width": 2, "arrows": "to", "dashes": False})

    nodes.append({
        "id": "delta",
        "label": f"{sign}{pct:.1f}%\n{sign}{_fmt(abs_chg, unit)}",
        "color": {"background": dc, "border": dc},
        "font": {"color": "#ffffff", "size": 14, "bold": True},
        "shape": "diamond", "size": 36,
        "title": f"{direction}: {sign}{pct:.1f}%",
        "metadata": {"nodeType": "delta", "direction": direction,
                     "pctChange": round(pct, 2), "absoluteChange": f"{sign}{_fmt(abs_chg, unit)}"},
    })
    edges.append({"from": "period_a", "to": "period_b", "label": f"{sign}{pct:.1f}%",
                  "color": {"color": dc}, "width": 3, "arrows": "to", "dashes": True})
    edges.append({"from": "delta", "to": "metric", "label": direction,
                  "color": {"color": dc}, "width": 2, "arrows": "to"})

    for i, c in enumerate(r.get("contributors", [])[:5]):
        cid = f"c{i}"
        delta = c.get("delta", 0)
        pc = c.get("pct_of_total_change", 0)
        cs = "+" if delta >= 0 else ""
        cc = "#22c55e" if delta >= 0 else "#ef4444"
        cb = "#16a34a" if delta >= 0 else "#dc2626"
        sz = max(24, min(38, int(abs(pc) * 0.5 + 20)))
        entity = c.get("entity", f"Entity {i+1}")
        dim = c.get("dimension", "")
        dir_word = "grow" if delta >= 0 else "decline"
        nodes.append({
            "id": cid,
            "label": f"{entity}\n({dim})\n{cs}{pc:.1f}%",
            "color": {"background": cb, "border": cc},
            "font": {"color": "#ffffff", "size": 12, "bold": True},
            "shape": "ellipse", "size": sz,
            "title": f"{entity} [{dim}]: {cs}{pc:.1f}% of change",
            "metadata": {
                "nodeType": "contributor",
                "entity": entity, "dimension": dim,
                "delta": f"{cs}{_fmt(delta, unit)}",
                "pctOfTotalChange": round(pc, 2),
                "rank": c.get("rank", i + 1),
                "followUp": f"Why did {entity} {dir_word}?",
            },
        })
        edges.append({"from": cid, "to": "delta", "label": f"{cs}{pc:.1f}%",
                      "color": {"color": cc}, "width": max(1, int(abs(pc)/20)+1), "arrows": "to"})

    return {"nodes": nodes, "edges": edges}


def _compare_graph_json(r: dict) -> dict:
    nodes, edges = [], []
    ml = r.get("metric_label", "Metric")
    unit = r.get("metric_unit", "")
    ea = r.get("entity_a", {})
    eb = r.get("entity_b", {})
    winner = r.get("winner", "")
    pct_diff = r.get("pct_diff", 0)

    nodes.append({
        "id": "metric", "label": ml,
        "color": {"background": "#42145F", "border": "#5a2d7a"},
        "font": {"color": "#ffffff", "size": 16, "bold": True},
        "shape": "ellipse", "size": 45,
        "title": f"Metric: {ml} ({unit})",
        "metadata": {"nodeType": "metric", "name": ml, "unit": unit,
                     "description": "Metric being compared between entities"},
    })

    for eid, entity in [("entity_a", ea), ("entity_b", eb)]:
        lbl = entity.get("label", eid)
        val = entity.get("value", 0)
        is_win = lbl == winner
        bg = "#065f46" if is_win else "#7f1d1d"
        bd = "#16a34a" if is_win else "#dc2626"
        badge = " ✓" if is_win else ""
        nodes.append({
            "id": eid,
            "label": f"{lbl}{badge}\n{_fmt(val, unit)}",
            "color": {"background": bg, "border": bd},
            "font": {"color": "#ffffff", "size": 13},
            "shape": "box", "size": 35,
            "title": f"{lbl}: {_fmt(val, unit)}",
            "metadata": {
                "nodeType": "entity", "label": lbl,
                "value": val, "formattedValue": _fmt(val, unit),
                "isWinner": is_win, "unit": unit,
                "followUp": f"What drives {lbl}'s performance?" if is_win else f"Why does {lbl} underperform?",
            },
        })
        edges.append({"from": eid, "to": "metric", "label": "contributes",
                      "color": {"color": bd}, "width": 3, "arrows": "to"})

    win_id = "entity_a" if ea.get("label") == winner else "entity_b"
    los_id = "entity_b" if win_id == "entity_a" else "entity_a"
    edges.append({"from": win_id, "to": los_id, "label": f"+{pct_diff:.1f}% edge",
                  "color": {"color": "#42145F"}, "width": 2, "arrows": "to", "dashes": True})

    for i, s in enumerate(r.get("sub_breakdown_winner", [])[:3]):
        sid = f"sub{i}"
        s_entity = s.get("entity", "")
        s_dim = s.get("dimension", "")
        s_share = s.get("share_pct", 0)
        nodes.append({
            "id": sid,
            "label": f"{s_entity}\n{s_share:.1f}%",
            "color": {"background": "#1e1738", "border": "#42145F"},
            "font": {"color": "#42145F", "size": 10},
            "shape": "ellipse", "size": max(15, int(s_share * 0.3 + 14)),
            "title": f"{s_entity}: {s_share:.1f}% of {winner}",
            "metadata": {
                "nodeType": "sub", "entity": s_entity, "dimension": s_dim,
                "sharePct": round(s_share, 2),
                "followUp": f"Tell me more about {s_entity} in {winner}",
            },
        })
        edges.append({"from": sid, "to": win_id, "label": "explains",
                      "color": {"color": "#7340a0"}, "width": 1, "arrows": "to"})

    return {"nodes": nodes, "edges": edges}


def _fallback_html(message: str) -> str:
    return (
        f'<div style="font-family:Arial;font-size:13px;color:#B71C1C;'
        f'padding:12px;background:#FFEBEE;border-radius:4px;">'
        f'{message}</div>'
    )
