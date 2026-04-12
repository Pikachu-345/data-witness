"""
counterfactual.py
"What if X didn't happen?" — Counterfactual analysis engine.
Recomputes a metric change excluding one entity's contribution.
Pure pandas. No LLM.
"""

import pandas as pd
from src.change_detector import detect_change


def compute_counterfactual(
    df: pd.DataFrame,
    metric_key: str,
    entity: str,
    dimension: str,
    period_a: dict,
    period_b: dict,
    metrics_config: dict,
) -> dict:
    """
    Compute what would have happened if `entity` (in `dimension`) hadn't changed.

    1. Run detect_change() to get the actual change result.
    2. Find the matching contributor's delta.
    3. Subtract that delta from Period B to get counterfactual Period B.
    4. Recompute the counterfactual pct_change.

    Returns a dict with both actual and counterfactual results.
    """
    # Step 1: Get the real change result
    actual = detect_change(
        df=df,
        metric_key=metric_key,
        period_a=period_a,
        period_b=period_b,
        metrics_config=metrics_config,
    )

    # Step 2: Find the entity's contribution
    entity_lower = entity.lower()
    dim_lower = dimension.lower()
    matched = None
    for c in actual.get("contributors", []):
        if (c.get("entity", "").lower() == entity_lower and
                c.get("dimension", "").lower() == dim_lower):
            matched = c
            break

    if not matched:
        # Try case-insensitive partial match
        for c in actual.get("contributors", []):
            if entity_lower in c.get("entity", "").lower():
                matched = c
                break

    if not matched:
        # Entity not found — return the actual result with an error note
        return {
            "type": "counterfactual",
            "error": f"Entity '{entity}' not found in {dimension} contributors.",
            "actual": actual,
            "counterfactual": None,
            "entity_removed": entity,
            "dimension": dimension,
        }

    entity_delta = matched.get("delta", 0)
    entity_pct = matched.get("pct_of_total_change", 0)

    # Step 3: Compute counterfactual values
    actual_a = actual["period_a"]["value"]
    actual_b = actual["period_b"]["value"]
    actual_change = actual["absolute_change"]

    # Counterfactual: what if this entity's delta was zero?
    cf_b = actual_b - entity_delta
    cf_change = cf_b - actual_a
    cf_pct = (cf_change / actual_a * 100) if actual_a != 0 else 0.0
    cf_direction = "increase" if cf_change > 0 else ("decrease" if cf_change < 0 else "no_change")

    return {
        "type": "counterfactual",
        "metric": actual.get("metric"),
        "metric_label": actual.get("metric_label"),
        "metric_unit": actual.get("metric_unit", ""),
        "entity_removed": matched.get("entity", entity),
        "dimension": matched.get("dimension", dimension),
        "actual": {
            "period_a_value": actual_a,
            "period_b_value": actual_b,
            "absolute_change": actual_change,
            "pct_change": actual.get("pct_change", 0),
            "direction": actual.get("direction", ""),
        },
        "counterfactual": {
            "period_b_value": cf_b,
            "absolute_change": cf_change,
            "pct_change": round(cf_pct, 2),
            "direction": cf_direction,
        },
        "entity_impact": {
            "delta": entity_delta,
            "pct_of_total_change": entity_pct,
            "rank": matched.get("rank", 0),
        },
        "period_a": actual.get("period_a"),
        "period_b": actual.get("period_b"),
        "full_change_result": actual,
    }
