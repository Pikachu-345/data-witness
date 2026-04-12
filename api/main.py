"""
api/main.py
FastAPI backend for DataWitness.
Replaces Streamlit — serves JSON to the React frontend.
"""

import io
import os
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import json
import numpy as np
from fastapi.responses import StreamingResponse

from api.models import (
    QueryRequest, QueryResponse, UploadResponse,
    InsightsResponse, InsightItem,
    QuickActionRequest, QuickActionResponse,
    DataPreviewResponse,
    ChartBuilderRequest,
)
from src.data_loader import get_dataset_summary, load_dataset, load_metrics
from src.dataset_profiler import build_dataset_profile, generate_example_queries
from src.reasoning_engine import route_and_run
from src.trust import build_trust_report
from src.smart_insights import generate_smart_insights

load_dotenv()

app = FastAPI(title="DataWitness API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory session store ───────────────────────────────────────────────────
_sessions: dict[str, dict] = {}


def _session(session_id: str) -> dict:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found. Please upload a dataset first.")
    return _sessions[session_id]


def _make_upload_response(
    session_id: str,
    df: pd.DataFrame,
    profile: dict,
    sample_used: bool = False,
) -> UploadResponse:
    summary = get_dataset_summary(df, metrics_config=profile)
    dr = summary.get("date_range") or {}
    suggested = generate_example_queries(profile)
    return UploadResponse(
        session_id=session_id,
        row_count=len(df),
        columns=list(df.columns),
        date_range={"start": str(dr.get("start", "")), "end": str(dr.get("end", ""))} if dr else None,
        numeric_columns=summary.get("numeric_columns", []),
        categorical_columns=summary.get("categorical_columns", []),
        sample_used=sample_used,
        profile=profile,
        suggested_queries=suggested,
    )


# ── Upload CSV ────────────────────────────────────────────────────────────────
@app.post("/api/upload", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    # Auto-detect schema from uploaded data
    profile = build_dataset_profile(df)

    # Parse the detected time column
    time_cfg = profile.get("time", {}).get("order_date", {})
    date_col = time_cfg.get("column")
    date_fmt = time_cfg.get("format")
    if date_col and date_col in df.columns:
        try:
            if date_fmt and date_fmt != "mixed":
                df[date_col] = pd.to_datetime(df[date_col], format=date_fmt, errors="coerce")
            else:
                df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True, errors="coerce")
        except Exception:
            df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True, errors="coerce")

    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "df": df,
        "dataset_summary": get_dataset_summary(df, metrics_config=profile),
        "metrics": profile,   # dynamic profile, same shape as metrics.yaml
        "last_result": None,
    }
    return _make_upload_response(session_id, df, profile, sample_used=False)


# ── Use sample dataset ────────────────────────────────────────────────────────
@app.get("/api/sample", response_model=UploadResponse)
def use_sample():
    sample_path = Path("assets") / "superstore.csv"
    if not sample_path.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found. Please upload a CSV instead.")

    metrics = load_metrics()
    df = load_dataset(str(sample_path))

    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "df": df,
        "dataset_summary": get_dataset_summary(df),
        "metrics": metrics,   # curated static metrics for Superstore
        "last_result": None,
    }
    return _make_upload_response(session_id, df, metrics, sample_used=True)


# ── Dataset profile ──────────────────────────────────────────────────────────
@app.get("/api/profile/{session_id}")
def get_profile(session_id: str):
    sess = _session(session_id)
    return sess["metrics"]


# ── Query ─────────────────────────────────────────────────────────────────────
@app.post("/api/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    sess = _session(req.session_id)
    df: pd.DataFrame = sess["df"].copy()
    dataset_summary: dict = sess["dataset_summary"]
    metrics: dict = sess["metrics"]
    last_result: Optional[dict] = sess.get("last_result")

    # Apply user filters before running the query
    if req.filters:
        for dim_key, dim_val in req.filters.items():
            dim_col = metrics.get("dimensions", {}).get(dim_key, {}).get("column", dim_key)
            if dim_col in df.columns:
                df = df[df[dim_col].astype(str).str.lower() == str(dim_val).lower()]
    if req.date_range:
        date_cfg = metrics.get("time", {}).get("order_date", {})
        date_col = date_cfg.get("column")
        if date_col and date_col in df.columns:
            if req.date_range.get("start"):
                df = df[df[date_col] >= pd.Timestamp(req.date_range["start"])]
            if req.date_range.get("end"):
                df = df[df[date_col] <= pd.Timestamp(req.date_range["end"])]
        dataset_summary = get_dataset_summary(df, metrics_config=metrics)

    result = route_and_run(
        question=req.question,
        df=df,
        dataset_summary=dataset_summary,
        metrics=metrics,
        eli5_mode=req.eli5_mode,
        context=last_result,
    )

    # Update session context
    sess["last_result"] = result

    # Build trust report for general queries
    confidence = None
    metrics_used = None
    if result.get("intent") not in ("change", "compare") and result.get("success"):
        trust = build_trust_report(
            question=req.question,
            result=result.get("result"),
            code=result.get("code", ""),
            error=result.get("error", ""),
            df=df,
            metrics_config=metrics,
        )
        confidence = trust.get("confidence")
        metrics_used = trust.get("metrics_used", [])

    # Serialise pandas result for general queries
    result_table = None
    result_scalar = None
    raw_result = result.get("result")

    def _sanitize_df(df_in: pd.DataFrame) -> list[dict]:
        """Convert all non-JSON-serializable types to strings before .to_dict()."""
        out = df_in.copy()
        for col in out.columns:
            if out[col].dtype == "object" or not pd.api.types.is_numeric_dtype(out[col]):
                out[col] = out[col].astype(str)
        return out.head(200).to_dict(orient="records")

    if isinstance(raw_result, pd.DataFrame):
        _stat_names = {"count", "mean", "std", "min", "25%", "50%", "75%", "max"}
        _idx_vals = set(str(x) for x in raw_result.index)
        if _idx_vals & _stat_names:
            result_table = _sanitize_df(
                raw_result.rename_axis("Statistic").reset_index()
            )
        else:
            result_table = _sanitize_df(raw_result)
    elif isinstance(raw_result, pd.Series):
        if len(raw_result) == 1:
            try:
                result_scalar = float(raw_result.iloc[0])
            except (TypeError, ValueError):
                result_table = _sanitize_df(raw_result.reset_index())
        else:
            result_table = _sanitize_df(raw_result.reset_index())
    elif isinstance(raw_result, (int, float)):
        result_scalar = float(raw_result)
    elif hasattr(raw_result, "item") and hasattr(raw_result, "ndim") and getattr(raw_result, "ndim", 1) == 0:
        result_scalar = float(raw_result.item())

    return QueryResponse(
        success=result.get("success", False),
        intent=result.get("intent", "general"),
        narrative=result.get("narrative"),
        eli5_narrative=result.get("eli5_narrative"),
        computation_result=result.get("computation_result"),
        graph_data=result.get("graph_data"),
        code=result.get("code"),
        result_table=result_table,
        result_scalar=result_scalar,
        error=result.get("error"),
        confidence=confidence,
        metrics_used=metrics_used,
        period_note=result.get("_period_note"),
        follow_ups=result.get("follow_ups"),
    )


# ── Smart Insights ───────────────────────────────────────────────────────────
@app.post("/api/insights/{session_id}", response_model=InsightsResponse)
def get_insights(session_id: str):
    sess = _session(session_id)
    insights = generate_smart_insights(sess["df"], sess["metrics"])
    return InsightsResponse(insights=[InsightItem(**i) for i in insights])


# ── Quick Actions ────────────────────────────────────────────────────────────
@app.post("/api/quick-action/{session_id}", response_model=QuickActionResponse)
def quick_action(session_id: str, req: QuickActionRequest):
    sess = _session(session_id)
    df = sess["df"]
    metrics = sess["metrics"]
    req.action = req.action.strip()  # Ensure no whitespace

    # Resolve metric and dimension columns
    metric_keys = list(metrics.get("metrics", {}).keys())
    if not metric_keys:
        raise HTTPException(400, "No metrics detected in this dataset")
    m_key = req.metric or metric_keys[0]
    m_meta = metrics.get("metrics", {}).get(m_key, {})
    m_col = m_meta.get("column", m_key)
    m_label = m_key.replace("_", " ").title()

    dims = metrics.get("dimensions", {})
    d_key = req.dimension or (list(dims.keys())[0] if dims else None)
    d_col = dims.get(d_key, {}).get("column", d_key) if d_key else None

    date_cfg = metrics.get("time", {}).get("order_date", {})
    date_col = date_cfg.get("column")

    if req.action == "trends" and date_col and date_col in df.columns:
        if m_col not in df.columns:
            raise HTTPException(400, f"Metric column '{m_col}' not found")
        monthly = df.set_index(date_col)[m_col].resample("ME").sum().dropna()
        data = [{"x": str(d.strftime("%Y-%m")), "y": round(float(v), 2)} for d, v in monthly.items()]
        return QuickActionResponse(chart_type="line", data=data, title=f"{m_label} Over Time", metric_label=m_label)

    elif req.action == "top10" and d_col and d_col in df.columns and m_col in df.columns:
        grp = df.groupby(d_col)[m_col].sum().nlargest(10).reset_index()
        data = [{"x": str(r[d_col]), "y": round(float(r[m_col]), 2)} for _, r in grp.iterrows()]
        return QuickActionResponse(chart_type="bar", data=data, title=f"Top 10 {d_key.replace('_',' ').title()} by {m_label}", metric_label=m_label)

    elif req.action == "distribution" and m_col in df.columns:
        vals = df[m_col].dropna().values
        counts, edges = np.histogram(vals, bins=20)
        data = [{"x": f"{edges[i]:.0f}-{edges[i+1]:.0f}", "y": int(counts[i])} for i in range(len(counts))]
        stats = {"mean": round(float(vals.mean()), 2), "median": round(float(np.median(vals)), 2), "std": round(float(vals.std()), 2)}
        return QuickActionResponse(chart_type="bar", data=data, title=f"{m_label} Distribution", metric_label=m_label, stats=stats)

    elif req.action == "correlation":
        num_cols = [v["column"] for v in metrics.get("metrics", {}).values()
                    if v.get("column") in df.columns and v.get("column") != "derived"]
        if len(num_cols) < 2:
            raise HTTPException(400, "Need at least 2 numeric columns for correlation")
        corr = df[num_cols].corr().round(3)
        data = {"columns": list(corr.columns), "matrix": corr.values.tolist()}
        return QuickActionResponse(chart_type="heatmap", data=data, title="Metric Correlations")

    if req.action == "trends":
        raise HTTPException(400, "No time/date column detected in this dataset for trend analysis")
    raise HTTPException(400, f"Action '{req.action}' could not be performed with the available columns")


# ── Data Preview ─────────────────────────────────────────────────────────────
@app.get("/api/data/{session_id}", response_model=DataPreviewResponse)
def get_data(session_id: str, page: int = 0, page_size: int = 50,
             sort_col: str = "", sort_dir: str = "asc", search: str = ""):
    sess = _session(session_id)
    df = sess["df"]

    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        df = df[mask]
    if sort_col and sort_col in df.columns:
        df = df.sort_values(sort_col, ascending=(sort_dir == "asc"), na_position="last")

    total = len(df)
    sliced = df.iloc[page * page_size : (page + 1) * page_size]
    rows = [{col: (str(v) if pd.notna(v) else None) for col, v in row.items()} for _, row in sliced.iterrows()]

    return DataPreviewResponse(rows=rows, total=total, page=page, page_size=page_size, columns=list(sess["df"].columns))


# ── Chart Builder ────────────────────────────────────────────────────────────
@app.post("/api/chart-builder/{session_id}")
def chart_builder(session_id: str, req: ChartBuilderRequest):
    sess = _session(session_id)
    df = sess["df"]
    metrics = sess["metrics"]

    # Resolve columns
    x_meta = metrics.get("dimensions", {}).get(req.x_column, {})
    x_col = x_meta.get("column", req.x_column) if x_meta else req.x_column

    y_meta = metrics.get("metrics", {}).get(req.y_metric, {})
    y_col = y_meta.get("column", req.y_metric) if y_meta else req.y_metric

    date_cfg = metrics.get("time", {}).get("order_date", {})
    date_col = date_cfg.get("column")

    # Time-based grouping
    if req.x_column == "__time__" and date_col and date_col in df.columns:
        agg_fn = {"sum": "sum", "mean": "mean", "count": "count", "median": "median"}.get(req.aggregation, "sum")
        ts = df.set_index(date_col)[y_col].resample("ME").agg(agg_fn).dropna()
        data = [{"x": str(d.strftime("%Y-%m")), "y": round(float(v), 2)} for d, v in ts.items()]
    elif x_col in df.columns and y_col in df.columns:
        agg_fn = {"sum": "sum", "mean": "mean", "count": "count", "median": "median"}.get(req.aggregation, "sum")
        grp = df.groupby(x_col)[y_col].agg(agg_fn).sort_values(ascending=False).head(req.top_n)
        data = [{"x": str(k), "y": round(float(v), 2)} for k, v in grp.items()]
    else:
        raise HTTPException(400, f"Columns not found: x={x_col}, y={y_col}")

    x_label = req.x_column.replace("_", " ").title() if req.x_column != "__time__" else "Time"
    y_label = req.y_metric.replace("_", " ").title()
    return {"chart_type": req.chart_type, "data": data, "x_label": x_label, "y_label": y_label}


# ── Export ───────────────────────────────────────────────────────────────────
@app.get("/api/export/{session_id}")
def export_result(session_id: str, format: str = "csv"):
    sess = _session(session_id)
    last = sess.get("last_result")
    if not last:
        raise HTTPException(404, "No result to export. Run a query first.")

    if format == "json":
        content = json.dumps(last, default=str, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=datawitness_result.json"},
        )
    else:
        comp = last.get("computation_result", {}) or {}
        if comp.get("contributors"):
            df_export = pd.DataFrame(comp["contributors"])
        elif comp.get("components"):
            df_export = pd.DataFrame(comp["components"])
        elif comp.get("metric_summaries"):
            df_export = pd.DataFrame(comp["metric_summaries"])
        else:
            df_export = pd.DataFrame([{"narrative": last.get("narrative", "")}])

        buf = io.StringIO()
        df_export.to_csv(buf, index=False)
        return StreamingResponse(
            io.BytesIO(buf.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=datawitness_result.csv"},
        )


# ── Session info ──────────────────────────────────────────────────────────────
@app.get("/api/session/{session_id}", response_model=UploadResponse)
def get_session(session_id: str):
    sess = _session(session_id)
    return _make_upload_response(session_id, sess["df"], sess["metrics"])


# ── Serve built React frontend (production) ───────────────────────────────────
_dist = Path("frontend") / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        index = _dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        raise HTTPException(status_code=404, detail="Frontend not built.")
