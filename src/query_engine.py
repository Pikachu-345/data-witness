"""
query_engine.py
Core engine: translates natural language to Pandas code via Groq,
then executes it safely on the loaded dataframe.

Pipeline upgrades:
  1. Dynamic schema injection — only relevant columns/metrics sent to the LLM.
  2. Deterministic time-series parsing — LLM emits a TIME_FILTER JSON directive
     that a Python helper applies with pandas timedelta logic.
  3. Self-correcting execution loop — on exec failure, the traceback is fed back
     to a low-temperature Groq call to rewrite the code (capped at 2 retries).

Safety rule: the blocklist (import/exec/eval/open(/os./sys./subprocess/__)
is enforced on every code candidate, including retries. Non-removable.
"""

import os
import re
import json
import difflib
import traceback
from typing import Any, Optional

import pandas as pd
from groq import Groq
from dotenv import load_dotenv

from src.data_loader import load_metrics, apply_time_filter

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL = "llama-3.3-70b-versatile"
MAX_RETRIES = 2

BLOCKED_TERMS = ["import", "exec", "eval", "open(", "os.", "sys.", "subprocess", "__"]


SYSTEM_PROMPT = """You are a Pandas code generator. Your ONLY job is to convert a natural language question into a short Pandas expression that runs on a DataFrame called `df`.

STRICT RULES:
1. Return ONLY Python code — no explanation, no markdown, no backticks.
2. Store the final output in a variable called `result`. Do NOT use print().
3. Do NOT import anything. `pd` and `df` are already available.
4. Do NOT use plt, matplotlib, or any plotting library.
5. Always return a DataFrame, Series, scalar, or dict — never None.
6. If you cannot answer safely, set `result = "UNABLE_TO_ANSWER"`.

TIME FILTER PROTOCOL (critical):
If the question contains a relative time phrase (e.g. "last month", "this year",
"past 7 days", "year to date", "mtd"), your FIRST line MUST be a directive in this exact format:

# TIME_FILTER: {{"type": "<one_of>", "n": <int_if_needed>}}

Valid types: last_week, this_week, last_month, this_month, mtd,
last_year, this_year, ytd, last_n_days (requires "n"), last_n_months (requires "n").

After the directive line, leave one blank line, then write the Pandas code.
The `df` seen by your code will already be pre-sliced to that period —
do NOT write date comparisons yourself.

If there is no relative time phrase, omit the TIME_FILTER line entirely.

RELEVANT SCHEMA (filtered to this question):
Columns available: {columns}
Date range: {date_range}

Metric definitions:
{metric_definitions}

Dimensions detected:
{dimensions}

Example (no time filter):
Question: What is the total sales by region?
Code:
result = df.groupby("Region")["Sales"].sum().reset_index().sort_values("Sales", ascending=False)

Example (with time filter):
Question: How did technology sales do last month?
Code:
# TIME_FILTER: {{"type": "last_month"}}

result = df[df["Category"] == "Technology"]["Sales"].sum()
"""


FIX_SYSTEM_PROMPT = """You are a Pandas code fixer. The previous code failed when executed.
Return ONLY the corrected Python code — no explanation, no markdown, no backticks.
Same rules as before: store final output in `result`, no imports, no print, no plotting.
If the failure was caused by a wrong column name, use the schema context to pick the right one.
If a TIME_FILTER directive is needed, keep the same format on the first line."""


# ─── Dynamic Schema Injection ─────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"[a-zA-Z]+")
_STOPWORDS = {
    "the", "and", "for", "with", "what", "which", "show", "give", "tell",
    "how", "many", "much", "that", "this", "from", "into", "about", "have",
    "are", "was", "were", "has", "had", "can", "you", "please", "there",
    "top", "total", "sum", "avg", "mean", "count", "all", "any", "per",
}


def _tokenize(question: str) -> list[str]:
    """Extract meaningful lowercase tokens from the question."""
    tokens = _TOKEN_RE.findall(question.lower())
    return [t for t in tokens if len(t) >= 3 and t not in _STOPWORDS]


def select_relevant_schema(
    question: str,
    df_columns: list[str],
    metrics_config: dict,
    cutoff: float = 0.78,
) -> dict:
    """
    Match the user's question against available columns, metrics, and dimensions
    using substring + difflib fuzzy matching. Returns only the pieces worth
    injecting into the LLM prompt.
    """
    q_lower = question.lower()
    tokens = _tokenize(question)

    matched_columns: set[str] = set()
    matched_metrics: dict = {}
    matched_dimensions: dict = {}

    # 1. Direct substring hits on column names (most reliable signal)
    for col in df_columns:
        if col.lower() in q_lower:
            matched_columns.add(col)

    # 2. Fuzzy match tokens against column names
    col_lower_map = {col.lower(): col for col in df_columns}
    for token in tokens:
        for m in difflib.get_close_matches(token, col_lower_map.keys(), n=2, cutoff=cutoff):
            matched_columns.add(col_lower_map[m])

    # 3. Metric name matches — key, column, or fuzzy against tokens
    for metric_name, metric_def in metrics_config.get("metrics", {}).items():
        col = metric_def.get("column", "")
        hit = (
            metric_name.lower() in q_lower
            or (col and col != "derived" and col.lower() in q_lower)
            or bool(difflib.get_close_matches(metric_name.lower(), tokens, n=1, cutoff=cutoff))
        )
        if hit:
            matched_metrics[metric_name] = metric_def
            if col and col != "derived":
                matched_columns.add(col)

    # 4. Dimension matches — key or any of its known values appearing in the question
    for dim_name, dim_def in metrics_config.get("dimensions", {}).items():
        col = dim_def.get("column", "")
        values = dim_def.get("values") or []
        value_hit = any(str(v).lower() in q_lower for v in values)
        name_hit = dim_name.lower() in q_lower or (col and col.lower() in q_lower)
        if value_hit or name_hit:
            matched_dimensions[dim_name] = dim_def
            if col:
                matched_columns.add(col)

    # 5. Always include the date column — temporal intent is common and implicit
    time_col = metrics_config.get("time", {}).get("order_date", {}).get("column")
    if time_col and time_col in df_columns:
        matched_columns.add(time_col)

    # 6. Fallback: if no metric matched at all, include every metric so the LLM
    #    still has something to aggregate on. Columns fallback to full list.
    if not matched_metrics:
        matched_metrics = dict(metrics_config.get("metrics", {}))
    if not matched_columns:
        matched_columns = set(df_columns)

    return {
        "columns": sorted(matched_columns),
        "metrics": matched_metrics,
        "dimensions": matched_dimensions,
    }


def build_system_prompt(
    question: str,
    df_columns: list[str],
    metrics_config: dict,
    dataset_summary: dict,
) -> tuple[str, dict]:
    """Build the scoped system prompt. Returns (prompt, schema_dict) for reuse in retries."""
    schema = select_relevant_schema(question, df_columns, metrics_config)

    columns_block = ", ".join(schema["columns"])

    metric_block = "\n".join(
        f"- {k}: {v.get('definition', '')} (column: {v.get('column', k)}, unit: {v.get('unit', '')})"
        for k, v in schema["metrics"].items()
    ) or "(none detected)"

    dim_block = "\n".join(
        f"- {k} (column: {v.get('column')})"
        + (f", values: {v.get('values')}" if v.get("values") else "")
        for k, v in schema["dimensions"].items()
    ) or "(none detected)"

    date_range = dataset_summary.get("date_range") or {}
    date_line = (
        f"{date_range.get('start', '?')} to {date_range.get('end', '?')}"
        if date_range else "unknown"
    )

    prompt = SYSTEM_PROMPT.format(
        columns=columns_block,
        metric_definitions=metric_block,
        dimensions=dim_block,
        date_range=date_line,
    )
    return prompt, schema


# ─── Time Filter Parsing ──────────────────────────────────────────────────────

_TIME_FILTER_RE = re.compile(r"^\s*#\s*TIME_FILTER:\s*(\{.*?\})\s*$", re.MULTILINE)


def split_time_filter(raw_code: str) -> tuple[Optional[dict], str]:
    """
    Extract the `# TIME_FILTER: {...}` directive (if any) and return
    (filter_spec_dict_or_None, code_without_directive).
    """
    match = _TIME_FILTER_RE.search(raw_code)
    if not match:
        return None, raw_code

    try:
        spec = json.loads(match.group(1))
        if not isinstance(spec, dict) or "type" not in spec:
            return None, raw_code
    except json.JSONDecodeError:
        return None, raw_code

    stripped = (raw_code[: match.start()] + raw_code[match.end():]).lstrip("\n")
    return spec, stripped


# ─── Code Sanitization ────────────────────────────────────────────────────────

def _strip_code_fencing(code: str) -> str:
    """Defensively remove ```python ... ``` fences if the model emits them."""
    code = code.strip()
    if code.startswith("```"):
        code = re.sub(r"^```[a-zA-Z]*\n?", "", code)
        code = re.sub(r"\n?```$", "", code)
    return code.strip()


# ─── LLM Calls ────────────────────────────────────────────────────────────────

def generate_pandas_code(
    question: str,
    df_columns: list[str],
    metrics_config: dict,
    dataset_summary: dict,
) -> tuple[str, dict]:
    """Call Groq to translate NL → Pandas code. Returns (code, schema) so retries can reuse schema."""
    system, schema = build_system_prompt(question, df_columns, metrics_config, dataset_summary)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=512,
    )
    return _strip_code_fencing(response.choices[0].message.content), schema


def fix_pandas_code(
    question: str,
    failed_code: str,
    error_trace: str,
    schema: dict,
) -> str:
    """Ask Groq to rewrite the failed code given the traceback and schema context."""
    schema_summary = (
        f"Columns: {schema.get('columns', [])}\n"
        f"Metrics: {[k for k in schema.get('metrics', {}).keys()]}\n"
        f"Dimensions: {[k for k in schema.get('dimensions', {}).keys()]}"
    )

    user_msg = (
        f"Question: {question}\n\n"
        f"Failed code:\n{failed_code}\n\n"
        f"Error traceback:\n{error_trace}\n\n"
        f"Schema context:\n{schema_summary}\n\n"
        f"Return the corrected code."
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": FIX_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        max_tokens=512,
    )
    return _strip_code_fencing(response.choices[0].message.content)


# ─── Safe Execution ───────────────────────────────────────────────────────────

def execute_pandas_code(code: str, df: pd.DataFrame) -> tuple[Any, str, str]:
    """
    Safely execute a single code candidate. Returns (result, code, error).
    Safety checker (BLOCKED_TERMS) is enforced here — do not weaken.
    """
    for term in BLOCKED_TERMS:
        if term in code:
            return None, code, f"Blocked: code contains disallowed term '{term}'"

    local_vars = {"df": df.copy(), "pd": pd, "result": None}

    try:
        exec(code, {}, local_vars)
    except Exception:
        return None, code, traceback.format_exc()

    result = local_vars.get("result")

    if result is None:
        return None, code, "Code executed but `result` was not set."

    if isinstance(result, str) and result == "UNABLE_TO_ANSWER":
        return None, code, "The model could not safely answer this question."

    return result, code, ""


def execute_with_retry(
    initial_code: str,
    df: pd.DataFrame,
    question: str,
    schema: dict,
    max_retries: int = MAX_RETRIES,
) -> tuple[Any, str, str, int]:
    """
    Run the safe executor with an LLM-in-the-loop self-correction layer.

    Returns (result, final_code, error, attempts) where `attempts` counts
    total exec attempts (1 + retries used).
    """
    current_code = initial_code
    attempts = 0
    last_error = ""

    while attempts <= max_retries:
        attempts += 1
        result, current_code, error = execute_pandas_code(current_code, df)

        if not error:
            return result, current_code, "", attempts

        last_error = error
        if attempts > max_retries:
            break

        try:
            fixed = fix_pandas_code(question, current_code, error, schema)
        except Exception as fix_err:
            last_error = f"{error}\n\n[fix-call failed: {fix_err}]"
            break

        # Re-apply time-filter split on the retry output in case the model
        # decides (or re-decides) to emit a directive.
        _, current_code = split_time_filter(fixed)

    return None, current_code, last_error, attempts


# ─── Narrative ────────────────────────────────────────────────────────────────

def generate_narrative(
    question: str,
    result: Any,
    metrics_config: dict,
    eli5_mode: bool = False,
) -> str:
    """Second Groq call: convert the already-verified result into prose. No math here."""
    result_str = (
        result.to_string()
        if isinstance(result, pd.DataFrame)
        else str(result)
    )

    tone = (
        "Explain this to a non-technical person in very simple, jargon-free language. "
        "Use short sentences. Avoid all technical terms. Max 3 sentences."
        if eli5_mode else
        "Write a concise analyst-style summary. Include key numbers. Max 4 sentences."
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"You are a data analyst writing summaries. {tone}"},
            {
                "role": "user",
                "content": f"Question: {question}\n\nData Result:\n{result_str}\n\nWrite the summary:",
            },
        ],
        temperature=0.3,
        max_tokens=256,
    )
    return response.choices[0].message.content.strip()


# ─── Reasoning Narrative (for structured intent paths) ────────────────────────

def generate_reasoning_narrative(
    question: str,
    computation_result: dict,
    result_type: str,
    metrics: dict,
    eli5_mode: bool = False,
) -> str:
    """Generate narrative grounded in pre-computed structured results (change/compare/breakdown/etc)."""
    tone = (
        "Explain this to a non-technical person in very simple, jargon-free language. "
        "Use short sentences. Avoid all technical terms. Max 3 sentences."
        if eli5_mode else
        "Write a concise analyst-style summary. Include key numbers. Max 4 sentences."
    )

    if result_type == "change":
        metric = computation_result.get("metric_label", "the metric")
        pa = computation_result.get("period_a", {})
        pb = computation_result.get("period_b", {})
        direction = computation_result.get("direction", "changed")
        pct = computation_result.get("pct_change", 0)
        abs_change = computation_result.get("absolute_change", 0)
        top = (computation_result.get("contributors") or [{}])[0] if computation_result.get("contributors") else {}
        unit = computation_result.get("metric_unit", "")
        context = (
            f"Metric: {metric} ({unit})\n"
            f"Period A ({pa.get('label', 'before')}): {pa.get('value', 0):,.2f}\n"
            f"Period B ({pb.get('label', 'after')}): {pb.get('value', 0):,.2f}\n"
            f"Change: {abs_change:+,.2f} ({pct:+.1f}%) — {direction}\n"
        )
        if top:
            context += (
                f"Top driver: {top.get('entity')} ({top.get('dimension')}) "
                f"contributed {top.get('delta', 0):+,.2f} "
                f"({top.get('pct_of_total_change', 0):.1f}% of total change)\n"
            )
        top5 = computation_result.get("contributors", [])[:5]
        if len(top5) > 1:
            others = ", ".join(
                f"{c.get('entity')} ({c.get('dimension')}, {c.get('pct_of_total_change', 0):+.1f}%)"
                for c in top5[1:]
            )
            context += f"Other contributors: {others}\n"

    elif result_type == "breakdown":
        metric = computation_result.get("metric_label", "the metric")
        unit = computation_result.get("metric_unit", "")
        total = computation_result.get("total_value", 0)
        dim_label = computation_result.get("dimension_label", "dimension")
        conc = computation_result.get("concentration", "")
        comps = computation_result.get("components", [])[:5]
        context = (
            f"Metric: {metric} ({unit})\nTotal: {total:,.2f}\n"
            f"Breakdown by: {dim_label}\nDistribution is {conc}\n"
        )
        for c in comps:
            context += f"- {c['entity']}: {c['value']:,.2f} ({c['share_pct']:.1f}% share, rank #{c['rank']})\n"

    elif result_type == "summarize":
        summaries = computation_result.get("metric_summaries", [])
        trend = computation_result.get("trend")
        tb = computation_result.get("top_bottom")
        context = "Statistical Summary:\n"
        for s in summaries[:3]:
            context += (
                f"\n{s['metric_label']} ({s['unit']}):\n"
                f"  Total: {s['sum']:,.2f}, Average: {s['mean']:,.2f}, Median: {s['median']:,.2f}\n"
                f"  Range: {s['min']:,.2f} to {s['max']:,.2f}, Std Dev: {s['std']:,.2f}\n"
            )
            if s.get("anomaly_count", 0) > 0:
                context += f"  Anomalies: {s['anomaly_count']} outliers ({s['anomaly_pct']:.1f}% of data)\n"
        if trend:
            context += f"\nTrend: {trend['direction']} ({trend['pct_change']:+.1f}% over {trend['periods']} periods)\n"
        if tb:
            top_str = ", ".join(f"{t['entity']} ({t['share_pct']:.1f}%)" for t in tb.get("top", []))
            context += f"Top performers by {tb['dimension']}: {top_str}\n"

    elif result_type == "counterfactual":
        metric = computation_result.get("metric_label", "the metric")
        unit = computation_result.get("metric_unit", "")
        entity_removed = computation_result.get("entity_removed", "")
        dimension = computation_result.get("dimension", "")
        actual = computation_result.get("actual", {})
        cf = computation_result.get("counterfactual", {})
        impact = computation_result.get("entity_impact", {})
        context = (
            f"Metric: {metric} ({unit})\n"
            f"ACTUAL: {metric} changed by {actual.get('pct_change', 0):+.1f}% "
            f"({actual.get('absolute_change', 0):+,.2f})\n"
            f"COUNTERFACTUAL: Without {entity_removed} ({dimension}), "
            f"{metric} would have changed by {cf.get('pct_change', 0):+.1f}% "
            f"({cf.get('absolute_change', 0):+,.2f})\n"
            f"Impact of {entity_removed}: delta={impact.get('delta', 0):+,.2f}, "
            f"{impact.get('pct_of_total_change', 0):.1f}% of total change\n"
        )

    else:  # compare
        metric = computation_result.get("metric_label", "the metric")
        unit = computation_result.get("metric_unit", "")
        ea = computation_result.get("entity_a", {})
        eb = computation_result.get("entity_b", {})
        winner = computation_result.get("winner", "")
        pct_diff = computation_result.get("pct_diff", 0)
        abs_diff = computation_result.get("absolute_diff", 0)
        context = (
            f"Metric: {metric} ({unit})\n"
            f"{ea.get('label', 'A')}: {ea.get('value', 0):,.2f}\n"
            f"{eb.get('label', 'B')}: {eb.get('value', 0):,.2f}\n"
            f"Difference: {abs_diff:+,.2f} ({pct_diff:.1f}%)\nWinner: {winner}\n"
        )
        sub = computation_result.get("sub_breakdown_winner", [])[:3]
        if sub:
            breakdown_str = ", ".join(f"{s.get('entity')} ({s.get('share_pct', 0):.1f}%)" for s in sub)
            context += f"Winner's top sub-components: {breakdown_str}\n"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": f"You are a data analyst writing summaries. {tone}"},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Pre-computed results (all numbers are exact — do NOT change them):\n"
                    f"{context}\n\nWrite a clear summary based only on the numbers above:"
                ),
            },
        ],
        temperature=0.3,
        max_tokens=256,
    )
    return response.choices[0].message.content.strip()


def generate_follow_ups(
    question: str,
    computation_result: dict | None,
    intent: str,
    metrics: dict,
) -> list[str]:
    """Generate 3 contextual follow-up questions using the LLM."""
    if not computation_result:
        return []

    result_type = computation_result.get("type", intent)
    metric = computation_result.get("metric_label", computation_result.get("metric", ""))
    summary_parts = [f"Intent: {result_type}", f"Metric: {metric}"]

    if result_type == "change":
        summary_parts.append(f"Direction: {computation_result.get('direction', '')}")
        top_c = (computation_result.get("contributors") or [{}])[0] if computation_result.get("contributors") else {}
        if top_c:
            summary_parts.append(f"Top driver: {top_c.get('entity', '')} ({top_c.get('dimension', '')})")
    elif result_type == "compare":
        summary_parts.append(f"Winner: {computation_result.get('winner', '')}")
    elif result_type == "breakdown":
        comps = computation_result.get("components", [])[:3]
        summary_parts.append(f"Top: {', '.join(c.get('entity', '') for c in comps)}")

    dim_keys = list(metrics.get("dimensions", {}).keys())[:5]
    metric_keys = list(metrics.get("metrics", {}).keys())[:5]
    summary_parts.extend([f"Available dimensions: {dim_keys}", f"Available metrics: {metric_keys}"])

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "You generate follow-up data analysis questions. "
                    "Return ONLY a JSON array of exactly 3 short question strings. "
                    "No markdown, no explanation — just the JSON array."
                )},
                {"role": "user", "content": (
                    f"User asked: \"{question}\"\n"
                    f"Result: {'; '.join(summary_parts)}\n\n"
                    "Suggest 3 natural follow-up questions:"
                )},
            ],
            temperature=0.4,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        follow_ups = json.loads(raw)
        if isinstance(follow_ups, list):
            return [str(q) for q in follow_ups[:3]]
    except Exception:
        pass
    return []


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def run_pipeline(
    question: str,
    df: pd.DataFrame,
    dataset_summary: dict,
    metrics: dict,
    eli5_mode: bool = False,
) -> dict:
    """
    Full pipeline:
      NL → scoped prompt → Pandas code (+ optional TIME_FILTER directive)
         → deterministic time slice → safe exec (with self-correct loop)
         → narrative generation.
    """
    # Step 1: scoped code generation
    raw_code, schema = generate_pandas_code(
        question=question,
        df_columns=list(df.columns),
        metrics_config=metrics,
        dataset_summary=dataset_summary,
    )

    # Step 2: pull out any TIME_FILTER directive and apply it deterministically
    time_filter_spec, code = split_time_filter(raw_code)

    scoped_df = df
    time_filter_applied = None
    if time_filter_spec is not None:
        date_col = metrics.get("time", {}).get("order_date", {}).get("column", "Order Date")
        scoped_df = apply_time_filter(df, time_filter_spec, date_col=date_col)
        time_filter_applied = {
            "spec": time_filter_spec,
            "rows_before": len(df),
            "rows_after": len(scoped_df),
        }

    # Step 3: execute with self-correction loop
    result, final_code, error, attempts = execute_with_retry(
        initial_code=code,
        df=scoped_df,
        question=question,
        schema=schema,
    )

    if error:
        return {
            "success": False,
            "error": error,
            "code": final_code,
            "result": None,
            "narrative": None,
            "eli5_narrative": None,
            "attempts": attempts,
            "time_filter": time_filter_applied,
            "schema_used": schema,
        }

    # Step 4: narrative calls (two — analyst + ELI5)
    narrative = generate_narrative(question, result, metrics, eli5_mode=False)
    eli5_narrative = generate_narrative(question, result, metrics, eli5_mode=True)

    return {
        "success": True,
        "error": None,
        "code": final_code,
        "result": result,
        "narrative": narrative,
        "eli5_narrative": eli5_narrative,
        "attempts": attempts,
        "time_filter": time_filter_applied,
        "schema_used": schema,
    }
