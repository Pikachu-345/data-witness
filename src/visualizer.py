"""
visualizer.py
Handles all chart rendering from Pandas results.
Person B owns this file.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def render_chart(result: any, question: str) -> go.Figure | None:
    """
    Auto-detect the best chart type for the result and render it.
    Returns a Plotly figure or None if no chart is appropriate.
    """
    if result is None:
        return None

    # Scalar result — no chart needed
    if isinstance(result, (int, float)):
        return _make_single_value_chart(result, question)

    if not isinstance(result, pd.DataFrame) or result.empty:
        return None

    df = result.copy()
    cols = list(df.columns)

    # Exactly 2 columns: one categorical, one numeric → bar chart
    if len(cols) == 2:
        cat_cols = df.select_dtypes(include="object").columns.tolist()
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if cat_cols and num_cols:
            return _bar_chart(df, x=cat_cols[0], y=num_cols[0], question=question)

    # Date column present → line chart
    date_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()
    if date_cols:
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            return _line_chart(df, x=date_cols[0], y=num_cols[0], question=question)

    # 3 columns with 2 categoricals + 1 numeric → grouped bar
    if len(cols) == 3:
        cat_cols = df.select_dtypes(include="object").columns.tolist()
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if len(cat_cols) >= 2 and num_cols:
            return _grouped_bar(df, x=cat_cols[0], y=num_cols[0], color=cat_cols[1], question=question)

    # Multiple numeric columns → try a bar chart on the first numeric
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    if cat_cols and num_cols:
        return _bar_chart(df, x=cat_cols[0], y=num_cols[0], question=question)

    return None


def _bar_chart(df: pd.DataFrame, x: str, y: str, question: str) -> go.Figure:
    fig = px.bar(
        df, x=x, y=y,
        title=f"",
        color=y,
        color_continuous_scale="Purples",
        text_auto=".2s",
    )
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=13),
        coloraxis_showscale=False,
        margin=dict(t=20, b=40, l=40, r=20),
    )
    fig.update_traces(textposition="outside")
    return fig


def _line_chart(df: pd.DataFrame, x: str, y: str, question: str) -> go.Figure:
    fig = px.line(
        df, x=x, y=y,
        title="",
        markers=True,
        color_discrete_sequence=["#4B0082"],
    )
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=13),
        margin=dict(t=20, b=40, l=40, r=20),
    )
    return fig


def _grouped_bar(df: pd.DataFrame, x: str, y: str, color: str, question: str) -> go.Figure:
    fig = px.bar(
        df, x=x, y=y, color=color,
        barmode="group",
        title="",
        color_discrete_sequence=px.colors.sequential.Purples_r,
    )
    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=13),
        margin=dict(t=20, b=40, l=40, r=20),
    )
    return fig


def _make_single_value_chart(value: float, question: str) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="number",
        value=value,
        number={"font": {"size": 64, "color": "#4B0082", "family": "Arial"}},
    ))
    fig.update_layout(
        height=200,
        margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor="white",
    )
    return fig


# ── Reasoning Layer Charts ────────────────────────────────────────────────────

def render_comparison_chart(compare_result: dict) -> go.Figure:
    """
    Grouped bar chart comparing entity_a vs entity_b on a metric.
    Works for both entity comparisons and time period comparisons.
    """
    ea = compare_result.get("entity_a", {})
    eb = compare_result.get("entity_b", {})
    metric_label = compare_result.get("metric_label", "Value")
    unit = compare_result.get("metric_unit", "")
    winner = compare_result.get("winner", "")

    labels = [ea.get("label", "A"), eb.get("label", "B")]
    values = [ea.get("value", 0), eb.get("value", 0)]
    colors = [
        "#1B5E20" if labels[0] == winner else "#B71C1C",
        "#1B5E20" if labels[1] == winner else "#B71C1C",
    ]

    fig = go.Figure(go.Bar(
        x=labels,
        y=values,
        marker_color=colors,
        text=[f"{v:,.2f}" for v in values],
        textposition="outside",
        textfont=dict(size=13, family="Arial"),
        hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
    ))

    y_max = max(values) * 1.2 if max(values) > 0 else 1
    fig.update_layout(
        title=dict(
            text=f"{metric_label} Comparison ({unit})" if unit else f"{metric_label} Comparison",
            font=dict(size=14, color="#4B0082", family="Arial"),
        ),
        yaxis=dict(
            title=f"{metric_label} ({unit})" if unit else metric_label,
            range=[0, y_max],
            gridcolor="#F0E8FF",
        ),
        xaxis=dict(title=""),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=12),
        margin=dict(t=50, b=40, l=60, r=20),
        showlegend=False,
    )
    return fig


def render_waterfall_chart(change_result: dict) -> go.Figure:
    """
    Plotly waterfall chart showing:
    Period A total → top contributors → Period B total.
    Positive deltas green, negative red, totals purple.
    """
    pa = change_result.get("period_a", {})
    pb = change_result.get("period_b", {})
    contributors = change_result.get("contributors", [])[:5]
    metric_label = change_result.get("metric_label", "Value")
    unit = change_result.get("metric_unit", "")

    x_labels = [pa.get("label", "Before")]
    y_values = [pa.get("value", 0)]
    measures = ["absolute"]
    text_vals = [f"{pa.get('value', 0):,.0f}"]
    colors_list = ["#4B0082"]

    for c in contributors:
        delta = c.get("delta", 0)
        entity = c.get("entity", "")
        dim = c.get("dimension", "")
        label = f"{entity}\n({dim})"
        x_labels.append(label)
        y_values.append(delta)
        measures.append("relative")
        sign = "+" if delta >= 0 else ""
        text_vals.append(f"{sign}{delta:,.0f}")
        colors_list.append("#2E7D32" if delta >= 0 else "#C62828")

    x_labels.append(pb.get("label", "After"))
    y_values.append(pb.get("value", 0))
    measures.append("total")
    text_vals.append(f"{pb.get('value', 0):,.0f}")
    colors_list.append("#4B0082")

    fig = go.Figure(go.Waterfall(
        name="",
        orientation="v",
        measure=measures,
        x=x_labels,
        y=y_values,
        text=text_vals,
        textposition="outside",
        textfont=dict(size=10, family="Arial"),
        connector={"line": {"color": "#BDBDBD", "width": 1, "dash": "dot"}},
        increasing={"marker": {"color": "#2E7D32"}},
        decreasing={"marker": {"color": "#C62828"}},
        totals={"marker": {"color": "#4B0082"}},
        hovertemplate="%{x}: %{y:,.2f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=f"{metric_label} Waterfall ({unit})" if unit else f"{metric_label} Waterfall",
            font=dict(size=14, color="#4B0082", family="Arial"),
        ),
        yaxis=dict(
            title=f"{metric_label} ({unit})" if unit else metric_label,
            gridcolor="#F0E8FF",
        ),
        xaxis=dict(title=""),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=11),
        margin=dict(t=50, b=80, l=60, r=20),
        showlegend=False,
    )
    return fig


def render_contributor_bar(contributors: list[dict], metric_key: str) -> go.Figure:
    """
    Horizontal bar chart of top contributors ranked by absolute contribution percentage.
    Green bars for positive contributors, red for negative.
    """
    if not contributors:
        return go.Figure()

    top = sorted(contributors, key=lambda c: abs(c.get("pct_of_total_change", 0)), reverse=True)[:8]

    labels = [f"{c.get('entity', '')} ({c.get('dimension', '')})" for c in top]
    pcts = [c.get("pct_of_total_change", 0) for c in top]
    deltas = [c.get("delta", 0) for c in top]
    colors = ["#2E7D32" if p >= 0 else "#C62828" for p in pcts]

    fig = go.Figure(go.Bar(
        x=pcts,
        y=labels,
        orientation="h",
        marker_color=colors,
        text=[f"{'+' if p >= 0 else ''}{p:.1f}%" for p in pcts],
        textposition="outside",
        textfont=dict(size=11, family="Arial"),
        customdata=deltas,
        hovertemplate="%{y}: %{x:.1f}% of change (delta: %{customdata:,.2f})<extra></extra>",
    ))

    x_range = max(abs(min(pcts)), abs(max(pcts))) if pcts else 10
    fig.update_layout(
        title=dict(
            text="Top Contributors to Change",
            font=dict(size=14, color="#4B0082", family="Arial"),
        ),
        xaxis=dict(
            title="% of Total Change",
            range=[-(x_range * 1.3), x_range * 1.3],
            zeroline=True,
            zerolinecolor="#757575",
            gridcolor="#F0E8FF",
        ),
        yaxis=dict(title="", autorange="reversed"),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Arial", size=11),
        margin=dict(t=50, b=40, l=180, r=80),
        height=max(300, len(top) * 45 + 80),
        showlegend=False,
    )
    return fig
