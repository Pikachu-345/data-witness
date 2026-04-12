"""
breakdown.py
Decomposes a metric into its dimensional components.
Pure pandas. No LLM. Answers "What makes up total sales?"

Ports from the starter version:
  - Structured error handling (_error_result pattern)
  - Flexible dimension resolution (YAML key / column name / case-insensitive)
  - Outlier detection (mean + 2σ)
  - Deterministic analyst narrative (4-sentence, unit-aware)
  - Plotly bar chart (top contributor highlighted)
  - 3-band data-quality confidence scoring
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.change_detector import _get_date_col, _filter_period, _apply_metric

# ── Thresholds (module-level, easy to tune) ───────────────────────────────────
_TOP_CONTRIBUTOR_THRESHOLD = 0.40   # ≥ 40 % share → "dominant driver"
_CONCENTRATION_THRESHOLD = 0.70     # top-3 cumulative ≥ 70 % → high concentration
_OUTLIER_SIGMA = 2.0                # values > mean + n·σ flagged
_HIGH_CONFIDENCE_MIN_ROWS = 30      # minimum rows for "High Confidence"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_dimension_column(
    dimension: str,
    dims_cfg: dict,
    df_columns: list[str],
) -> str:
    """
    Accept a YAML key ("region"), an actual column name ("Region"), or a
    case-insensitive variant. Returns the resolved column name as it appears
    in the DataFrame.
    """
    if dimension in df_columns:
        return dimension

    lower_map = {c.lower(): c for c in df_columns}
    if dimension.lower() in lower_map:
        return lower_map[dimension.lower()]

    for key, meta in dims_cfg.items():
        if key.lower() == dimension.lower():
            col = meta.get("column", "")
            if col in df_columns:
                return col

    return dimension


def _format_value(value: float, unit: str) -> str:
    if unit == "USD":
        return f"${value:,.0f}"
    if unit == "percent":
        return f"{value:.1f}%"
    if unit == "ratio":
        return f"{value:.3f}"
    return f"{value:,.0f}"


def _enrich_with_percentages(table: pd.DataFrame, metric_col: str) -> pd.DataFrame:
    table = table.copy()
    total = table[metric_col].sum()
    if total == 0:
        table["% Contribution"] = 0.0
        table["Cumulative %"] = 0.0
    else:
        table["% Contribution"] = (table[metric_col] / total * 100).round(2)
        table["Cumulative %"] = table["% Contribution"].cumsum().round(2)
    return table


# ── Pattern Detection ─────────────────────────────────────────────────────────

def _detect_patterns(
    table: pd.DataFrame,
    dimension_col: str,
    metric_col: str,
) -> dict:
    values = table[metric_col].to_numpy(dtype=float)
    pcts = table["% Contribution"].to_numpy(dtype=float)
    names = table[dimension_col].tolist()

    top_contributor = {
        "name": names[0],
        "value": float(values[0]),
        "pct": float(pcts[0]),
        "rank": 1,
        "is_dominant": float(pcts[0]) >= _TOP_CONTRIBUTOR_THRESHOLD * 100,
    }

    top_n = min(3, len(table))
    top_n_pct = float(pcts[:top_n].sum())
    concentration = {
        "top_n": top_n,
        "cumulative_pct": round(top_n_pct, 2),
        "is_high": top_n_pct >= _CONCENTRATION_THRESHOLD * 100,
        "groups": names[:top_n],
    }

    mean_val = float(np.mean(values))
    std_val = float(np.std(values))
    threshold = mean_val + _OUTLIER_SIGMA * std_val
    outlier_mask = values > threshold
    outliers = {
        "names": [n for n, m in zip(names, outlier_mask) if m],
        "values": [float(v) for v, m in zip(values, outlier_mask) if m],
        "threshold": round(threshold, 2),
        "mean": round(mean_val, 2),
        "std": round(std_val, 2),
    }

    return {
        "top_contributor": top_contributor,
        "concentration": concentration,
        "outliers": outliers,
    }


# ── Narrative Generation ──────────────────────────────────────────────────────

def _generate_narrative(
    insights: dict,
    metric: str,
    dimension_col: str,
    unit: str,
    total_value: float,
) -> str:
    top = insights["top_contributor"]
    conc = insights["concentration"]
    outs = insights["outliers"]
    sentences = []

    dominant_tag = " — making it the dominant driver" if top["is_dominant"] else ""
    sentences.append(
        f"{top['name']} {dimension_col} contributes {top['pct']:.1f}% of total {metric} "
        f"({_format_value(top['value'], unit)}){dominant_tag}."
    )

    if conc["top_n"] > 1:
        groups = conc["groups"]
        if len(groups) == 2:
            group_str = f"{groups[0]} and {groups[1]}"
        else:
            group_str = ", ".join(groups[:-1]) + f", and {groups[-1]}"
        conc_label = "a high concentration" if conc["is_high"] else "a moderate spread"
        sentences.append(
            f"The top {conc['top_n']} {dimension_col} groups ({group_str}) together "
            f"account for {conc['cumulative_pct']:.1f}%, indicating {conc_label} of {metric}."
        )

    if outs["names"]:
        is_plural = len(outs["names"]) > 1
        out_list = ", ".join(outs["names"])
        verb = "show" if is_plural else "shows"
        sentences.append(
            f"{out_list} {verb} unusually high {metric} "
            f"(above {_format_value(outs['threshold'], unit)}), "
            f"exceeding the expected range by more than {_OUTLIER_SIGMA:.0f} "
            f"standard deviations from the mean ({_format_value(outs['mean'], unit)})."
        )
    else:
        sentences.append(
            f"No significant outliers detected — values across {dimension_col} groups "
            f"are within {_OUTLIER_SIGMA:.0f} standard deviations of the mean "
            f"({_format_value(outs['mean'], unit)})."
        )

    sentences.append(
        f"Total {metric} across all {dimension_col} groups: "
        f"{_format_value(total_value, unit)}."
    )
    return " ".join(sentences)


# ── Visualization ─────────────────────────────────────────────────────────────

def _build_chart(
    table: pd.DataFrame,
    dimension_col: str,
    metric_col: str,
    metric_label: str,
    top_contributor_name: str,
) -> go.Figure:
    bar_colors = [
        "#4B0082" if str(name) == str(top_contributor_name) else "#9E9AC8"
        for name in table[dimension_col]
    ]

    fig = go.Figure(
        go.Bar(
            x=table[dimension_col].astype(str),
            y=table[metric_col],
            marker_color=bar_colors,
            text=table["% Contribution"].apply(lambda p: f"{p:.1f}%"),
            textposition="outside",
            textfont=dict(size=12, color="#444444"),
            cliponaxis=False,
            hovertemplate=(
                "<b>%{x}</b><br>"
                f"{metric_col}: %{{y:,.2f}}<br>"
                "Share: %{text}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text=f"<b>{metric_label} by {dimension_col}</b>",
            font=dict(size=16, color="#222222", family="Arial, sans-serif"),
            x=0.0, xanchor="left",
        ),
        xaxis=dict(
            title=dict(text=dimension_col, font=dict(size=13)),
            tickfont=dict(size=12),
            tickangle=-20 if len(table) > 5 else 0,
            showgrid=False,
        ),
        yaxis=dict(
            title=dict(text=metric_col, font=dict(size=13)),
            tickfont=dict(size=11),
            showgrid=True, gridcolor="#F0F0F0", zeroline=False,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        margin=dict(t=70, b=60, l=70, r=30),
        height=430,
        bargap=0.35,
    )

    max_y = float(table[metric_col].max())
    fig.update_yaxes(range=[0, max_y * 1.18])
    return fig


# ── Confidence Scoring ────────────────────────────────────────────────────────

def _compute_confidence(df: pd.DataFrame, metric_col: str) -> dict:
    total_rows = len(df)
    missing_count = int(df[metric_col].isna().sum()) if metric_col in df.columns else 0
    missing_pct = missing_count / total_rows if total_rows > 0 else 1.0

    if missing_pct == 0.0 and total_rows >= _HIGH_CONFIDENCE_MIN_ROWS:
        score = min(95, 75 + min(20, total_rows // 200))
        label, color = "High Confidence", "green"
        explanation = (
            f"No missing values in '{metric_col}' across {total_rows:,} rows. "
            "Aggregation is statistically reliable."
        )
    elif missing_pct < 0.05 and total_rows >= 15:
        score = 65
        label, color = "Medium Confidence", "orange"
        explanation = (
            f"{missing_count} missing value(s) in '{metric_col}' "
            f"({missing_pct:.1%} of {total_rows:,} rows). "
            "Results may slightly undercount the true total."
        )
    else:
        score = 40
        label, color = "Low Confidence", "red"
        explanation = (
            f"Data quality concern: {missing_count} missing value(s) "
            f"({missing_pct:.1%}) across {total_rows} rows. "
            "Treat this breakdown as indicative only."
        )

    return {"score": score, "label": label, "color": color, "explanation": explanation}


# ── Error Response ────────────────────────────────────────────────────────────

def _error_result(message: str, metric_key: str = "", metric_label: str = "", unit: str = "") -> dict:
    return {
        "type": "breakdown",
        "success": False,
        "metric": metric_key,
        "metric_label": metric_label,
        "metric_unit": unit,
        "dimension": None,
        "dimension_label": "",
        "total_value": 0,
        "components": [],
        "top_3_share_pct": 0,
        "concentration": "unknown",
        "component_count": 0,
        "data_quality": {"total_rows": 0},
        "table": pd.DataFrame(),
        "insights": {},
        "chart": None,
        "narrative": "",
        "trust": {},
        "error": message,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def decompose_metric(
    df: pd.DataFrame,
    metric_key: str,
    dimension: str | None,
    time_period: dict | None,
    metrics_config: dict,
    filters: dict | None = None,
) -> dict:
    """
    Break down a metric by a dimension.

    Returns a dict with both the original component-list format (for
    reasoning_engine / knowledge_graph compatibility) AND the enriched
    fields ported from the starter: table, insights, chart, narrative, trust.
    """
    metric_meta = metrics_config.get("metrics", {}).get(metric_key, {})
    if not metric_meta:
        available = list(metrics_config.get("metrics", {}).keys())
        return _error_result(
            f"Unknown metric '{metric_key}'. Available metrics: {available}.",
            metric_key=metric_key,
        )

    metric_label = metric_key.replace("_", " ").title()
    unit = metric_meta.get("unit", "value")
    column = metric_meta.get("column", "")
    aggregation = metric_meta.get("aggregation", "sum")
    dims = metrics_config.get("dimensions", {})

    if not isinstance(df, pd.DataFrame) or df.empty:
        return _error_result("The DataFrame is empty — nothing to analyse.", metric_key, metric_label, unit)

    # Validate metric column exists (skip for derived)
    if aggregation != "derived" and column and column != "derived" and column not in df.columns:
        return _error_result(
            f"Metric column '{column}' not found. Available: {list(df.columns)}.",
            metric_key, metric_label, unit,
        )

    # Filter by time period if given
    date_col = _get_date_col(metrics_config)
    if time_period and date_col:
        sliced = _filter_period(df, time_period, date_col, filters)
    else:
        sliced = df.copy()
        if filters:
            for col, val in filters.items():
                if col in sliced.columns:
                    sliced = sliced[sliced[col].str.lower() == str(val).lower()]

    total = _apply_metric(sliced, metric_key, metrics_config)

    # Resolve dimension
    if not dimension:
        dimension = list(dims.keys())[0] if dims else None
    if not dimension:
        return _error_result("No dimension specified and none found in config.", metric_key, metric_label, unit)

    dim_col = _resolve_dimension_column(dimension, dims, list(sliced.columns))
    if dim_col not in sliced.columns:
        return _error_result(
            f"Dimension '{dimension}' could not be resolved. Available: {list(sliced.columns)}.",
            metric_key, metric_label, unit,
        )

    # Aggregate
    if aggregation == "derived":
        formula = metric_meta.get("formula", {})
        num_col = formula.get("numerator", "Profit")
        den_col = formula.get("denominator", "Sales")
        mult = formula.get("multiply", 100)
        if num_col in sliced.columns and den_col in sliced.columns:
            grp = sliced.groupby(dim_col).agg(
                num_sum=(num_col, "sum"), den_sum=(den_col, "sum")
            ).reset_index()
            grp[metric_key] = grp.apply(
                lambda r: (r["num_sum"] / r["den_sum"] * mult) if r["den_sum"] != 0 else 0.0, axis=1
            )
            grp = grp[[dim_col, metric_key]]
            display_col = metric_key
        else:
            return _error_result(
                f"Derived metric '{metric_key}' requires columns '{num_col}' and '{den_col}'.",
                metric_key, metric_label, unit,
            )
    elif column and column in sliced.columns:
        if aggregation == "count_distinct":
            grp = sliced.groupby(dim_col)[column].nunique().reset_index(name=column)
        elif aggregation == "mean":
            grp = sliced.groupby(dim_col)[column].mean().reset_index()
        elif aggregation == "count":
            grp = sliced.groupby(dim_col)[column].count().reset_index()
        else:
            grp = sliced.groupby(dim_col)[column].sum().reset_index()
        display_col = column
    else:
        return _error_result(
            f"Cannot aggregate metric '{metric_key}'.", metric_key, metric_label, unit,
        )

    grp = grp.sort_values(display_col, ascending=False).reset_index(drop=True)

    if grp.empty:
        return _error_result(
            f"No rows after grouping '{metric_key}' by '{dim_col}'.", metric_key, metric_label, unit,
        )

    # Enrich with percentages
    table = _enrich_with_percentages(grp, display_col)
    total_value = float(table[display_col].sum())

    # Pattern detection
    insights = _detect_patterns(table, dim_col, display_col)

    # Narrative
    narrative = _generate_narrative(insights, metric_key, dim_col, unit, total_value)

    # Chart
    chart = _build_chart(table, dim_col, display_col, metric_label, insights["top_contributor"]["name"])

    # Confidence
    conf_col = "Profit" if aggregation == "derived" else (column if column in df.columns else display_col)
    confidence = _compute_confidence(df, conf_col)
    trust = {
        "metric_definition": {
            "name": metric_key,
            "column": metric_meta.get("column", ""),
            "definition": metric_meta.get("definition", ""),
            "unit": unit,
            "aggregation": aggregation,
        },
        "confidence": confidence,
    }

    # Build backward-compatible components list
    components = []
    for _, row in table.iterrows():
        components.append({
            "entity": str(row[dim_col]),
            "dimension": dimension,
            "value": float(row[display_col]),
            "share_pct": round(float(row["% Contribution"]), 2),
            "rank": int(row.name) + 1,
        })

    top_3_share = sum(c["share_pct"] for c in components[:3])
    conc_label = (
        "highly concentrated" if top_3_share > 80
        else "moderately concentrated" if top_3_share > 60
        else "well distributed"
    )

    return {
        "type": "breakdown",
        "success": True,
        "error": None,
        # Original fields (reasoning_engine / knowledge_graph compatibility)
        "metric": metric_key,
        "metric_label": metric_label,
        "metric_unit": unit,
        "dimension": dimension,
        "dimension_label": dimension.replace("_", " ").title(),
        "total_value": total,
        "components": components,
        "top_3_share_pct": round(top_3_share, 1),
        "concentration": conc_label,
        "component_count": len(components),
        "data_quality": {
            "total_rows": len(sliced),
            "missing_values": int(sliced[conf_col].isna().sum()) if conf_col in sliced.columns else 0,
        },
        # Enriched fields (ported from starter)
        "table": table,
        "insights": insights,
        "chart": chart,
        "narrative": narrative,
        "trust": trust,
    }
