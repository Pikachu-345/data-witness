"""
change_detector.py
Pure pandas. No LLM. Detects metric change across two time periods and
ranks contributor entities by their impact on the total change.
"""

import pandas as pd


def detect_change(
    df: pd.DataFrame,
    metric_key: str,
    period_a: dict,
    period_b: dict,
    metrics_config: dict,
    filters: dict | None = None,
) -> dict:
    """
    Master function for change detection.

    Returns a change_result dict with:
    - period values (computed by pandas)
    - absolute and percentage change
    - ranked contributor list across all dimensions
    - per-dimension contributor breakdown
    - data quality metadata
    """
    metric_meta = metrics_config.get("metrics", {}).get(metric_key, {})
    metric_label = metric_meta.get("column", metric_key.capitalize())
    metric_unit = metric_meta.get("unit", "")

    val_a = _compute_metric_for_period(df, metric_key, period_a, metrics_config, filters)
    val_b = _compute_metric_for_period(df, metric_key, period_b, metrics_config, filters)

    absolute_change = val_b - val_a
    pct_change = (absolute_change / val_a * 100) if val_a != 0 else 0.0
    if absolute_change > 0:
        direction = "increase"
    elif absolute_change < 0:
        direction = "decrease"
    else:
        direction = "no_change"

    top_contributors_by_dimension, flat_contributors = _compute_contributors(
        df, metric_key, period_a, period_b, metrics_config, absolute_change, filters
    )

    # Row counts for data quality
    date_col = _get_date_col(metrics_config)
    rows_a = _filter_period(df, period_a, date_col, filters).shape[0]
    rows_b = _filter_period(df, period_b, date_col, filters).shape[0]

    return {
        "type": "change",
        "metric": metric_key,
        "metric_label": metric_label,
        "metric_unit": metric_unit,
        "period_a": {**period_a, "value": round(val_a, 2)},
        "period_b": {**period_b, "value": round(val_b, 2)},
        "absolute_change": round(absolute_change, 2),
        "pct_change": round(pct_change, 2),
        "direction": direction,
        "contributors": flat_contributors,
        "top_contributors_by_dimension": top_contributors_by_dimension,
        "data_quality": {
            "period_a_rows": rows_a,
            "period_b_rows": rows_b,
            "missing_dates": rows_a == 0 or rows_b == 0,
        },
    }


def _compute_metric_for_period(
    df: pd.DataFrame,
    metric_key: str,
    period: dict,
    metrics_config: dict,
    filters: dict | None = None,
) -> float:
    """
    Filter df to the given period and compute the metric.
    Handles: sum, count_distinct, mean, derived (profit_margin).
    Returns 0.0 if no data in the period.
    """
    date_col = _get_date_col(metrics_config)
    sliced = _filter_period(df, period, date_col, filters)

    if sliced.empty:
        return 0.0

    return _apply_metric(sliced, metric_key, metrics_config)


def _apply_metric(sliced: pd.DataFrame, metric_key: str, metrics_config: dict) -> float:
    """Apply the metric aggregation to a sliced dataframe. Returns float."""
    metric_meta = metrics_config.get("metrics", {}).get(metric_key, {})
    aggregation = metric_meta.get("aggregation", "sum")
    column = metric_meta.get("column", "")

    if aggregation == "derived":
        # Generic derived metric: uses formula dict from profile/metrics.yaml
        formula = metric_meta.get("formula", {})
        num_col = formula.get("numerator", "")
        den_col = formula.get("denominator", "")
        mult = formula.get("multiply", 1)
        num_val = sliced[num_col].sum() if num_col and num_col in sliced.columns else 0
        den_val = sliced[den_col].sum() if den_col and den_col in sliced.columns else 0
        return (num_val / den_val * mult) if den_val != 0 else 0.0

    if column not in sliced.columns:
        return 0.0

    if aggregation == "sum":
        return float(sliced[column].sum())
    elif aggregation == "count_distinct":
        return float(sliced[column].nunique())
    elif aggregation == "mean":
        return float(sliced[column].mean())
    else:
        return float(sliced[column].sum())


def _compute_contributors(
    df: pd.DataFrame,
    metric_key: str,
    period_a: dict,
    period_b: dict,
    metrics_config: dict,
    total_change: float,
    filters: dict | None = None,
    top_n: int = 10,
) -> tuple[dict, list]:
    """
    For each dimension in metrics_config, group by that dimension's column,
    compute the metric for both periods, calculate per-entity delta,
    and rank by absolute delta.

    Returns (top_contributors_by_dimension, flat_global_contributors).
    flat list is deduplicated and globally ranked by abs(delta).
    """
    date_col = _get_date_col(metrics_config)
    sliced_a = _filter_period(df, period_a, date_col, filters)
    sliced_b = _filter_period(df, period_b, date_col, filters)

    dimensions = metrics_config.get("dimensions", {})
    top_by_dim: dict[str, list] = {}
    all_contributors: list[dict] = []

    for dim_key, dim_meta in dimensions.items():
        dim_col = dim_meta.get("column", "")
        if not dim_col or dim_col not in df.columns:
            continue

        # Skip very high cardinality dims for speed (state/city/product capped separately)
        contrib_a = _groupby_metric(sliced_a, dim_col, metric_key, metrics_config)
        contrib_b = _groupby_metric(sliced_b, dim_col, metric_key, metrics_config)

        merged = contrib_a.merge(contrib_b, on=dim_col, how="outer", suffixes=("_a", "_b"))
        merged = merged.fillna(0)
        merged["delta"] = merged["value_b"] - merged["value_a"]
        merged["pct_of_total_change"] = (
            (merged["delta"] / total_change * 100) if total_change != 0 else 0.0
        )
        merged = merged.reindex(
            merged["delta"].abs().sort_values(ascending=False).index
        ).head(top_n).reset_index(drop=True)

        dim_contributors = []
        for i, row in merged.iterrows():
            c = {
                "dimension": dim_key,
                "entity": str(row[dim_col]),
                "value_a": round(float(row["value_a"]), 2),
                "value_b": round(float(row["value_b"]), 2),
                "delta": round(float(row["delta"]), 2),
                "pct_of_total_change": round(float(row["pct_of_total_change"]), 2),
            }
            dim_contributors.append(c)
            all_contributors.append(c)

        top_by_dim[dim_key] = dim_contributors

    # Global rank by abs(delta), deduplication not needed (different dimensions)
    all_contributors.sort(key=lambda x: abs(x["delta"]), reverse=True)
    for i, c in enumerate(all_contributors):
        c["rank"] = i + 1

    return top_by_dim, all_contributors[:top_n]


def _groupby_metric(
    sliced: pd.DataFrame,
    dim_col: str,
    metric_key: str,
    metrics_config: dict,
) -> pd.DataFrame:
    """
    Group sliced df by dim_col and compute the metric per group.
    Returns a DataFrame with columns [dim_col, 'value'].
    """
    if sliced.empty or dim_col not in sliced.columns:
        return pd.DataFrame(columns=[dim_col, "value"])

    metric_meta = metrics_config.get("metrics", {}).get(metric_key, {})
    aggregation = metric_meta.get("aggregation", "sum")
    column = metric_meta.get("column", "")

    if aggregation == "derived":
        formula = metric_meta.get("formula", {})
        num_col = formula.get("numerator", "")
        den_col = formula.get("denominator", "")
        mult = formula.get("multiply", 1)
        if not num_col or not den_col or num_col not in sliced.columns or den_col not in sliced.columns:
            return pd.DataFrame(columns=[dim_col, "value"])
        grp = sliced.groupby(dim_col).agg(
            num_sum=(num_col, "sum"),
            den_sum=(den_col, "sum"),
        ).reset_index()
        grp["value"] = grp.apply(
            lambda r: (r["num_sum"] / r["den_sum"] * mult) if r["den_sum"] != 0 else 0.0,
            axis=1,
        )
        return grp[[dim_col, "value"]]

    if column not in sliced.columns:
        return pd.DataFrame(columns=[dim_col, "value"])

    if aggregation == "sum":
        grp = sliced.groupby(dim_col)[column].sum().reset_index()
    elif aggregation == "count_distinct":
        grp = sliced.groupby(dim_col)[column].nunique().reset_index()
    elif aggregation == "mean":
        grp = sliced.groupby(dim_col)[column].mean().reset_index()
    else:
        grp = sliced.groupby(dim_col)[column].sum().reset_index()

    grp = grp.rename(columns={column: "value"})
    return grp[[dim_col, "value"]]


def _filter_period(
    df: pd.DataFrame,
    period: dict,
    date_col: str,
    filters: dict | None = None,
) -> pd.DataFrame:
    """Filter df to a date range period and optional dimension filters."""
    if not period or date_col not in df.columns:
        return df.copy()

    start = period.get("start")
    end = period.get("end")
    sliced = df.copy()

    if start:
        sliced = sliced[sliced[date_col] >= pd.Timestamp(start)]
    if end:
        sliced = sliced[sliced[date_col] <= pd.Timestamp(end)]

    if filters:
        for col, val in filters.items():
            if col in sliced.columns:
                sliced = sliced[sliced[col].str.lower() == str(val).lower()]

    return sliced


def _get_date_col(metrics_config: dict) -> str:
    """Return the date column name from metrics config."""
    return metrics_config.get("time", {}).get("order_date", {}).get("column", "Order Date")
