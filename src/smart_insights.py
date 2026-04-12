"""
smart_insights.py
Auto-discovers interesting patterns in any dataset on upload.
Pure pandas computes the numbers, then LLM writes one-sentence narratives.
"""

import os
import json
import pandas as pd
import numpy as np
from src.change_detector import _get_date_col


def generate_smart_insights(df: pd.DataFrame, profile: dict) -> list[dict]:
    """
    Run 5 lightweight analyses and return structured insights.
    Each insight has pre-computed numbers + an action_query for drill-down.
    """
    insights = []
    metrics_cfg = profile.get("metrics", {})
    dims = profile.get("dimensions", {})
    date_col = _get_date_col(profile)

    # Find primary metric (first sum-type metric)
    primary_key = None
    primary_col = None
    for k, v in metrics_cfg.items():
        if v.get("aggregation") == "sum" and v.get("column") in df.columns:
            primary_key = k
            primary_col = v["column"]
            break
    if not primary_key:
        for k, v in metrics_cfg.items():
            if v.get("column") in df.columns and v.get("column") != "derived":
                primary_key = k
                primary_col = v["column"]
                break

    if not primary_key:
        return [{"type": "info", "title": "Dataset Loaded",
                 "insight_text": f"Dataset with {len(df):,} rows and {len(df.columns)} columns ready for analysis.",
                 "metric": "", "value": len(df), "severity": "info",
                 "action_query": "Give me a summary of this data"}]

    primary_label = primary_key.replace("_", " ").title()

    # ── 1. Trend insight ────────────────────────────────────────────
    if date_col and date_col in df.columns:
        try:
            monthly = df.set_index(date_col)[primary_col].resample("ME").sum().dropna()
            if len(monthly) >= 4:
                half = len(monthly) // 2
                first_avg = monthly[:half].mean()
                second_avg = monthly[half:].mean()
                if first_avg != 0:
                    pct = (second_avg - first_avg) / abs(first_avg) * 100
                    direction = "upward" if pct > 5 else ("downward" if pct < -5 else "stable")
                    insights.append({
                        "type": "trend", "title": f"{primary_label} Trend",
                        "insight_text": f"{primary_label} shows a {direction} trend ({pct:+.1f}%) across {len(monthly)} months.",
                        "metric": primary_key, "value": round(pct, 1),
                        "severity": "warning" if abs(pct) > 20 else "info",
                        "action_query": f"How did {primary_key} change over time?",
                    })
        except Exception:
            pass

    # ── 2. Top entity insight ───────────────────────────────────────
    if dims:
        first_dim_key = list(dims.keys())[0]
        first_dim_col = dims[first_dim_key].get("column", first_dim_key)
        if first_dim_col in df.columns:
            try:
                grp = df.groupby(first_dim_col)[primary_col].sum().sort_values(ascending=False)
                total = grp.sum()
                if total > 0 and len(grp) > 0:
                    top_entity = str(grp.index[0])
                    top_share = grp.iloc[0] / total * 100
                    insights.append({
                        "type": "top", "title": f"Top {first_dim_key.replace('_', ' ').title()}",
                        "insight_text": f"{top_entity} leads in {primary_label} with {top_share:.1f}% of the total.",
                        "metric": primary_key, "value": round(top_share, 1),
                        "severity": "highlight" if top_share > 40 else "info",
                        "action_query": f"Break down {primary_key} by {first_dim_key}",
                    })
            except Exception:
                pass

    # ── 3. Anomaly insight ──────────────────────────────────────────
    try:
        series = df[primary_col].dropna()
        if len(series) > 10:
            mean = series.mean()
            std = series.std()
            if std > 0:
                anomaly_count = int(((series > mean + 2 * std) | (series < mean - 2 * std)).sum())
                anomaly_pct = anomaly_count / len(series) * 100
                if anomaly_count > 0:
                    insights.append({
                        "type": "anomaly", "title": "Anomalies Detected",
                        "insight_text": f"{anomaly_count} outlier values found in {primary_label} ({anomaly_pct:.1f}% of records exceed 2σ).",
                        "metric": primary_key, "value": anomaly_count,
                        "severity": "warning",
                        "action_query": f"Give me a summary of {primary_key}",
                    })
    except Exception:
        pass

    # ── 4. Concentration insight ────────────────────────────────────
    if dims and len(dims) > 0:
        first_dim_key = list(dims.keys())[0]
        first_dim_col = dims[first_dim_key].get("column", first_dim_key)
        if first_dim_col in df.columns:
            try:
                grp = df.groupby(first_dim_col)[primary_col].sum().sort_values(ascending=False)
                total = grp.sum()
                if total > 0 and len(grp) >= 3:
                    top3_share = grp.head(3).sum() / total * 100
                    concentration = "highly concentrated" if top3_share > 80 else ("moderately concentrated" if top3_share > 60 else "well distributed")
                    insights.append({
                        "type": "distribution", "title": f"{primary_label} Distribution",
                        "insight_text": f"Top 3 {first_dim_key.replace('_', ' ')}s account for {top3_share:.1f}% of {primary_label} — {concentration}.",
                        "metric": primary_key, "value": round(top3_share, 1),
                        "severity": "highlight" if top3_share > 80 else "info",
                        "action_query": f"What makes up total {primary_key}?",
                    })
            except Exception:
                pass

    # ── 5. Correlation insight ──────────────────────────────────────
    numeric_cols = [v["column"] for v in metrics_cfg.values()
                    if v.get("column") in df.columns and v.get("column") != "derived"]
    if len(numeric_cols) >= 2:
        try:
            corr = df[numeric_cols].corr()
            # Find strongest off-diagonal correlation
            np.fill_diagonal(corr.values, 0)
            max_idx = np.unravel_index(np.abs(corr.values).argmax(), corr.shape)
            max_corr = corr.values[max_idx]
            col_a = corr.columns[max_idx[0]]
            col_b = corr.columns[max_idx[1]]
            if abs(max_corr) > 0.5:
                direction = "positively" if max_corr > 0 else "negatively"
                insights.append({
                    "type": "correlation", "title": "Strong Correlation",
                    "insight_text": f"{col_a} and {col_b} are {direction} correlated (r={max_corr:.2f}).",
                    "metric": primary_key, "value": round(max_corr, 2),
                    "severity": "highlight",
                    "action_query": f"Compare {col_a.lower().replace(' ', '_')} and {col_b.lower().replace(' ', '_')}",
                })
        except Exception:
            pass

    # ── Fallback: dataset overview ──────────────────────────────────
    if not insights:
        total_val = df[primary_col].sum() if primary_col in df.columns else 0
        insights.append({
            "type": "info", "title": "Dataset Overview",
            "insight_text": f"Dataset has {len(df):,} records. Total {primary_label}: {total_val:,.0f}.",
            "metric": primary_key, "value": total_val,
            "severity": "info",
            "action_query": f"Give me a summary of {primary_key}",
        })

    return insights[:5]
