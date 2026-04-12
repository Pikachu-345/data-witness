"""
reasoning_engine.py
Master orchestrator. Routes by intent to the correct computation path,
builds knowledge graph, generates narrative, returns unified result dict.
Falls back to the existing run_pipeline() for general queries.
"""

import pandas as pd

from src.intent_classifier import classify_intent
from src.change_detector import detect_change
from src.comparator import compare_entities, compare_time_periods
from src.query_engine import run_pipeline, generate_reasoning_narrative, generate_follow_ups


def route_and_run(
    question: str,
    df: pd.DataFrame,
    dataset_summary: dict,
    metrics: dict,
    eli5_mode: bool = False,
    context: dict | None = None,
) -> dict:
    """
    Entry point called by app.py instead of run_pipeline().

    1. Classify intent
    2. Route: change → _run_change_path, compare → _run_compare_path, else → _run_general_path
    3. Return unified result dict (backward-compatible with existing app.py)
    """
    intent = classify_intent(question, dataset_summary, metrics, context)
    intent_type = intent.get("intent", "general")

    if intent_type == "change":
        result = _run_change_path(intent, df, metrics, question, eli5_mode)
    elif intent_type == "compare":
        result = _run_compare_path(intent, df, metrics, question, eli5_mode)
    elif intent_type == "counterfactual":
        result = _run_counterfactual_path(intent, df, metrics, question, eli5_mode)
    elif intent_type == "breakdown":
        result = _run_breakdown_path(intent, df, metrics, question, eli5_mode)
    elif intent_type == "summarize":
        result = _run_summarize_path(intent, df, metrics, question, eli5_mode)
    else:
        result = _run_general_path(question, df, dataset_summary, metrics, eli5_mode)

    # Always store the question for context memory
    result["question"] = question
    result["intent"] = intent_type

    # Generate follow-up suggestions (LLM)
    try:
        result["follow_ups"] = generate_follow_ups(
            question, result.get("computation_result"), intent_type, metrics
        )
    except Exception:
        result["follow_ups"] = []

    return result


# ── Change Path ───────────────────────────────────────────────────────────────

def _run_change_path(
    intent: dict,
    df: pd.DataFrame,
    metrics: dict,
    question: str,
    eli5_mode: bool,
) -> dict:
    """Detect change, rank contributors, build graph, generate narrative."""
    metric_key = intent.get("metric") or _infer_metric_from_df(df, metrics)
    period_a = intent.get("period_a")
    period_b = intent.get("period_b")
    filters = intent.get("filters") or {}

    # Default period fallback: earliest year vs latest year in dataset
    if not period_a or not period_b:
        period_a, period_b = _default_periods(df, metrics)
        _default_used = True
    else:
        _default_used = False

    if not metric_key:
        return _run_general_path(question, df, _build_empty_summary(df), metrics, eli5_mode)

    try:
        computation_result = detect_change(
            df=df,
            metric_key=metric_key,
            period_a=period_a,
            period_b=period_b,
            metrics_config=metrics,
            filters=filters if filters else None,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Change detection failed: {e}",
            "intent": "change",
            "narrative": None, "eli5_narrative": None,
            "code": None, "result": None,
            "computation_result": None, "graph_data": None,
        }

    if computation_result["data_quality"]["missing_dates"]:
        computation_result["_warning"] = "One or both periods returned no data rows."

    narrative = generate_reasoning_narrative(
        question, computation_result, "change", metrics, eli5_mode=False
    )
    eli5_narrative = generate_reasoning_narrative(
        question, computation_result, "change", metrics, eli5_mode=True
    )

    graph_data = _build_graph(computation_result)

    result = {
        "success": True,
        "error": None,
        "narrative": narrative,
        "eli5_narrative": eli5_narrative,
        "code": None,
        "result": None,
        "computation_result": computation_result,
        "graph_data": graph_data,
    }
    if _default_used:
        result["_period_note"] = "No time period specified — comparing earliest vs latest year in dataset."
    return result


# ── Compare Path ──────────────────────────────────────────────────────────────

def _run_compare_path(
    intent: dict,
    df: pd.DataFrame,
    metrics: dict,
    question: str,
    eli5_mode: bool,
) -> dict:
    """Compute comparison, build graph, generate narrative."""
    metric_key = intent.get("metric") or _infer_metric_from_df(df, metrics)
    comparison_type = intent.get("comparison_type", "entity")
    filters = intent.get("filters") or {}

    if not metric_key:
        return _run_general_path(question, df, _build_empty_summary(df), metrics, eli5_mode)

    try:
        if comparison_type == "entity":
            entity_a = intent.get("entity_a")
            entity_b = intent.get("entity_b")
            dimension = intent.get("dimension")

            if not entity_a or not entity_b or not dimension:
                return _run_general_path(question, df, _build_empty_summary(df), metrics, eli5_mode)

            # Validate entities exist in dataset (case-insensitive)
            entity_a, entity_b, dimension = _validate_entities(
                df, entity_a, entity_b, dimension, metrics
            )

            time_period = intent.get("period_a") or intent.get("period_b")

            computation_result = compare_entities(
                df=df,
                metric_key=metric_key,
                entity_a=entity_a,
                entity_b=entity_b,
                dimension=dimension,
                time_period=time_period,
                metrics_config=metrics,
            )

        else:  # time comparison
            period_a = intent.get("period_a")
            period_b = intent.get("period_b")

            if not period_a or not period_b:
                period_a, period_b = _default_periods(df, metrics)

            computation_result = compare_time_periods(
                df=df,
                metric_key=metric_key,
                period_a=period_a,
                period_b=period_b,
                entity_filter=filters if filters else None,
                metrics_config=metrics,
            )

    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "intent": "compare",
            "narrative": None, "eli5_narrative": None,
            "code": None, "result": None,
            "computation_result": None, "graph_data": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Comparison failed: {e}",
            "intent": "compare",
            "narrative": None, "eli5_narrative": None,
            "code": None, "result": None,
            "computation_result": None, "graph_data": None,
        }

    narrative = generate_reasoning_narrative(
        question, computation_result, "compare", metrics, eli5_mode=False
    )
    eli5_narrative = generate_reasoning_narrative(
        question, computation_result, "compare", metrics, eli5_mode=True
    )

    graph_data = _build_graph(computation_result)

    return {
        "success": True,
        "error": None,
        "narrative": narrative,
        "eli5_narrative": eli5_narrative,
        "code": None,
        "result": None,
        "computation_result": computation_result,
        "graph_data": graph_data,
    }


# ── Breakdown Path ───────────────────────────────────────────────────────────

def _run_breakdown_path(
    intent: dict,
    df: pd.DataFrame,
    metrics: dict,
    question: str,
    eli5_mode: bool,
) -> dict:
    """Decompose a metric by dimension."""
    from src.breakdown import decompose_metric

    metric_key = intent.get("metric") or _infer_metric_from_df(df, metrics)
    dimension = intent.get("dimension")
    time_period = intent.get("period_a") or intent.get("period_b")
    filters = intent.get("filters") or {}

    if not metric_key:
        return _run_general_path(question, df, _build_empty_summary(df), metrics, eli5_mode)

    try:
        breakdown_result = decompose_metric(
            df=df, metric_key=metric_key, dimension=dimension,
            time_period=time_period, metrics_config=metrics, filters=filters if filters else None,
        )
    except Exception as e:
        return {
            "success": False, "error": f"Breakdown failed: {e}", "intent": "breakdown",
            "narrative": None, "eli5_narrative": None, "code": None, "result": None,
            "computation_result": None, "graph_data": None,
        }

    narrative = generate_reasoning_narrative(question, breakdown_result, "breakdown", metrics, eli5_mode=False)
    eli5_narrative = generate_reasoning_narrative(question, breakdown_result, "breakdown", metrics, eli5_mode=True)
    graph_data = _build_breakdown_graph(breakdown_result)

    return {
        "success": True, "error": None,
        "narrative": narrative, "eli5_narrative": eli5_narrative,
        "code": None, "result": None,
        "computation_result": breakdown_result, "graph_data": graph_data,
    }


def _build_breakdown_graph(result: dict) -> dict | None:
    """Build a knowledge graph for breakdown results."""
    if not result or not result.get("components"):
        return None

    nodes, edges = [], []
    ml = result.get("metric_label", "Metric")
    unit = result.get("metric_unit", "")
    total = result.get("total_value", 0)
    dim = result.get("dimension_label", "")

    # Central metric node
    nodes.append({
        "id": "total", "label": f"{ml}\n{_fmt_graph(total, unit)}",
        "color": {"background": "#7c3aed", "border": "#a78bfa"},
        "font": {"color": "#ffffff", "size": 18, "bold": True},
        "shape": "ellipse", "size": 55,
        "title": f"Total {ml}: {_fmt_graph(total, unit)}",
        "metadata": {"nodeType": "metric", "name": ml, "unit": unit},
    })

    # Component nodes with colors based on share
    colors = ["#3b82f6", "#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6"]
    for i, c in enumerate(result["components"][:8]):
        cid = f"comp_{i}"
        color = colors[i % len(colors)]
        sz = max(22, min(42, int(c["share_pct"] * 0.4 + 18)))
        nodes.append({
            "id": cid, "label": f"{c['entity']}\n{c['share_pct']:.1f}%",
            "color": {"background": color, "border": color},
            "font": {"color": "#ffffff", "size": 12, "bold": True},
            "shape": "ellipse", "size": sz,
            "title": f"{c['entity']}: {c['share_pct']:.1f}% of {ml}",
            "metadata": {"nodeType": "contributor", "entity": c["entity"], "dimension": c.get("dimension", dim),
                         "sharePct": c["share_pct"], "rank": c["rank"]},
        })
        edges.append({
            "from": cid, "to": "total", "label": f"{c['share_pct']:.1f}%",
            "color": {"color": color}, "width": max(1, int(c["share_pct"] / 15) + 1), "arrows": "to",
        })

    return {"nodes": nodes, "edges": edges}


def _fmt_graph(value: float, unit: str) -> str:
    if unit in ("USD", "$"):
        if abs(value) >= 1_000_000: return f"${value/1_000_000:.1f}M"
        if abs(value) >= 1_000: return f"${value/1_000:.1f}K"
        return f"${value:,.0f}"
    if abs(value) >= 1_000_000: return f"{value/1_000_000:.1f}M"
    if abs(value) >= 1_000: return f"{value/1_000:.1f}K"
    return f"{value:,.1f}"


# ── Summarize Path ──────────────────────────────────────────────────────────

def _run_summarize_path(
    intent: dict,
    df: pd.DataFrame,
    metrics: dict,
    question: str,
    eli5_mode: bool,
) -> dict:
    """Generate statistical summary with trends and anomalies."""
    from src.summarizer import summarize_dataset

    metric_key = intent.get("metric")
    time_period = intent.get("period_a") or intent.get("period_b")

    try:
        summary_result = summarize_dataset(
            df=df, metric_key=metric_key, metrics_config=metrics, time_period=time_period,
        )
    except Exception as e:
        return {
            "success": False, "error": f"Summary failed: {e}", "intent": "summarize",
            "narrative": None, "eli5_narrative": None, "code": None, "result": None,
            "computation_result": None, "graph_data": None,
        }

    narrative = generate_reasoning_narrative(question, summary_result, "summarize", metrics, eli5_mode=False)
    eli5_narrative = generate_reasoning_narrative(question, summary_result, "summarize", metrics, eli5_mode=True)

    return {
        "success": True, "error": None,
        "narrative": narrative, "eli5_narrative": eli5_narrative,
        "code": None, "result": None,
        "computation_result": summary_result, "graph_data": None,
    }


# ── Counterfactual Path ──────────────────────────────────────────────────────

def _run_counterfactual_path(
    intent: dict,
    df: pd.DataFrame,
    metrics: dict,
    question: str,
    eli5_mode: bool,
) -> dict:
    """Compute counterfactual: 'What if entity X didn't change?'"""
    from src.counterfactual import compute_counterfactual

    metric_key = intent.get("metric") or _infer_metric_from_df(df, metrics)
    entity = intent.get("entity_a") or intent.get("entity_b") or ""
    dimension = intent.get("dimension") or ""
    period_a = intent.get("period_a")
    period_b = intent.get("period_b")

    if not metric_key:
        return _run_general_path(question, df, _build_empty_summary(df), metrics, eli5_mode)

    if not period_a or not period_b:
        period_a, period_b = _default_periods(df, metrics)

    if not entity or not dimension:
        return {
            "success": False,
            "error": "Counterfactual requires an entity and dimension (e.g. 'What if South region didn't drop?')",
            "intent": "counterfactual",
            "narrative": None, "eli5_narrative": None,
            "code": None, "result": None,
            "computation_result": None, "graph_data": None,
        }

    try:
        cf_result = compute_counterfactual(
            df=df,
            metric_key=metric_key,
            entity=entity,
            dimension=dimension,
            period_a=period_a,
            period_b=period_b,
            metrics_config=metrics,
        )
    except Exception as e:
        return {
            "success": False,
            "error": f"Counterfactual analysis failed: {e}",
            "intent": "counterfactual",
            "narrative": None, "eli5_narrative": None,
            "code": None, "result": None,
            "computation_result": None, "graph_data": None,
        }

    if cf_result.get("error"):
        return {
            "success": False,
            "error": cf_result["error"],
            "intent": "counterfactual",
            "narrative": None, "eli5_narrative": None,
            "code": None, "result": None,
            "computation_result": cf_result.get("actual"),
            "graph_data": None,
        }

    narrative = generate_reasoning_narrative(
        question, cf_result, "counterfactual", metrics, eli5_mode=False
    )
    eli5_narrative = generate_reasoning_narrative(
        question, cf_result, "counterfactual", metrics, eli5_mode=True
    )

    graph_data = _build_graph(cf_result.get("full_change_result", {}))

    return {
        "success": True,
        "error": None,
        "narrative": narrative,
        "eli5_narrative": eli5_narrative,
        "code": None,
        "result": None,
        "computation_result": cf_result,
        "graph_data": graph_data,
    }


# ── General Path (fallback) ───────────────────────────────────────────────────

def _run_general_path(
    question: str,
    df: pd.DataFrame,
    dataset_summary: dict,
    metrics: dict,
    eli5_mode: bool,
) -> dict:
    """Wrap the existing run_pipeline() and return the unified dict shape."""
    pipeline_result = run_pipeline(
        question=question,
        df=df,
        dataset_summary=dataset_summary,
        metrics=metrics,
        eli5_mode=eli5_mode,
    )
    return {
        "success": pipeline_result["success"],
        "error": pipeline_result.get("error"),
        "narrative": pipeline_result.get("narrative"),
        "eli5_narrative": pipeline_result.get("eli5_narrative"),
        "code": pipeline_result.get("code"),
        "result": pipeline_result.get("result"),
        "computation_result": None,
        "graph_data": None,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_graph(computation_result: dict) -> dict | None:
    """Build knowledge graph JSON dict for the React frontend."""
    try:
        from src.knowledge_graph import build_graph_json
        return build_graph_json(computation_result)
    except Exception:
        return None


def _default_periods(df: pd.DataFrame, metrics: dict) -> tuple[dict, dict]:
    """Return the earliest and latest full years in the dataset."""
    from src.change_detector import _get_date_col
    date_col = _get_date_col(metrics)
    if date_col in df.columns:
        years = sorted(df[date_col].dt.year.dropna().unique())
        if len(years) >= 2:
            ya, yb = int(years[0]), int(years[-1])
        else:
            ya = yb = int(years[0]) if years else 2017
    else:
        import datetime as _dt
        ya = yb = _dt.date.today().year

    return (
        {"start": f"{ya}-01-01", "end": f"{ya}-12-31", "label": str(ya), "raw": str(ya)},
        {"start": f"{yb}-01-01", "end": f"{yb}-12-31", "label": str(yb), "raw": str(yb)},
    )


def _infer_metric_from_df(df: pd.DataFrame, metrics: dict) -> str | None:
    """Return the first metric whose column exists in df, as a fallback."""
    for key, meta in metrics.get("metrics", {}).items():
        col = meta.get("column", "")
        if col == "derived" or col in df.columns:
            return key
    return None


def _build_empty_summary(df: pd.DataFrame) -> dict:
    """Minimal dataset_summary for the general path fallback."""
    return {
        "columns": list(df.columns),
        "date_range": {},
        "numeric_columns": list(df.select_dtypes("number").columns),
        "categorical_columns": list(df.select_dtypes("object").columns),
    }


def _validate_entities(
    df: pd.DataFrame,
    entity_a: str,
    entity_b: str,
    dimension: str,
    metrics: dict,
) -> tuple[str, str, str]:
    """
    Case-insensitive entity validation against the dataframe column.
    Raises ValueError with a clear message if not found.
    """
    dim_meta = metrics.get("dimensions", {}).get(dimension, {})
    dim_col = dim_meta.get("column", dimension)

    if dim_col not in df.columns:
        raise ValueError(f"Dimension column '{dim_col}' not found in dataset.")

    unique_vals = df[dim_col].dropna().unique()
    lower_map = {str(v).lower(): str(v) for v in unique_vals}

    resolved_a = lower_map.get(entity_a.lower())
    resolved_b = lower_map.get(entity_b.lower())

    if not resolved_a:
        raise ValueError(f"Entity '{entity_a}' not found in {dim_col} column.")
    if not resolved_b:
        raise ValueError(f"Entity '{entity_b}' not found in {dim_col} column.")

    return resolved_a, resolved_b, dimension
