"""
test_breakdown.py
Breakdown Engine Test Suite (ported from starter, adapted for active API)

Runs 6 test cases covering happy path, high-cardinality dimensions,
unknown-metric error handling, small-sample confidence degradation, and
missing-value robustness.

Run with:
    python -m pytest tests/test_breakdown.py -v
    or
    python tests/test_breakdown.py
"""

import os
import sys
import traceback

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.breakdown import decompose_metric
from src.utils.sample_data import load_sample_data
from src.data_loader import load_metrics

_W = 72


def _banner(text: str) -> None:
    print("\n" + "=" * _W)
    print(f"  {text}")
    print("=" * _W)


def _rule(label: str = "") -> None:
    if label:
        print(f"\n  -- {label} {'-' * max(0, _W - len(label) - 6)}")
    else:
        print(f"  {'-' * (_W - 2)}")


def _ok(msg: str = "") -> None:
    print(f"  PASS  {msg}")


def _fail(msg: str = "") -> None:
    print(f"  FAIL  {msg}")


def _info(label: str, value) -> None:
    print(f"  {label:<28}{value}")


def _load_config() -> dict:
    try:
        return load_metrics()
    except Exception:
        import yaml
        yaml_path = os.path.join(os.path.dirname(__file__), "..", "metrics.yaml")
        with open(yaml_path, "r") as f:
            return yaml.safe_load(f) or {}


def _check_success(result: dict) -> bool:
    all_ok = True

    if not result.get("success"):
        _fail(f"success=False -- error: {result.get('error', '?')}")
        return False

    # Components list (backward-compatible format)
    components = result.get("components", [])
    if not components:
        _fail("'components' list is empty")
        all_ok = False
    else:
        _info("Components:", f"{len(components)} groups")

    # Enriched table
    table = result.get("table")
    if not isinstance(table, pd.DataFrame) or table.empty:
        _fail("'table' is missing or empty")
        all_ok = False
    else:
        _rule("Breakdown Table")
        print(table.to_string(index=False))
        _info("\nTable shape:", f"{table.shape[0]} rows x {table.shape[1]} cols")

    # % Contribution sums to ~100
    if table is not None and "% Contribution" in table.columns:
        pct_sum = table["% Contribution"].sum()
        if abs(pct_sum - 100.0) <= 0.5:
            _info("% Contribution sum:", f"{pct_sum:.2f}")
        else:
            _fail(f"% Contribution sums to {pct_sum:.2f}, expected ~100")
            all_ok = False

    # Cumulative % ends at ~100
    if table is not None and "Cumulative %" in table.columns:
        cum_last = table["Cumulative %"].iloc[-1]
        if abs(cum_last - 100.0) <= 0.5:
            _info("Cumulative % (last):", f"{cum_last:.2f}")
        else:
            _fail(f"Cumulative % last value is {cum_last:.2f}, expected ~100")
            all_ok = False

    # Insights
    insights = result.get("insights", {})
    required = {"top_contributor", "concentration", "outliers"}
    missing = required - insights.keys()
    if missing:
        _fail(f"Missing insight keys: {missing}")
        all_ok = False
    else:
        top = insights["top_contributor"]
        conc = insights["concentration"]
        outs = insights["outliers"]
        _info("Top contributor:", f"{top['name']}  {top['pct']:.1f}%  dominant={top['is_dominant']}")
        _info("Concentration:", f"top-{conc['top_n']} = {conc['cumulative_pct']:.1f}%  high={conc['is_high']}")
        _info("Outliers:", ", ".join(outs["names"]) if outs["names"] else "none")

    # Narrative
    narrative = result.get("narrative", "")
    if narrative:
        _rule("Narrative")
        words, line = narrative.split(), ""
        for w in words:
            if len(line) + len(w) + 1 > 68:
                print(f"  {line}")
                line = w
            else:
                line = (line + " " + w).strip()
        if line:
            print(f"  {line}")
    else:
        _fail("'narrative' is empty")
        all_ok = False

    # Chart
    if result.get("chart") is not None:
        _info("\nChart:", "Plotly Figure present")
    else:
        _fail("'chart' is None")
        all_ok = False

    # Trust metadata
    trust = result.get("trust", {})
    if "confidence" not in trust or "metric_definition" not in trust:
        _fail("'trust' dict is missing 'confidence' or 'metric_definition'")
        all_ok = False
    else:
        conf = trust["confidence"]
        mdef = trust["metric_definition"]
        _info("Confidence:", f"{conf['label']}  {conf['score']}/100")
        _info("Metric definition:", mdef.get("definition", "")[:55] + "...")

    return all_ok


def _check_error(result: dict, expected_fragment: str = "") -> bool:
    if result.get("success"):
        _fail("Expected success=False but got True")
        return False

    error = result.get("error", "")
    if not error:
        _fail("success=False but 'error' field is empty")
        return False

    _info("Error message:", error[:75])

    if expected_fragment and expected_fragment.lower() not in error.lower():
        _fail(f"Error message does not mention '{expected_fragment}'")
        return False

    shape_ok = (
        isinstance(result.get("table"), pd.DataFrame)
        and result.get("chart") is None
        and result.get("narrative") == ""
    )
    if not shape_ok:
        _fail("Failure response has wrong shape (table/chart/narrative)")
        return False

    _ok("Handled gracefully -- returned structured error dict")
    return True


# ── TEST CASES ────────────────────────────────────────────────────────────────

def test_01_sales_by_region(df: pd.DataFrame, config: dict) -> bool:
    _banner("TEST 1 -- decompose_metric(df, 'sales', 'Region')")
    try:
        result = decompose_metric(df, "sales", "Region", None, config)
        passed = _check_success(result)
        (_ok if passed else _fail)()
        return passed
    except Exception:
        _fail("Unexpected exception raised")
        traceback.print_exc()
        return False


def test_02_sales_by_category(df: pd.DataFrame, config: dict) -> bool:
    _banner("TEST 2 -- decompose_metric(df, 'sales', 'Category')")
    try:
        result = decompose_metric(df, "sales", "Category", None, config)
        passed = _check_success(result)
        (_ok if passed else _fail)()
        return passed
    except Exception:
        _fail("Unexpected exception raised")
        traceback.print_exc()
        return False


def test_03_profit_by_sub_category(df: pd.DataFrame, config: dict) -> bool:
    _banner("TEST 3 -- decompose_metric(df, 'profit', 'Sub-Category')")
    try:
        result = decompose_metric(df, "profit", "Sub-Category", None, config)
        passed = _check_success(result)
        (_ok if passed else _fail)()
        return passed
    except Exception:
        _fail("Unexpected exception raised")
        traceback.print_exc()
        return False


def test_04_invalid_metric(df: pd.DataFrame, config: dict) -> bool:
    _banner("TEST 4 -- decompose_metric(df, 'revenue', 'Region')  [invalid metric]")
    try:
        result = decompose_metric(df, "revenue", "Region", None, config)
        return _check_error(result, expected_fragment="revenue")
    except Exception:
        _fail("Crashed instead of returning a structured error")
        traceback.print_exc()
        return False


def test_05_small_dataset(df: pd.DataFrame, config: dict) -> bool:
    _banner("TEST 5 -- decompose_metric(df.head(10), 'sales', 'Region')  [small dataset]")
    small = df.head(10).copy()
    _info("Input rows:", len(small))
    try:
        result = decompose_metric(small, "sales", "Region", None, config)
        if not result.get("success"):
            _fail(f"Unexpected failure: {result.get('error')}")
            return False

        passed = _check_success(result)

        conf_label = result["trust"]["confidence"]["label"]
        if "Low" in conf_label or "Medium" in conf_label:
            _info("Confidence check:", f"'{conf_label}' (expected degraded for 10 rows)")
        else:
            _fail(f"Expected Low/Medium confidence for 10 rows, got '{conf_label}'")
            passed = False

        (_ok if passed else _fail)()
        return passed
    except Exception:
        _fail("Unexpected exception raised")
        traceback.print_exc()
        return False


def test_06_missing_values(df: pd.DataFrame, config: dict) -> bool:
    _banner("TEST 6 -- decompose_metric(dirty_df, 'sales', 'Region')  [missing values]")
    dirty = df.copy()
    rng = np.random.default_rng(seed=99)
    n_missing = max(1, len(dirty) // 10)
    idx = rng.choice(len(dirty), size=n_missing, replace=False)
    dirty.loc[idx, "Sales"] = np.nan
    actual_pct = dirty["Sales"].isna().mean() * 100
    _info("Injected NaN in Sales:", f"{actual_pct:.1f}% of rows")

    try:
        result = decompose_metric(dirty, "sales", "Region", None, config)
        if not result.get("success"):
            _fail(f"Unexpected failure: {result.get('error')}")
            return False

        passed = _check_success(result)
        conf = result["trust"]["confidence"]
        _info("Confidence (with NaNs):", f"'{conf['label']}'  {conf['score']}/100")

        (_ok if passed else _fail)()
        return passed
    except Exception:
        _fail("Unexpected exception raised")
        traceback.print_exc()
        return False


# ── RUNNER ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "#" * _W)
    print("  DataWitness - Breakdown Engine Test Suite")
    print("  Testing: src/breakdown.py :: decompose_metric()")
    print("#" * _W)

    print("\n  Loading dataset...")
    df = load_sample_data()
    config = _load_config()
    print(f"  Rows: {len(df):,}   Columns: {list(df.columns)[:8]}...")

    tests = [
        test_01_sales_by_region,
        test_02_sales_by_category,
        test_03_profit_by_sub_category,
        test_04_invalid_metric,
        test_05_small_dataset,
        test_06_missing_values,
    ]

    results: list[bool] = []
    for fn in tests:
        try:
            results.append(fn(df, config))
        except Exception:
            _fail(f"Test function {fn.__name__} raised an unhandled exception")
            traceback.print_exc()
            results.append(False)

    n_pass = sum(results)
    n_fail = len(results) - n_pass

    print("\n" + "=" * _W)
    print("  SUMMARY")
    print("=" * _W)
    for fn, ok in zip(tests, results):
        status = "PASS" if ok else "FAIL"
        doc = (fn.__doc__ or "").split(".")[0].strip()
        print(f"  {status}  {fn.__name__}  --  {doc}")
    print("-" * _W)
    print(f"  {n_pass}/{len(results)} tests passed")
    if n_fail == 0:
        print("  All tests passed.")
    else:
        print(f"  {n_fail} test(s) failed -- review output above.")
    print("=" * _W + "\n")

    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
