"""
Master Orchestrator
====================
Runs the full multi-agent pipeline for each user query.
Coordinates: Intent → Data → Insight → Risk → Recommendation → [Executive]
Produces a fully structured ChatResponse with reasoning trace.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.agents import data_agent, executive_agent, insight_agent, recommendation_agent, risk_agent
from app.agents.intent_agent import IntentResult, classify
from app.agents.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Response schema
# ──────────────────────────────────────────────────────────
@dataclass
class ReasoningStep:
    module: str
    action: str
    duration_ms: int


@dataclass
class ChatResponse:
    answer: str = ""
    reasoning_steps: list[ReasoningStep] = field(default_factory=list)
    chart: dict | None = None
    data_used: dict = field(default_factory=dict)
    confidence: float = 0.0
    limitations: list[str] = field(default_factory=list)
    agents_used: list[str] = field(default_factory=list)
    executive_summary: dict | None = None
    voice_text: str | None = None
    total_duration_ms: int = 0


# ──────────────────────────────────────────────────────────
# Confidence heuristic
# ──────────────────────────────────────────────────────────
def _compute_confidence(intent: IntentResult, n_records: int) -> float:
    base = intent.confidence
    if n_records > 10_000: base = min(1.0, base + 0.10)
    if n_records > 25_000: base = min(1.0, base + 0.05)
    return round(base, 2)


# ──────────────────────────────────────────────────────────
# Static limitations by intent type
# ──────────────────────────────────────────────────────────
LIMITATIONS: dict[str, list[str]] = {
    "trend":             ["Historical data (2022–2024) only; no real-time feed.",
                          "Seasonal effects not fully modelled."],
    "what_if":           ["Simulation assumes static portfolio — no behavioural response modelled.",
                          "Macro-economic factors not incorporated."],
    "risk_analysis":     ["SHAP values explain model decisions, not causal relationships.",
                          "Model trained on synthetic data; real-world accuracy may differ."],
    "executive_summary": ["Summary reflects portfolio snapshot, not forward projections.",
                          "Board-level decisions require additional due diligence."],
    "policy_query":      ["Policy documents are illustrative; consult legal/compliance for binding interpretation."],
    "_default":          ["Analysis limited to 2022–2024 dataset (30,000 records).",
                          "Synthetic data may not capture all real-world nuances.",
                          "Individual customer decisions require additional manual review."],
}


def _get_limitations(intent: str) -> list[str]:
    return LIMITATIONS.get(intent, LIMITATIONS["_default"])


# ──────────────────────────────────────────────────────────
# Response assembly
# ──────────────────────────────────────────────────────────
def _assemble_answer(
    query: str,
    intent: IntentResult,
    data: Any,
    insights: Any,
    risk: Any,
    recommendations: Any,
    policy_context: list | None,
) -> str:
    parts: list[str] = []

    # ── Headline insight ──────────────────────────────────
    if insights.headline:
        parts.append(f"**{insights.headline}**\n")

    # ── Key findings ──────────────────────────────────────
    if insights.key_findings:
        parts.append("**Key Findings:**")
        for f in insights.key_findings:
            parts.append(f"• {f}")
        parts.append("")

    # ── Pattern analysis ─────────────────────────────────
    if insights.pattern_description:
        parts.append(f"**Analysis:** {insights.pattern_description}\n")

    # ── Risk factors (if applicable) ──────────────────────
    if risk and risk.top_factors and intent.intent in ("risk_analysis", "segmentation", "explanation"):
        parts.append("**Top Risk Drivers (SHAP Analysis):**")
        for f in risk.top_factors[:4]:
            bar = "█" * int(f["importance"] / 5) + "░" * (10 - int(f["importance"] / 5))
            parts.append(f"• **{f['factor']}** [{bar}] {f['importance']:.1f}%")
            parts.append(f"  ↳ {f['description']}")
        parts.append("")

    # ── Policy context (RAG) ──────────────────────────────
    if policy_context:
        parts.append("**Relevant Policy:**")
        for doc in policy_context[:2]:
            parts.append(f"*{doc['title']}*: {doc['content'][:300]}…")
        parts.append("")

    # ── Recommendations ───────────────────────────────────
    if recommendations and recommendations.actions:
        parts.append("**Recommended Actions:**")
        priority_icons = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}
        for a in recommendations.actions[:3]:
            icon = priority_icons.get(a.get("priority", "LOW"), "⚪")
            parts.append(f"{icon} **{a.get('title', '')}** *(_{a.get('timeline', '')}_)*")
            parts.append(f"  {a.get('recommendation', '')}")
            if a.get("expected_impact"):
                parts.append(f"  → Expected impact: _{a.get('expected_impact')}_")
        parts.append("")

    # ── Supporting data note ──────────────────────────────
    if insights.supporting_data:
        parts.append(f"*📊 {insights.supporting_data}*")

    return "\n".join(parts) if parts else "Analysis complete. Please see the chart and data below."


# ──────────────────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────────────────
async def process_query(
    message: str,
    df: pd.DataFrame,
    llm: LLMClient,
    mode: str = "normal",           # "normal" | "executive"
    rag=None,
    feature_importance: dict | None = None,
    model=None,
    conversation_history: list | None = None,
) -> ChatResponse:
    t0    = time.perf_counter()
    steps: list[ReasoningStep] = []
    response = ChatResponse()

    # ── Step 1: Intent Classification ────────────────────
    t1     = time.perf_counter()
    intent = await classify(message, llm)
    steps.append(ReasoningStep(
        module="Query Understanding Module",
        action=(
            f"Classified as '{intent.intent}' query"
            + (f" targeting '{intent.target_column}'" if intent.target_column else "")
            + f" with {intent.confidence:.0%} confidence"
        ),
        duration_ms=int((time.perf_counter() - t1) * 1000),
    ))

    # Override if caller requested executive mode
    if mode == "executive":
        intent.intent = "executive_summary"

    # ── Step 2: RAG lookup (policy queries) ──────────────
    policy_context = None
    if rag and intent.intent == "policy_query":
        t2 = time.perf_counter()
        policy_context = rag.search(message)
        steps.append(ReasoningStep(
            module="Knowledge Retrieval Module",
            action=f"Retrieved {len(policy_context)} relevant policy sections from 3 enterprise documents",
            duration_ms=int((time.perf_counter() - t2) * 1000),
        ))

    # ── Step 3: Data Analysis ─────────────────────────────
    t3   = time.perf_counter()
    data = data_agent.analyse(intent, df)
    steps.append(ReasoningStep(
        module="Data Analysis Module",
        action=f"Computed {data.metric_description} across {data.records_count:,} records",
        duration_ms=int((time.perf_counter() - t3) * 1000),
    ))

    # ── Step 4: Insight Generation ────────────────────────
    t4      = time.perf_counter()
    insights = await insight_agent.generate(message, intent, data, llm)
    steps.append(ReasoningStep(
        module="Insight Generation Module",
        action=f"Identified {len(insights.key_findings)} key patterns; headline: {insights.headline[:80]}…",
        duration_ms=int((time.perf_counter() - t4) * 1000),
    ))

    # ── Step 5: Risk Assessment (conditional) ────────────
    risk = None
    if intent.intent in ("risk_analysis", "segmentation", "explanation", "ranking",
                         "summary", "executive_summary", "anomaly"):
        t5 = time.perf_counter()
        risk = risk_agent.assess(intent, data, df, model, feature_importance)
        steps.append(ReasoningStep(
            module="Risk Assessment Module",
            action=f"Computed SHAP-based risk profile; top driver: {risk.top_factors[0]['factor'] if risk.top_factors else 'N/A'}",
            duration_ms=int((time.perf_counter() - t5) * 1000),
        ))

    # ── Step 6: Recommendations ───────────────────────────
    t6 = time.perf_counter()
    recs = await recommendation_agent.generate(message, insights, risk, intent, data, llm)
    steps.append(ReasoningStep(
        module="Recommendation Engine",
        action=f"Generated {len(recs.actions)} data-backed business recommendations; priority: {recs.priority_action[:60]}…",
        duration_ms=int((time.perf_counter() - t6) * 1000),
    ))

    # ── Step 7: Executive Intelligence (if mode) ─────────
    exec_summary = None
    if intent.intent == "executive_summary" or mode == "executive":
        t7 = time.perf_counter()
        exec_obj = await executive_agent.generate(insights, risk, recs, df, llm)
        steps.append(ReasoningStep(
            module="Executive Intelligence Module",
            action="Synthesised C-suite executive brief with metrics snapshot and voice summary",
            duration_ms=int((time.perf_counter() - t7) * 1000),
        ))
        exec_summary = {
            "portfolio_health":    exec_obj.portfolio_health,
            "headline_metric":     exec_obj.headline_metric,
            "top_concerns":        exec_obj.top_concerns,
            "key_insights":        exec_obj.key_insights,
            "recommended_actions": exec_obj.recommended_actions,
            "metrics_snapshot":    exec_obj.metrics_snapshot,
            "full_markdown":       exec_obj.full_markdown,
        }
        response.voice_text = exec_obj.voice_text

    # ── Assemble final answer ─────────────────────────────
    response.answer = _assemble_answer(
        message, intent, data, insights, risk, recs, policy_context
    )

    # ── Generate conversational voice text via LLM ────────
    if not response.voice_text and llm and llm.is_available:
        try:
            voice_system = (
                "You are a friendly financial AI assistant speaking out loud. "
                "Convert the following analysis into 2-3 natural spoken sentences — "
                "like how a smart colleague would explain it verbally. "
                "No bullet points, no markdown, no symbols. "
                "Speak directly and conversationally. Start with the key number or finding."
            )
            voice_user = (
                f"User asked: {message}\n\n"
                f"Analysis summary: {insights.headline}. "
                f"{insights.pattern_description}"
            )
            voice_raw = await llm.complete(voice_system, voice_user)
            if voice_raw:
                response.voice_text = voice_raw.strip()
        except Exception:
            pass
    response.chart  = data.chart
    response.reasoning_steps = steps
    response.data_used = {
        "records_analyzed": data.records_count,
        "time_period":      "Jan 2022 – Dec 2024",
        "dataset":          "Indian Credit Risk Portfolio (Synthetic, 30,000 records)",
        "missing_data_note": (
            "Income missing for ~2% of records (imputed by segment median). "
            "Savings ratio missing for ~8% (imputed as 0)."
        ),
    }
    response.confidence      = _compute_confidence(intent, data.records_count)
    response.limitations     = _get_limitations(intent.intent)
    response.agents_used     = [s.module for s in steps]
    response.executive_summary = exec_summary
    response.total_duration_ms = int((time.perf_counter() - t0) * 1000)

    logger.info(
        f"Query processed in {response.total_duration_ms}ms | "
        f"intent={intent.intent} | agents={len(steps)} | "
        f"LLM={llm.provider}"
    )
    return response
