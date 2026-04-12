"""
summarizer.py
Generates statistical summaries with trend detection and anomaly flagging.
Pure pandas. No LLM. Answers "Give me a summary of performance."
"""

import pandas as pd
import numpy as np
from src.change_detector import _get_date_col


def summarize_dataset(
    df: pd.DataFrame,
    metric_key: str | None,
    metrics_config: dict,
    time_period: dict | None = None,
) -> dict:
    """
    Produce a rich statistical summary of one or all metrics.
    Includes: stats, trends, anomalies, top/bottom performers.
    """
    date_col = _get_date_col(metrics_config)
    metrics_cfg = metrics_config.get("metrics", {})
    dims = metrics_config.get("dimensions", {})

    # Filter by time if given
    sliced = df.copy()
    if time_period and date_col and date_col in sliced.columns:
        start = time_period.get("start")
        end = time_period.get("end")
        if start:
            sliced = sliced[sliced[date_col] >= pd.Timestamp(start)]
        if end:
            sliced = sliced[sliced[date_col] <= pd.Timestamp(end)]

    # If specific metric requested, focus on it; else summarize all
    if metric_key and metric_key in metrics_cfg:
        target_metrics = {metric_key: metrics_cfg[metric_key]}
    else:
        # Use all non-derived, non-count metrics
        target_metrics = {
            k: v for k, v in metrics_cfg.items()
            if v.get("aggregation") not in ("derived", "count_distinct")
        }

    metric_summaries = []
    for mkey, mmeta in target_metrics.items():
        col = mmeta.get("column", "")
        if col not in sliced.columns or col == "derived":
            continue
        series = sliced[col].dropna()
        if series.empty:
            continue

        stats = {
            "metric": mkey,
            "metric_label": mkey.replace("_", " ").title(),
            "unit": mmeta.get("unit", "value"),
            "count": int(len(series)),
            "sum": round(float(series.sum()), 2),
            "mean": round(float(series.mean()), 2),
            "median": round(float(series.median()), 2),
            "std": round(float(series.std()), 2),
            "min": round(float(series.min()), 2),
            "max": round(float(series.max()), 2),
            "q25": round(float(series.quantile(0.25)), 2),
            "q75": round(float(series.quantile(0.75)), 2),
        }

        # Coefficient of variation (volatility)
        if stats["mean"] != 0:
            stats["cv"] = round(stats["std"] / abs(stats["mean"]) * 100, 1)
        else:
            stats["cv"] = 0.0

        # Anomaly detection (values beyond 2 std devs)
        threshold_high = stats["mean"] + 2 * stats["std"]
        threshold_low = stats["mean"] - 2 * stats["std"]
        anomaly_count = int(((series > threshold_high) | (series < threshold_low)).sum())
        stats["anomaly_count"] = anomaly_count
        stats["anomaly_pct"] = round(anomaly_count / len(series) * 100, 1) if len(series) > 0 else 0

        metric_summaries.append(stats)

    # Time trend (if date column exists)
    trend = None
    if date_col and date_col in sliced.columns and metric_summaries:
        primary_metric = metric_summaries[0]
        primary_col = metrics_cfg.get(primary_metric["metric"], {}).get("column", "")
        if primary_col and primary_col in sliced.columns:
            trend = _compute_trend(sliced, date_col, primary_col)

    # Top/bottom by first dimension
    top_bottom = None
    if dims and metric_summaries:
        first_dim_key = list(dims.keys())[0]
        first_dim_col = dims[first_dim_key].get("column", first_dim_key)
        primary_col = metrics_cfg.get(metric_summaries[0]["metric"], {}).get("column", "")
        if first_dim_col in sliced.columns and primary_col and primary_col in sliced.columns:
            top_bottom = _top_bottom(sliced, first_dim_col, primary_col, first_dim_key)

    return {
        "type": "summarize",
        "metric_summaries": metric_summaries,
        "trend": trend,
        "top_bottom": top_bottom,
        "row_count": len(sliced),
        "data_quality": {
            "total_rows": len(sliced),
            "null_pct": round(sliced.isnull().sum().sum() / (len(sliced) * len(sliced.columns)) * 100, 1) if len(sliced) > 0 else 0,
        },
    }


def _compute_trend(df: pd.DataFrame, date_col: str, value_col: str) -> dict | None:
    """Detect monthly trend direction and magnitude."""
    try:
        monthly = df.set_index(date_col)[value_col].resample("ME").sum().dropna()
        if len(monthly) < 2:
            return None

        first_half = monthly[:len(monthly)//2].mean()
        second_half = monthly[len(monthly)//2:].mean()

        if first_half != 0:
            pct = (second_half - first_half) / abs(first_half) * 100
        else:
            pct = 0

        direction = "upward" if pct > 5 else ("downward" if pct < -5 else "stable")

        return {
            "direction": direction,
            "pct_change": round(pct, 1),
            "periods": len(monthly),
            "first_half_avg": round(first_half, 2),
            "second_half_avg": round(second_half, 2),
        }
    except Exception:
        return None


def _top_bottom(df: pd.DataFrame, dim_col: str, val_col: str, dim_key: str) -> dict:
    """Find top and bottom performers by a dimension."""
    grp = df.groupby(dim_col)[val_col].sum().sort_values(ascending=False)
    total = grp.sum()

    top = []
    for entity, val in grp.head(3).items():
        top.append({
            "entity": str(entity),
            "dimension": dim_key,
            "value": round(float(val), 2),
            "share_pct": round(float(val / total * 100), 1) if total != 0 else 0,
        })

    bottom = []
    for entity, val in grp.tail(3).items():
        bottom.append({
            "entity": str(entity),
            "dimension": dim_key,
            "value": round(float(val), 2),
            "share_pct": round(float(val / total * 100), 1) if total != 0 else 0,
        })

    return {"top": top, "bottom": bottom, "dimension": dim_key}
