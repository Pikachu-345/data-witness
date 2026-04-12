"""
trust.py
The Trust Layer — attaches confidence score, metric definition,
and source row references to every query result.
Person C owns this file.
"""

import pandas as pd
import re
from src.data_loader import load_metrics


def compute_confidence(result: any, code: str, error: str) -> dict:
    """
    Compute a confidence score for the answer based on heuristics.

    Returns:
        dict with score (0-100), label, and explanation
    """
    if error:
        return {"score": 0, "label": "Failed", "color": "red",
                "explanation": "Query execution failed — result cannot be trusted."}

    score = 70  # base score
    reasons = []

    # Boost: result is a non-empty DataFrame
    if isinstance(result, pd.DataFrame) and not result.empty:
        score += 15
        reasons.append("Result returned structured tabular data")
        # Data-quality check: missing values in numeric columns
        num_cols = result.select_dtypes(include="number").columns
        if len(num_cols) > 0:
            missing_pct = result[num_cols].isna().mean().mean()
            if missing_pct > 0.05:
                score -= 10
                reasons.append(f"Result has {missing_pct:.0%} missing numeric values")
        # Row count boost
        if len(result) >= 30:
            score += 3
            reasons.append(f"Sufficient sample size ({len(result)} rows)")

    # Boost: result is a clean scalar
    elif isinstance(result, (int, float)):
        score += 20
        reasons.append("Result is a single verified numeric value")

    # Slight penalty: result is a string (could be ambiguous)
    elif isinstance(result, str):
        score -= 10
        reasons.append("Result is a text value — verify interpretation")

    # Penalty: empty result
    if isinstance(result, pd.DataFrame) and result.empty:
        score -= 30
        reasons.append("Result returned empty — question may not match available data")

    # Boost: code uses groupby (structured aggregation)
    if code and "groupby" in code:
        score += 5
        reasons.append("Used structured groupby aggregation")

    # Boost: code uses explicit column names
    if code and ('"' in code or "'" in code):
        score += 5
        reasons.append("Code references explicit column names")

    # Penalty: self-correction was needed (if retry metadata present)
    if code and "# RETRY" in code:
        score -= 5
        reasons.append("Code required self-correction retry")

    score = max(0, min(100, score))

    if score >= 85:
        label, color = "High Confidence", "green"
    elif score >= 60:
        label, color = "Medium Confidence", "orange"
    else:
        label, color = "Low Confidence", "red"

    return {
        "score": score,
        "label": label,
        "color": color,
        "explanation": " | ".join(reasons) if reasons else "Standard query executed"
    }


def detect_metrics_used(question: str, code: str, metrics_config: dict | None = None) -> list[dict]:
    """
    Detect which metrics from the config appear in the question or code.
    Returns a list of metric definitions to display in the trust panel.
    """
    if metrics_config is None:
        metrics_config = load_metrics()
    metrics = metrics_config.get("metrics", {})
    detected = []

    question_lower = question.lower()
    code_lower = (code or "").lower()

    for metric_name, metric_info in metrics.items():
        col = metric_info.get("column", "").lower()
        # Check if metric name or its column appears in question or code
        if (metric_name in question_lower or
                col in question_lower or
                col.replace(" ", "") in code_lower or
                f'"{metric_info.get("column", "")}"' in (code or "")):
            detected.append({
                "name": metric_name.title(),
                "column": metric_info.get("column", ""),
                "definition": metric_info.get("definition", ""),
                "unit": metric_info.get("unit", ""),
            })

    return detected


def get_source_rows(result: any, df: pd.DataFrame, code: str) -> pd.DataFrame | None:
    """
    Attempt to extract the source rows from the original dataframe
    that contributed to the result. Used to show in the right panel.

    For grouped results, returns the underlying raw rows.
    For scalar results, returns a sample of relevant rows.
    """
    try:
        # If result is already a DataFrame, check if it looks like a grouped summary
        if isinstance(result, pd.DataFrame):
            if len(result) <= len(df) * 0.5:
                # Looks like an aggregation — try to find underlying raw rows
                # Use the first column of result as a filter key if it's a dimension
                first_col = result.columns[0] if len(result.columns) > 0 else None
                if first_col and first_col in df.columns:
                    filter_vals = result[first_col].tolist()
                    source = df[df[first_col].isin(filter_vals)]
                    return source.head(50)  # cap at 50 rows for display
            return result.head(50)

        # For scalar results, return a sample of the full dataframe
        elif isinstance(result, (int, float)):
            return df.head(20)

        return None
    except Exception:
        return None


def build_trust_report(
    question: str,
    result: any,
    code: str,
    error: str,
    df: pd.DataFrame,
    metrics_config: dict | None = None,
) -> dict:
    """
    Master function — builds the complete trust report for a query.
    Called after every successful (or failed) query execution.

    Returns a dict consumed directly by the UI trust panel.
    """
    confidence = compute_confidence(result, code, error)
    metrics_used = detect_metrics_used(question, code, metrics_config=metrics_config)
    source_rows = get_source_rows(result, df, code) if not error else None

    return {
        "confidence": confidence,
        "metrics_used": metrics_used,
        "source_rows": source_rows,
        "code": code,
        "has_error": bool(error),
        "error_message": error,
    }
