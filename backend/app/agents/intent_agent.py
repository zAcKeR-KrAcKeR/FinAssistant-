"""
Query Understanding Module (Intent Agent)
==========================================
Classifies user queries into 12 intent types using a two-tier approach:
  Tier 1: Keyword matching (instant, always works)
  Tier 2: LLM classification (richer, if LLM available)

Returns a structured IntentResult with entity extraction.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Intent definitions
# ──────────────────────────────────────────────────────────
INTENT_TYPES = [
    "summary",           # "What is the overall default rate?"
    "aggregation",       # "Default rate by state"
    "filter",            # "Customers with DTI > 50%"
    "ranking",           # "Top 5 states by default rate"
    "risk_analysis",     # "What are the risk factors?"
    "trend",             # "How has default rate changed over time?"
    "what_if",           # "What if income threshold raised by 15%?"
    "executive_summary", # "CEO summary / executive overview"
    "anomaly",           # "Any anomalies? Unusual patterns?"
    "segmentation",      # "How do segments compare?"
    "policy_query",      # "What are the lending policies?"
    "explanation",       # "Why is this customer high risk?"
]

KEYWORD_MAP: dict[str, list[str]] = {
    "what_if":           ["what if", "what-if", "scenario", "hypothetical",
                          "simulate", "suppose", "if we", "would happen", "impact of"],
    "executive_summary": ["executive", "ceo", "c-suite", "board", "summary report",
                          "executive overview", "brief me", "highlight", "top concerns"],
    "anomaly":           ["anomal", "unusual", "spike", "alert", "outlier",
                          "abnormal", "detect", "flagged", "suspicious", "weird"],
    "risk_analysis":     ["risk factor", "shap", "driver", "cause", "why default",
                          "reason for default", "what causes", "contributing", "explai"],
    "trend":             ["over time", "monthly", "quarterly", "yearly", "trend",
                          "change over", "growth", "increase", "decrease", "historic",
                          "time series", "2022", "2023", "2024"],
    "ranking":           ["highest", "lowest", "top ", "bottom ", "best", "worst",
                          "rank", "leading", "most", "least", "which state"],
    "segmentation":      ["segment", "group by", "cohort", "cluster", "by age",
                          "by income", "by employment", "breakdown", "split by"],
    "policy_query":      ["policy", "guideline", "rule", "regulation", "compliance",
                          "criterion", "criteria", "eligible", "allowed", "permitted"],
    "explanation":       ["why is", "explain this", "how did", "tell me about",
                          "deep dive", "breakdown of", "analyse this customer"],
    "aggregation":       ["by state", "by region", "by segment", "by purpose",
                          "by education", "per segment", "grouped", "broken down"],
    "filter":            ["show me", "filter", "where dti", "customers with",
                          "above", "below", "greater than", "less than"],
}

COLUMN_KEYWORDS: dict[str, list[str]] = {
    "state":                    ["state", "region", "geography", "maharashtra", "gujarat",
                                 "delhi", "karnataka", "tamil", "uttar"],
    "customer_segment":         ["segment", "young professional", "mid-career", "student",
                                 "senior", "retired"],
    "loan_purpose":             ["purpose", "home loan", "personal loan", "education",
                                 "vehicle", "business loan"],
    "employment_type":          ["employment", "salaried", "self-employed", "freelancer",
                                 "government", "business owner"],
    "debt_to_income_ratio":     ["dti", "debt to income", "debt-to-income", "debt ratio"],
    "credit_utilization":       ["credit util", "utilization", "utilisation"],
    "credit_score":             ["credit score", "cibil", "score"],
    "income":                   ["income", "salary", "earnings", "annual income"],
    "previous_defaults":        ["previous default", "past default", "default history"],
    "age":                      ["age", "young", "old", "senior"],
    "default":                  ["default", "default rate", "defaulters"],
    "application_month":        ["monthly", "month", "trend"],
    "application_year":         ["yearly", "annual trend", "year"],
}


# ──────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────
@dataclass
class IntentResult:
    intent: str = "summary"
    target_column: str | None = None
    group_by_column: str | None = None
    filters: dict = field(default_factory=dict)
    time_dimension: str | None = None      # "monthly" | "quarterly" | "yearly"
    top_n: int | None = None
    what_if_param: str | None = None
    what_if_change_pct: float | None = None
    confidence: float = 0.7
    raw_query: str = ""


# ──────────────────────────────────────────────────────────
# Keyword classifier
# ──────────────────────────────────────────────────────────
def _keyword_classify(query: str) -> str:
    q = query.lower()
    scores: dict[str, int] = {intent: 0 for intent in INTENT_TYPES}

    for intent, kws in KEYWORD_MAP.items():
        for kw in kws:
            if kw in q:
                scores[intent] += 1

    # Fallbacks by structure
    if "?" in q and scores["summary"] == 0 and max(scores.values()) == 0:
        scores["summary"] = 1

    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        return "summary"
    return best


def _extract_column(query: str) -> str | None:
    q = query.lower()
    for col, kws in COLUMN_KEYWORDS.items():
        for kw in kws:
            if kw in q:
                return col
    return None


def _extract_group_by(query: str) -> str | None:
    q = query.lower()
    patterns = [r"by (\w+)", r"per (\w+)", r"across (\w+)"]
    for pat in patterns:
        m = re.search(pat, q)
        if m:
            token = m.group(1)
            for col, kws in COLUMN_KEYWORDS.items():
                if token in [kw.split()[-1] for kw in kws] or token in col:
                    return col
    return None


def _extract_top_n(query: str) -> int | None:
    m = re.search(r"top[- ]?(\d+)", query.lower())
    if m:
        return int(m.group(1))
    return None


def _extract_time_dim(query: str) -> str | None:
    q = query.lower()
    if any(w in q for w in ["monthly", "month-by-month", "per month"]):
        return "monthly"
    if any(w in q for w in ["quarterly", "quarter", "q1", "q2", "q3", "q4"]):
        return "quarterly"
    if any(w in q for w in ["yearly", "annual", "year-by-year", "per year"]):
        return "yearly"
    return None


def _extract_what_if(query: str) -> tuple[str | None, float | None]:
    q = query.lower()
    param = None
    change_pct = None

    # Extract percentage
    m = re.search(r"(\d+)\s*%", q)
    if m:
        change_pct = float(m.group(1))

    # Extract parameter
    if "income" in q:
        param = "income"
    elif "credit score" in q or "cibil" in q:
        param = "credit_score"
    elif "dti" in q or "debt" in q:
        param = "debt_to_income_ratio"
    elif "utilization" in q or "utilisation" in q:
        param = "credit_utilization"

    return param, change_pct


# ──────────────────────────────────────────────────────────
# LLM-enhanced classification
# ──────────────────────────────────────────────────────────
INTENT_SYSTEM_PROMPT = """You are an intent classifier for a financial data analytics assistant.
Classify the user query into exactly ONE of these intents:
summary, aggregation, filter, ranking, risk_analysis, trend, what_if,
executive_summary, anomaly, segmentation, policy_query, explanation

Return ONLY valid JSON like:
{"intent": "ranking", "confidence": 0.95}

Do not explain. Do not add any text outside the JSON."""


async def classify(query: str, llm=None) -> IntentResult:
    """Classify intent using keywords first, LLM for confidence boost."""
    result = IntentResult(raw_query=query)

    # Tier 1: keyword
    kw_intent = _keyword_classify(query)
    result.intent = kw_intent
    result.confidence = 0.75

    # Entity extraction (always)
    result.target_column  = _extract_column(query)
    result.group_by_column = _extract_group_by(query) or result.target_column
    result.top_n          = _extract_top_n(query)
    result.time_dimension = _extract_time_dim(query)

    if kw_intent == "what_if":
        result.what_if_param, result.what_if_change_pct = _extract_what_if(query)

    # Tier 2: LLM refinement
    if llm and llm.is_available:
        try:
            raw = await llm.complete(INTENT_SYSTEM_PROMPT, f"Query: {query}")
            if raw:
                data = json.loads(raw.strip().strip("```json").strip("```"))
                llm_intent = data.get("intent", kw_intent)
                llm_conf   = float(data.get("confidence", 0.75))
                if llm_intent in INTENT_TYPES and llm_conf > result.confidence:
                    result.intent     = llm_intent
                    result.confidence = llm_conf
        except Exception as e:
            logger.debug(f"LLM intent refinement skipped: {e}")

    logger.info(f"Intent: '{result.intent}' | target: {result.target_column} | confidence: {result.confidence:.2f}")
    return result
