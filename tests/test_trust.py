"""
test_trust.py
Basic unit tests for the Trust Layer.
Run with: pytest tests/
"""

import pandas as pd
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.trust import compute_confidence, detect_metrics_used


def test_confidence_high_for_dataframe():
    df = pd.DataFrame({"Region": ["West", "East"], "Sales": [1000, 800]})
    result = compute_confidence(df, 'result = df.groupby("Region")["Sales"].sum()', "")
    assert result["score"] >= 80
    assert result["label"] == "High Confidence"


def test_confidence_zero_on_error():
    result = compute_confidence(None, "", "SyntaxError: invalid syntax")
    assert result["score"] == 0
    assert result["label"] == "Failed"


def test_confidence_penalty_empty_df():
    df = pd.DataFrame()
    result = compute_confidence(df, "result = df[df['Region']=='Unknown']", "")
    assert result["score"] < 70


def test_detect_metrics_sales():
    detected = detect_metrics_used("What is total sales by region?", 'result = df.groupby("Region")["Sales"].sum()')
    names = [m["name"] for m in detected]
    assert "Sales" in names


def test_detect_metrics_profit():
    detected = detect_metrics_used("Show me profit by category", 'result = df.groupby("Category")["Profit"].sum()')
    names = [m["name"] for m in detected]
    assert "Profit" in names


def test_confidence_scalar():
    result = compute_confidence(42000.0, 'result = df["Sales"].sum()', "")
    assert result["score"] >= 85
