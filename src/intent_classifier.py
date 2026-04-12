"""
intent_classifier.py
Classifies natural language questions into structured intent dicts.
LLM call returns JSON only. Time resolution is pure Python (deterministic).
"""

import json
import re
import os
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    return _client

def _build_intent_schema(metrics: dict) -> dict:
    """Build intent schema dynamically from whatever metrics/dimensions the profile has."""
    metric_keys = list(metrics.get("metrics", {}).keys())
    dim_keys = list(metrics.get("dimensions", {}).keys())
    return {
        "intent": "change | compare | breakdown | summarize | counterfactual | general",
        "metric": f"one of {metric_keys} or null",
        "period_a": {
            "raw": "exact phrase from question or null",
            "label": "short human label or null"
        },
        "period_b": {
            "raw": "exact phrase from question or null",
            "label": "short human label or null"
        },
        "entity_a": "string entity name or null",
        "entity_b": "string entity name or null",
        "dimension": f"one of {dim_keys} or null",
        "comparison_type": "time | entity | null",
        "filters": {},
        "is_followup": False
    }

_CLASSIFIER_SYSTEM = """You are an intent classifier for a data analytics system.
Your ONLY output must be a single valid JSON object — no explanation, no markdown, no backticks.

CLASSIFICATION RULES:
1. intent must be exactly one of: change, compare, breakdown, summarize, counterfactual, general
   - "change": user asks why/how a metric changed over time (e.g. "why did sales drop", "how did profit change from X to Y")
   - "compare": user compares two entities or two time periods (e.g. "West vs East", "this year vs last year")
   - "breakdown": user wants decomposition of a metric (e.g. "what makes up total sales", "break down costs")
   - "summarize": user wants a summary or overview (e.g. "give me a weekly summary", "overview of performance")
   - "counterfactual": user asks hypothetical questions like "what if X didn't happen", "what if X was removed", "without X", "imagine X didn't drop"
   - "general": anything else (filtering, top N, trends, specific lookups)

2. metric: use only keys from: {metric_keys}
   If no metric is clearly identifiable, set to null.

3. For period_a / period_b: copy the EXACT raw phrase from the question (e.g. "last year", "Q1 2017", "February").
   Do NOT resolve phrases to dates — return raw text only. Set to null if no time period mentioned.

4. entity_a / entity_b: exact string values as mentioned in the question (e.g. "West", "Furniture").
   Set to null if not a compare intent or entities not mentioned.

5. dimension: only use keys from: {dimension_keys}
   Infer from entity names if possible (e.g. "West" → "region").

6. comparison_type: "time" if comparing two time periods, "entity" if comparing two named entities, null otherwise.

7. filters: dict of {{column_key: value}} for any narrowing constraints beyond the main query.

8. is_followup: true if question uses "that", "it", "same", "why", "drill down", "more detail", "that region",
   or otherwise references a prior query without repeating the subject.

DATASET INFO:
- Date range: {date_range}
- Available dimension values: {dimension_values}

PRIOR CONTEXT (if any):
{context_summary}

Return ONLY this JSON shape (with actual values filled in):
{schema}
"""


def _build_context_summary(context: dict | None) -> str:
    if not context:
        return "None"
    intent = context.get("intent", "unknown")
    comp = context.get("computation_result", {}) or {}
    metric = comp.get("metric", context.get("metric", "unknown"))
    parts = [f"Last query was intent='{intent}', metric='{metric}'."]
    if comp.get("period_a"):
        parts.append(f"Period A: {comp['period_a'].get('label', '')}.")
    if comp.get("period_b"):
        parts.append(f"Period B: {comp['period_b'].get('label', '')}.")
    if comp.get("contributors"):
        top = comp["contributors"][0] if comp["contributors"] else None
        if top:
            parts.append(
                f"Top contributor: {top.get('entity')} ({top.get('dimension')}) "
                f"delta={top.get('delta', 0):+.0f}."
            )
    if comp.get("winner"):
        parts.append(f"Winner: {comp['winner']} vs {comp.get('loser', '')}.")
    return " ".join(parts)


def _build_dimension_values(metrics: dict) -> str:
    dims = metrics.get("dimensions", {})
    parts = []
    for key, val in dims.items():
        values = val.get("values", [])
        if values:
            parts.append(f"{key}: {values}")
    return "; ".join(parts) if parts else "not available"


def classify_intent(
    question: str,
    dataset_summary: dict,
    metrics: dict,
    context: dict | None = None,
) -> dict:
    """
    Calls LLM (T=0) to classify question intent into a structured JSON dict.
    After receiving the LLM response, resolves raw time phrases to ISO date ranges.
    Falls back to {"intent": "general"} on any error.
    """
    date_range = dataset_summary.get("date_range") or {}
    date_range_str = f"{date_range.get('start', 'unknown')} to {date_range.get('end', 'unknown')}"
    dimension_values_str = _build_dimension_values(metrics)
    context_summary = _build_context_summary(context)

    # Build dynamic schema from whatever metrics/dimensions this dataset has
    intent_schema = _build_intent_schema(metrics)
    metric_keys = list(metrics.get("metrics", {}).keys())
    dim_keys = list(metrics.get("dimensions", {}).keys())

    system_prompt = _CLASSIFIER_SYSTEM.format(
        date_range=date_range_str,
        dimension_values=dimension_values_str,
        context_summary=context_summary,
        schema=json.dumps(intent_schema, indent=2),
        metric_keys=metric_keys,
        dimension_keys=dim_keys,
    )

    try:
        response = _get_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            temperature=0,
            max_tokens=512,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

        intent_dict = json.loads(raw)
    except (json.JSONDecodeError, Exception):
        return {"intent": "general", "metric": None, "period_a": None, "period_b": None,
                "entity_a": None, "entity_b": None, "dimension": None,
                "comparison_type": None, "filters": {}, "is_followup": False}

    # Resolve raw time phrases to ISO date dicts
    if intent_dict.get("period_a") and isinstance(intent_dict["period_a"], dict):
        raw_a = intent_dict["period_a"].get("raw")
        if raw_a:
            resolved = _resolve_relative_time(raw_a, date_range)
            if resolved:
                intent_dict["period_a"].update(resolved)

    if intent_dict.get("period_b") and isinstance(intent_dict["period_b"], dict):
        raw_b = intent_dict["period_b"].get("raw")
        if raw_b:
            resolved = _resolve_relative_time(raw_b, date_range)
            if resolved:
                intent_dict["period_b"].update(resolved)

    # If it's a followup and we have context, merge missing period info from context
    if intent_dict.get("is_followup") and context:
        comp = context.get("computation_result", {}) or {}
        if not intent_dict.get("period_a") and comp.get("period_a"):
            intent_dict["period_a"] = comp["period_a"]
        if not intent_dict.get("period_b") and comp.get("period_b"):
            intent_dict["period_b"] = comp["period_b"]
        if not intent_dict.get("metric") and comp.get("metric"):
            intent_dict["metric"] = comp["metric"]
        # If follow-up references top contributor as entity, carry it forward
        if not intent_dict.get("entity_a") and comp.get("contributors"):
            top = comp["contributors"][0] if comp["contributors"] else None
            if top:
                intent_dict["entity_a"] = top.get("entity")
                if not intent_dict.get("dimension"):
                    intent_dict["dimension"] = top.get("dimension")

    return intent_dict


def _resolve_relative_time(period_str: str, dataset_date_range: dict) -> dict | None:
    """
    Pure Python. Converts natural language time phrases into ISO date dicts.
    Anchors relative terms to the dataset's actual date range.
    Returns {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} or None if unresolvable.
    """
    if not period_str:
        return None

    text = period_str.strip().lower()

    # Parse dataset date range for anchoring
    try:
        ds_end = date.fromisoformat(str(dataset_date_range.get("end", "2017-12-30")))
        ds_start = date.fromisoformat(str(dataset_date_range.get("start", "2014-01-01")))
    except ValueError:
        ds_end = date(2017, 12, 30)
        ds_start = date(2014, 1, 1)

    anchor = ds_end  # "current" is the end of the dataset

    # ── Exact 4-digit year ───────────────────────────────────────────────────
    m = re.fullmatch(r"(\d{4})", text)
    if m:
        y = int(m.group(1))
        return {"start": f"{y}-01-01", "end": f"{y}-12-31"}

    # ── Year range: "2016 to 2017", "2016 vs 2017", "2016-2017" ────────────
    m = re.search(r"(\d{4})\s*(?:to|vs|–|-)\s*(\d{4})", text)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        return {"start": f"{y1}-01-01", "end": f"{y2}-12-31"}

    # ── Quarter: "Q1 2017", "q3 2016" ───────────────────────────────────────
    m = re.search(r"q([1-4])\s*(\d{4})", text)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        month_start = (q - 1) * 3 + 1
        month_end = q * 3
        start = date(y, month_start, 1)
        # last day of quarter-end month
        if month_end == 12:
            end = date(y, 12, 31)
        else:
            end = date(y, month_end + 1, 1) - timedelta(days=1)
        return {"start": start.isoformat(), "end": end.isoformat()}

    # ── Named month + year: "January 2017", "jan 2016" ──────────────────────
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10,
        "november": 11, "december": 12,
    }
    for mon_name, mon_num in months.items():
        m = re.search(rf"\b{mon_name}\s+(\d{{4}})\b", text)
        if m:
            y = int(m.group(1))
            start = date(y, mon_num, 1)
            if mon_num == 12:
                end = date(y, 12, 31)
            else:
                end = date(y, mon_num + 1, 1) - timedelta(days=1)
            return {"start": start.isoformat(), "end": end.isoformat()}

    # ── Named month only (anchor to dataset year) ────────────────────────────
    for mon_name, mon_num in months.items():
        if re.fullmatch(mon_name, text):
            y = anchor.year
            start = date(y, mon_num, 1)
            if mon_num == 12:
                end = date(y, 12, 31)
            else:
                end = date(y, mon_num + 1, 1) - timedelta(days=1)
            return {"start": start.isoformat(), "end": end.isoformat()}

    # ── Relative: "last year", "this year", "previous year" ─────────────────
    if text in ("last year", "previous year", "prior year"):
        y = anchor.year - 1
        return {"start": f"{y}-01-01", "end": f"{y}-12-31"}
    if text in ("this year", "current year"):
        y = anchor.year
        return {"start": f"{y}-01-01", "end": f"{y}-12-31"}

    # ── Relative: "last month", "this month" ─────────────────────────────────
    if text in ("last month", "previous month", "prior month"):
        first_this = anchor.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return {"start": first_prev.isoformat(), "end": last_prev.isoformat()}
    if text in ("this month", "current month"):
        first = anchor.replace(day=1)
        if anchor.month == 12:
            last = date(anchor.year, 12, 31)
        else:
            last = date(anchor.year, anchor.month + 1, 1) - timedelta(days=1)
        return {"start": first.isoformat(), "end": last.isoformat()}

    # ── Relative: "last quarter", "this quarter" ─────────────────────────────
    if text in ("last quarter", "previous quarter", "prior quarter"):
        cur_q = (anchor.month - 1) // 3 + 1
        prev_q = cur_q - 1 if cur_q > 1 else 4
        y = anchor.year if cur_q > 1 else anchor.year - 1
        month_start = (prev_q - 1) * 3 + 1
        month_end = prev_q * 3
        start = date(y, month_start, 1)
        end = date(y, month_end + 1, 1) - timedelta(days=1) if month_end < 12 else date(y, 12, 31)
        return {"start": start.isoformat(), "end": end.isoformat()}

    # ── "last N months" ───────────────────────────────────────────────────────
    m = re.search(r"last\s+(\d+)\s+months?", text)
    if m:
        n = int(m.group(1))
        end = anchor
        start = (anchor.replace(day=1) - relativedelta(months=n - 1)).replace(day=1)
        return {"start": start.isoformat(), "end": end.isoformat()}

    # ── "last week", "this week" ──────────────────────────────────────────────
    if text in ("last week", "previous week"):
        end = anchor - timedelta(days=anchor.weekday() + 1)
        start = end - timedelta(days=6)
        return {"start": start.isoformat(), "end": end.isoformat()}
    if text in ("this week", "current week"):
        start = anchor - timedelta(days=anchor.weekday())
        return {"start": start.isoformat(), "end": anchor.isoformat()}

    # ── YTD ──────────────────────────────────────────────────────────────────
    if text in ("ytd", "year to date"):
        return {"start": f"{anchor.year}-01-01", "end": anchor.isoformat()}

    # ── Earliest / latest dataset defaults ───────────────────────────────────
    if text in ("earliest", "first year", "start"):
        y = ds_start.year
        return {"start": f"{y}-01-01", "end": f"{y}-12-31"}
    if text in ("latest", "last year in data", "most recent year"):
        y = ds_end.year
        return {"start": f"{y}-01-01", "end": f"{y}-12-31"}

    return None
