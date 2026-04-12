"""
dataset_profiler.py
Auto-detects schema from any CSV: metrics (numeric), dimensions (categorical),
time columns, and derived metrics. Outputs a profile dict with the same shape
as metrics.yaml so ALL downstream code works without modification.
"""

import re
import pandas as pd
import numpy as np


def build_dataset_profile(df: pd.DataFrame) -> dict:
    """
    Analyse a DataFrame and produce a profile dict structurally identical to
    the static metrics.yaml.  Downstream modules (change_detector, comparator,
    intent_classifier, etc.) receive this as their `metrics_config` and cannot
    tell the difference from a hand-written YAML.

    Returns:
        {
          "metrics": { key: {column, definition, unit, aggregation, ...} },
          "dimensions": { key: {column, values} },
          "time": { "order_date": {column, format} },
        }
    """
    time_col, time_fmt = _detect_time_column(df)
    metrics = _detect_metrics(df, time_col)
    dimensions = _detect_dimensions(df, time_col)
    derived = _detect_derived_metrics(df, metrics)
    metrics.update(derived)

    time_cfg = {}
    if time_col:
        # Use "order_date" as the key so _get_date_col() in change_detector works unchanged
        time_cfg["order_date"] = {"column": time_col, "format": time_fmt or "mixed"}

    return {
        "metrics": metrics,
        "dimensions": dimensions,
        "time": time_cfg,
    }


# ── Time detection ─────────────────────────────────────────────────────────────

def _detect_time_column(df: pd.DataFrame) -> tuple[str | None, str | None]:
    """
    Find the best time/date column by attempting datetime parsing on each column.
    Returns (column_name, format_string) or (None, None).
    """
    # 1. Already-parsed datetime columns
    dt_cols = df.select_dtypes(include=["datetime64", "datetimetz"]).columns.tolist()
    if dt_cols:
        return dt_cols[0], None  # already parsed, no format needed

    # 2. Try common date column names first (fast path)
    date_hints = ["date", "datetime", "timestamp", "time", "created", "ordered"]
    candidates = []
    for col in df.columns:
        if df[col].dtype != "object":
            continue
        sample = df[col].dropna().head(200)
        if sample.empty:
            continue
        try:
            parsed = pd.to_datetime(sample, format="mixed", errors="coerce")
            parse_rate = parsed.notna().sum() / len(sample)
            if parse_rate >= 0.6:
                # Boost score for columns with date-like names
                name_boost = 1.0 if any(h in col.lower() for h in date_hints) else 0.0
                candidates.append((col, parse_rate + name_boost))
        except Exception:
            continue

    if candidates:
        best_col = max(candidates, key=lambda x: x[1])[0]
        fmt = _infer_date_format(df[best_col].dropna().head(20))
        return best_col, fmt

    return None, None


def _infer_date_format(sample: pd.Series) -> str | None:
    """Try common date formats and return the first one that parses >80% of samples."""
    common_formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%m-%d-%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
    ]
    for fmt in common_formats:
        try:
            parsed = pd.to_datetime(sample, format=fmt, errors="coerce")
            if parsed.notna().sum() / len(sample) >= 0.8:
                return fmt
        except Exception:
            continue
    return None  # fall back to infer_datetime_format


# ── Metric detection ───────────────────────────────────────────────────────────

_CURRENCY_HINTS = re.compile(
    r"(price|cost|revenue|sales|profit|amount|total|fee|income|expense|salary|wage|payment)",
    re.IGNORECASE,
)
_PERCENT_HINTS = re.compile(r"(percent|pct|rate|ratio|margin|share|%)", re.IGNORECASE)
_COUNT_HINTS = re.compile(r"(id|_id$|number|count|qty|code)", re.IGNORECASE)


def _detect_metrics(df: pd.DataFrame, time_col: str | None) -> dict:
    """Detect numeric columns and classify them as sum/count_distinct/mean metrics."""
    metrics = {}
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    for col in numeric_cols:
        if col == time_col:
            continue

        key = _col_to_key(col)
        n_unique = df[col].nunique()
        n_rows = len(df)

        # Infer aggregation
        if _COUNT_HINTS.search(col) or (n_unique > 0.5 * n_rows and n_rows > 100):
            aggregation = "count_distinct"
        elif df[col].dropna().between(0, 1).all():
            aggregation = "mean"
        elif _PERCENT_HINTS.search(col):
            aggregation = "mean"
        else:
            aggregation = "sum"

        # Infer unit
        if _CURRENCY_HINTS.search(col):
            unit = "USD"
        elif _PERCENT_HINTS.search(col):
            unit = "percent"
        elif aggregation == "count_distinct":
            unit = "count"
        else:
            unit = "value"

        agg_label = {"sum": "Sum", "count_distinct": "Count of unique", "mean": "Average"}
        definition = f"{agg_label.get(aggregation, 'Sum')} of {col}"

        metrics[key] = {
            "column": col,
            "definition": definition,
            "unit": unit,
            "aggregation": aggregation,
        }

    return metrics


# ── Dimension detection ────────────────────────────────────────────────────────

def _detect_dimensions(df: pd.DataFrame, time_col: str | None) -> dict:
    """Detect categorical columns suitable as grouping dimensions."""
    dimensions = {}
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    # Sort by cardinality (low → high) for sensible drilldown order
    col_cardinality = [(col, df[col].nunique()) for col in cat_cols if col != time_col]
    col_cardinality.sort(key=lambda x: x[1])

    for col, card in col_cardinality:
        if card > 500 or card < 2:
            continue  # Skip very high cardinality or single-value columns

        key = _col_to_key(col)
        values = sorted(df[col].dropna().unique().tolist())[:20]  # Cap at 20 sample values

        dimensions[key] = {
            "column": col,
            "values": values,
        }

    return dimensions


# ── Derived metric detection ───────────────────────────────────────────────────

def _detect_derived_metrics(df: pd.DataFrame, metrics: dict) -> dict:
    """Auto-detect potential derived metrics (e.g. profit_margin = Profit/Sales)."""
    derived = {}

    # Find profit and sales/revenue columns
    profit_key = None
    sales_key = None
    for key, meta in metrics.items():
        col_lower = meta["column"].lower()
        if "profit" in col_lower and not profit_key:
            profit_key = key
        if any(s in col_lower for s in ["sales", "revenue", "income"]) and not sales_key:
            sales_key = key

    if profit_key and sales_key:
        derived["profit_margin"] = {
            "column": "derived",
            "definition": f"Ratio of {metrics[profit_key]['column']} to {metrics[sales_key]['column']} (%)",
            "unit": "percent",
            "aggregation": "derived",
            "formula": {
                "numerator": metrics[profit_key]["column"],
                "denominator": metrics[sales_key]["column"],
                "multiply": 100,
            },
        }

    return derived


# ── Example query generation ──────────────────────────────────────────────────

def generate_example_queries(profile: dict) -> list[str]:
    """Generate 6-9 example queries from detected schema for the sidebar."""
    queries = []
    metrics = list(profile.get("metrics", {}).keys())
    dims = list(profile.get("dimensions", {}).keys())
    has_time = bool(profile.get("time", {}))

    if not metrics:
        return ["Show me the data"]

    m0 = metrics[0]  # primary metric
    m0_label = m0.replace("_", " ")

    # General queries
    if dims:
        d0 = dims[0].replace("_", " ")
        queries.append(f"Total {m0_label} by {d0}")
        queries.append(f"Top 5 {d0}s by {m0_label}")

    # Change queries (if time column exists)
    if has_time:
        queries.append(f"How did {m0_label} change?")
        if len(metrics) > 1:
            m1_label = metrics[1].replace("_", " ")
            queries.append(f"Why did {m1_label} drop last year?")

    # Comparison queries
    if dims:
        d0_meta = profile["dimensions"][dims[0]]
        vals = d0_meta.get("values", [])
        if len(vals) >= 2:
            queries.append(f"Compare {vals[0]} vs {vals[1]} {m0_label}")
        if len(dims) > 1:
            d1 = dims[1].replace("_", " ")
            queries.append(f"Break down {m0_label} by {d1}")

    # Summary
    queries.append(f"Give me a summary of {m0_label}")

    # More general
    if len(metrics) > 1:
        queries.append(f"Show {metrics[1].replace('_', ' ')} trend over time")

    return queries[:9]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _col_to_key(col: str) -> str:
    """Convert a column name to a lowercase key: 'Order ID' → 'order_id'."""
    return re.sub(r"[^a-z0-9]+", "_", col.lower()).strip("_")
