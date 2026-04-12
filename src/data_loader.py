"""
data_loader.py
Handles loading, preprocessing, and deterministic time slicing of the dataset.
Uses functools.lru_cache for FastAPI / test contexts.
"""

import functools
import pandas as pd
import yaml
import os

_cache = functools.lru_cache(maxsize=None)


@_cache
def load_dataset(filepath: str) -> pd.DataFrame:
    """
    Load CSV dataset and parse date columns.
    Cached per filepath so the file is only read once per process.
    """
    try:
        df = pd.read_csv(filepath, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(filepath, encoding="latin-1")

    metrics = load_metrics()
    date_col = metrics.get("time", {}).get("order_date", {}).get("column", "Order Date")
    date_fmt = metrics.get("time", {}).get("order_date", {}).get("format", "%m/%d/%Y")

    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], format=date_fmt, errors="coerce")

    return df


@_cache
def load_metrics() -> dict:
    yaml_path = os.path.join(os.path.dirname(__file__), "..", "metrics.yaml")
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


def get_dataset_summary(df: pd.DataFrame, metrics_config: dict | None = None) -> dict:
    metrics = metrics_config or load_metrics()
    date_col = metrics.get("time", {}).get("order_date", {}).get("column", "Order Date")

    summary = {
        "total_rows": len(df),
        "columns": list(df.columns),
        "date_range": None,
        "numeric_columns": list(df.select_dtypes(include="number").columns),
        "categorical_columns": list(df.select_dtypes(include="object").columns),
    }

    if date_col in df.columns:
        summary["date_range"] = {
            "start": str(df[date_col].min().date()),
            "end": str(df[date_col].max().date()),
        }

    return summary


# ─── Deterministic Time-Series Slicing ────────────────────────────────────────

def apply_time_filter(
    df: pd.DataFrame,
    spec: dict,
    date_col: str = "Order Date",
) -> pd.DataFrame:
    """
    Slice `df` according to a relative time filter spec.
    Anchor date = df[date_col].max() (latest data point, not wall-clock).
    Unknown or malformed specs return `df` unchanged (fail-open).
    """
    if not isinstance(spec, dict) or date_col not in df.columns:
        return df

    anchor = df[date_col].max()
    if pd.isna(anchor):
        return df

    filter_type = str(spec.get("type", "")).lower()
    n_raw = spec.get("n", 0) or 0
    try:
        n = int(n_raw)
    except (TypeError, ValueError):
        n = 0

    if filter_type == "last_week":
        start = anchor - pd.Timedelta(days=7)
        return df[df[date_col] > start]

    if filter_type == "this_week":
        start = anchor - pd.Timedelta(days=anchor.weekday())
        return df[df[date_col] >= start]

    if filter_type == "last_month":
        first_of_anchor_month = anchor.replace(day=1)
        last_month_end = first_of_anchor_month - pd.Timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return df[(df[date_col] >= last_month_start) & (df[date_col] <= last_month_end)]

    if filter_type in ("this_month", "mtd"):
        start = anchor.replace(day=1)
        return df[df[date_col] >= start]

    if filter_type == "last_year":
        start = pd.Timestamp(year=anchor.year - 1, month=1, day=1)
        end = pd.Timestamp(year=anchor.year - 1, month=12, day=31)
        return df[(df[date_col] >= start) & (df[date_col] <= end)]

    if filter_type in ("this_year", "ytd"):
        start = pd.Timestamp(year=anchor.year, month=1, day=1)
        return df[df[date_col] >= start]

    if filter_type == "last_n_days" and n > 0:
        start = anchor - pd.Timedelta(days=n)
        return df[df[date_col] > start]

    if filter_type == "last_n_months" and n > 0:
        start = anchor - pd.DateOffset(months=n)
        return df[df[date_col] > start]

    return df
