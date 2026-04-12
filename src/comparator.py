"""
comparator.py
Pure pandas. No LLM. Two comparison modes:
  - compare_entities: same time, different entities (e.g. West vs East)
  - compare_time_periods: same entity, different times (e.g. 2016 vs 2017)
Both return a structured compare_result dict.
"""

import pandas as pd
from src.change_detector import _filter_period, _apply_metric, _get_date_col


def compare_entities(
    df: pd.DataFrame,
    metric_key: str,
    entity_a: str,
    entity_b: str,
    dimension: str,
    time_period: dict | None,
    metrics_config: dict,
) -> dict:
    """
    Compare two named entities on a metric within an optional time window.
    e.g. "West vs East profit in 2017"
    """
    metric_meta = metrics_config.get("metrics", {}).get(metric_key, {})
    metric_label = metric_meta.get("column", metric_key.capitalize())
    metric_unit = metric_meta.get("unit", "")

    dim_meta = metrics_config.get("dimensions", {}).get(dimension, {})
    dim_col = dim_meta.get("column", dimension)

    val_a = _compute_metric_filtered(
        df, metric_key, {dim_col: entity_a}, time_period, metrics_config
    )
    val_b = _compute_metric_filtered(
        df, metric_key, {dim_col: entity_b}, time_period, metrics_config
    )

    absolute_diff = val_a - val_b
    pct_diff = (abs(absolute_diff) / val_b * 100) if val_b != 0 else 0.0
    winner = entity_a if val_a >= val_b else entity_b
    loser = entity_b if winner == entity_a else entity_a
    winner_val = val_a if winner == entity_a else val_b
    loser_val = val_b if winner == entity_a else val_a

    # Sub-breakdown: explain winner vs loser across next-level dimensions
    next_dims = _get_next_dimensions(dimension, metrics_config)
    sub_winner = []
    sub_loser = []
    if next_dims:
        breakdown_dim = next_dims[0]
        sub_winner = _compute_sub_breakdown(
            df, metric_key, {dim_col: winner}, breakdown_dim, time_period, metrics_config
        )
        sub_loser = _compute_sub_breakdown(
            df, metric_key, {dim_col: loser}, breakdown_dim, time_period, metrics_config
        )

    # Row counts
    date_col = _get_date_col(metrics_config)
    rows_a = _filter_period_and_entity(df, {dim_col: entity_a}, time_period, date_col).shape[0]
    rows_b = _filter_period_and_entity(df, {dim_col: entity_b}, time_period, date_col).shape[0]

    return {
        "type": "compare",
        "comparison_type": "entity",
        "metric": metric_key,
        "metric_label": metric_label,
        "metric_unit": metric_unit,
        "entity_a": {
            "label": entity_a,
            "dimension": dimension,
            "value": round(val_a, 2),
            "time_period": time_period,
        },
        "entity_b": {
            "label": entity_b,
            "dimension": dimension,
            "value": round(val_b, 2),
            "time_period": time_period,
        },
        "absolute_diff": round(absolute_diff, 2),
        "pct_diff": round(pct_diff, 2),
        "winner": winner,
        "loser": loser,
        "winner_value": round(winner_val, 2),
        "loser_value": round(loser_val, 2),
        "sub_breakdown_winner": sub_winner,
        "sub_breakdown_loser": sub_loser,
        "data_quality": {
            "entity_a_rows": rows_a,
            "entity_b_rows": rows_b,
        },
    }


def compare_time_periods(
    df: pd.DataFrame,
    metric_key: str,
    period_a: dict,
    period_b: dict,
    entity_filter: dict | None,
    metrics_config: dict,
) -> dict:
    """
    Compare the same metric across two time periods (optionally filtered to an entity).
    e.g. "Sales in 2016 vs 2017" or "West region 2016 vs 2017"
    """
    metric_meta = metrics_config.get("metrics", {}).get(metric_key, {})
    metric_label = metric_meta.get("column", metric_key.capitalize())
    metric_unit = metric_meta.get("unit", "")

    val_a = _compute_metric_filtered(df, metric_key, entity_filter or {}, period_a, metrics_config)
    val_b = _compute_metric_filtered(df, metric_key, entity_filter or {}, period_b, metrics_config)

    absolute_diff = val_b - val_a
    pct_diff = (abs(absolute_diff) / val_a * 100) if val_a != 0 else 0.0
    winner_period = period_b if val_b >= val_a else period_a
    loser_period = period_a if winner_period is period_b else period_b

    # Sub-breakdown: show metric by top dimension for the winning period
    dimensions = metrics_config.get("dimensions", {})
    first_dim = next(iter(dimensions), None)
    sub_winner = []
    if first_dim:
        sub_winner = _compute_sub_breakdown(
            df, metric_key, entity_filter or {}, first_dim, winner_period, metrics_config
        )

    date_col = _get_date_col(metrics_config)
    rows_a = _filter_period(df, period_a, date_col, entity_filter).shape[0]
    rows_b = _filter_period(df, period_b, date_col, entity_filter).shape[0]

    return {
        "type": "compare",
        "comparison_type": "time",
        "metric": metric_key,
        "metric_label": metric_label,
        "metric_unit": metric_unit,
        "entity_a": {
            "label": period_a.get("label", "Period A"),
            "dimension": "time",
            "value": round(val_a, 2),
            "time_period": period_a,
        },
        "entity_b": {
            "label": period_b.get("label", "Period B"),
            "dimension": "time",
            "value": round(val_b, 2),
            "time_period": period_b,
        },
        "absolute_diff": round(absolute_diff, 2),
        "pct_diff": round(pct_diff, 2),
        "winner": winner_period.get("label", "Period B"),
        "loser": loser_period.get("label", "Period A"),
        "winner_value": round(max(val_a, val_b), 2),
        "loser_value": round(min(val_a, val_b), 2),
        "sub_breakdown_winner": sub_winner,
        "sub_breakdown_loser": [],
        "data_quality": {
            "entity_a_rows": rows_a,
            "entity_b_rows": rows_b,
        },
    }


def _compute_sub_breakdown(
    df: pd.DataFrame,
    metric_key: str,
    dimension_filter: dict,
    breakdown_dim: str,
    time_period: dict | None,
    metrics_config: dict,
) -> list[dict]:
    """
    Break down the metric for a filtered entity by a secondary dimension.
    Used to explain *why* the winner outperformed the loser.
    Returns top-5 entities sorted by value desc.
    """
    dim_meta = metrics_config.get("dimensions", {}).get(breakdown_dim, {})
    dim_col = dim_meta.get("column", breakdown_dim)
    date_col = _get_date_col(metrics_config)

    sliced = _filter_period(df, time_period, date_col, dimension_filter)
    if sliced.empty or dim_col not in sliced.columns:
        return []

    metric_meta = metrics_config.get("metrics", {}).get(metric_key, {})
    aggregation = metric_meta.get("aggregation", "sum")
    column = metric_meta.get("column", "")

    if aggregation == "derived":
        formula = metric_meta.get("formula", {})
        num_col = formula.get("numerator", "")
        den_col = formula.get("denominator", "")
        mult = formula.get("multiply", 1)
        if not num_col or not den_col or num_col not in sliced.columns or den_col not in sliced.columns:
            return []
        grp = sliced.groupby(dim_col).agg(
            num_sum=(num_col, "sum"),
            den_sum=(den_col, "sum"),
        ).reset_index()
        grp["value"] = grp.apply(
            lambda r: (r["num_sum"] / r["den_sum"] * mult) if r["den_sum"] != 0 else 0.0,
            axis=1,
        )
    elif column and column in sliced.columns:
        if aggregation == "sum":
            grp = sliced.groupby(dim_col)[column].sum().reset_index().rename(columns={column: "value"})
        elif aggregation == "count_distinct":
            grp = sliced.groupby(dim_col)[column].nunique().reset_index().rename(columns={column: "value"})
        elif aggregation == "mean":
            grp = sliced.groupby(dim_col)[column].mean().reset_index().rename(columns={column: "value"})
        else:
            grp = sliced.groupby(dim_col)[column].sum().reset_index().rename(columns={column: "value"})
    else:
        return []

    total = grp["value"].sum()
    grp = grp.sort_values("value", ascending=False).head(5).reset_index(drop=True)

    result = []
    for _, row in grp.iterrows():
        val = float(row["value"])
        result.append({
            "dimension": breakdown_dim,
            "entity": str(row[dim_col]),
            "value": round(val, 2),
            "share_pct": round(val / total * 100, 2) if total != 0 else 0.0,
        })
    return result


def _compute_metric_filtered(
    df: pd.DataFrame,
    metric_key: str,
    filters: dict,
    time_period: dict | None,
    metrics_config: dict,
) -> float:
    """
    Filter df by entity filters + optional time period, then apply metric aggregation.
    Returns a single float.
    """
    date_col = _get_date_col(metrics_config)
    sliced = _filter_period(df, time_period, date_col, filters)

    if sliced.empty:
        return 0.0

    return _apply_metric(sliced, metric_key, metrics_config)


def _filter_period_and_entity(
    df: pd.DataFrame,
    entity_filter: dict,
    time_period: dict | None,
    date_col: str,
) -> pd.DataFrame:
    """Filter by time period and entity filter. Returns filtered df."""
    sliced = df.copy()
    if time_period:
        start = time_period.get("start")
        end = time_period.get("end")
        if start and date_col in sliced.columns:
            sliced = sliced[sliced[date_col] >= pd.Timestamp(start)]
        if end and date_col in sliced.columns:
            sliced = sliced[sliced[date_col] <= pd.Timestamp(end)]
    for col, val in entity_filter.items():
        if col in sliced.columns:
            sliced = sliced[sliced[col].str.lower() == str(val).lower()]
    return sliced


def _get_next_dimensions(dimension: str, metrics_config: dict) -> list[str]:
    """
    Return sub-dimensions to drill into, using whatever dimensions exist in the config.
    Dimensions are ordered by their position in the config (profiler sorts by cardinality).
    """
    dims = list(metrics_config.get("dimensions", {}).keys())
    try:
        idx = dims.index(dimension)
        return dims[idx + 1:]
    except ValueError:
        return [d for d in dims if d != dimension]
