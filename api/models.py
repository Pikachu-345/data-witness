from pydantic import BaseModel
from typing import Optional, Any, Dict, List


class UploadResponse(BaseModel):
    session_id: str
    row_count: int
    columns: List[str]
    date_range: Optional[Dict[str, str]] = None
    numeric_columns: List[str] = []
    categorical_columns: List[str] = []
    sample_used: bool = False
    profile: Optional[Dict[str, Any]] = None
    suggested_queries: Optional[List[str]] = None


class QueryRequest(BaseModel):
    question: str
    session_id: str
    eli5_mode: bool = False
    filters: Optional[Dict[str, str]] = None
    date_range: Optional[Dict[str, str]] = None


class QueryResponse(BaseModel):
    success: bool
    intent: str
    narrative: Optional[str] = None
    eli5_narrative: Optional[str] = None
    computation_result: Optional[Dict[str, Any]] = None
    graph_data: Optional[Dict[str, Any]] = None
    code: Optional[str] = None
    result_table: Optional[List[Dict[str, Any]]] = None
    result_scalar: Optional[float] = None
    error: Optional[str] = None
    confidence: Optional[Dict[str, Any]] = None
    metrics_used: Optional[List[Dict[str, Any]]] = None
    period_note: Optional[str] = None
    follow_ups: Optional[List[str]] = None


# ── Smart Insights ───────────────────────────────────────────────
class InsightItem(BaseModel):
    type: str
    title: str
    insight_text: str
    metric: str = ""
    value: Optional[float] = None
    severity: str = "info"
    action_query: str = ""


class InsightsResponse(BaseModel):
    insights: List[InsightItem]


# ── Quick Actions ────────────────────────────────────────────────
class QuickActionRequest(BaseModel):
    action: str   # trends, top10, distribution, correlation
    metric: Optional[str] = None
    dimension: Optional[str] = None


class QuickActionResponse(BaseModel):
    chart_type: str
    data: Any
    title: str
    metric_label: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None


# ── Data Preview ─────────────────────────────────────────────────
class DataPreviewResponse(BaseModel):
    rows: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    columns: List[str]


# ── Chart Builder ────────────────────────────────────────────────
class ChartBuilderRequest(BaseModel):
    x_column: str
    y_metric: str
    chart_type: str = "bar"
    aggregation: str = "sum"
    top_n: int = 20
