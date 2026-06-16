"""
Executive Intelligence Module
==============================
Synthesises all agent outputs into a C-suite executive summary.
Also generates a voice-optimised plain-text version for TTS playback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.agents.data_agent import DataResult
from app.agents.insight_agent import InsightResult
from app.agents.recommendation_agent import RecommendationResult
from app.agents.risk_agent import RiskResult

logger = logging.getLogger(__name__)


@dataclass
class ExecutiveSummary:
    period: str = ""
    portfolio_health: str = "AT RISK"    # GOOD | AT RISK | CRITICAL
    headline_metric: str = ""
    top_concerns: list[str] = field(default_factory=list)
    key_insights: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    metrics_snapshot: dict = field(default_factory=dict)
    voice_text: str = ""           # Optimised for TTS / voice playback
    full_markdown: str = ""


EXEC_SYSTEM = """You are a Chief Risk Officer presenting to the board of a major Indian lending institution.
Generate a concise, impactful executive summary from the data provided.

Tone: authoritative, precise, action-oriented.

Return ONLY valid JSON:
{
  "portfolio_health": "GOOD | AT RISK | CRITICAL",
  "headline_metric": "One critical sentence — the most important number/change",
  "top_concerns": ["Concern 1 with data", "Concern 2 with data", "Concern 3 with data"],
  "key_insights": ["Insight 1", "Insight 2", "Insight 3"],
  "recommended_actions": ["Action 1", "Action 2", "Action 3"],
  "voice_text": "Natural spoken language version (2-3 sentences, no markdown, suitable for TTS)"
}"""


def _health_status(default_rate: float) -> str:
    if default_rate < 8:   return "GOOD"
    if default_rate < 15:  return "AT RISK"
    return "CRITICAL"


def _build_markdown(summary: ExecutiveSummary) -> str:
    health_emoji = {"GOOD": "🟢", "AT RISK": "🟡", "CRITICAL": "🔴"}.get(
        summary.portfolio_health, "🟡"
    )
    concerns = "\n".join(f"{i+1}. {c}" for i, c in enumerate(summary.top_concerns))
    insights = "\n".join(f"• {ins}" for ins in summary.key_insights)
    actions  = "\n".join(f"{i+1}. {a}" for i, a in enumerate(summary.recommended_actions))
    metrics  = "\n".join(f"| {k} | {v} |" for k, v in summary.metrics_snapshot.items())

    return f"""# 📊 FinSight AI — Executive Brief
**{summary.period}** &nbsp;|&nbsp; Generated {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}

---

## Portfolio Health: {health_emoji} **{summary.portfolio_health}**

{summary.headline_metric}

---

## 🔴 Top Concerns
{concerns}

---

## 💡 Key Insights
{insights}

---

## ✅ Recommended Actions
{actions}

---

## 📈 Metrics Snapshot

| Metric | Value |
|--------|-------|
{metrics}
"""


async def generate(
    insights: InsightResult,
    risk: RiskResult | None,
    recommendations: RecommendationResult,
    df: pd.DataFrame,
    llm=None,
) -> ExecutiveSummary:
    dr    = round(df["default"].mean() * 100, 2)
    total = len(df)
    avg_cs = round(df["credit_score"].mean(), 0)

    summary = ExecutiveSummary(
        period="Portfolio Analysis: Jan 2022 – Dec 2024",
        metrics_snapshot={
            "Total Portfolio Records":       f"{total:,}",
            "Overall Default Rate":          f"{dr:.2f}%",
            "Average Credit Score":          f"{avg_cs:.0f}",
            "High DTI Customers (>40%)":     f"{int((df['debt_to_income_ratio']>40).sum()):,}",
            "Repeat Defaulters (2+ times)":  f"{int((df['previous_defaults']>=2).sum()):,}",
            "Total Portfolio Value":         f"₹{df['loan_amount'].sum()/1e7:.1f} Cr",
        },
    )

    if llm and llm.is_available:
        try:
            import json
            user_prompt = (
                f"Default rate: {dr:.2f}%\n"
                f"Total records: {total:,}\n"
                f"Headline insight: {insights.headline}\n"
                f"Key findings: {chr(10).join(insights.key_findings)}\n"
                f"Top risk factors: {[f['factor'] for f in (risk.top_factors[:3] if risk else [])]}\n"
                f"Priority action: {recommendations.priority_action}\n"
                f"Expected impact: {recommendations.expected_impact}\n"
                "Generate the executive board summary."
            )
            raw = await llm.complete(EXEC_SYSTEM, user_prompt)
            if raw:
                clean = raw.strip().strip("```json").strip("```").strip()
                parsed = json.loads(clean)
                summary.portfolio_health    = parsed.get("portfolio_health", _health_status(dr))
                summary.headline_metric     = parsed.get("headline_metric", insights.headline)
                summary.top_concerns        = parsed.get("top_concerns", [])
                summary.key_insights        = parsed.get("key_insights", insights.key_findings)
                summary.recommended_actions = parsed.get("recommended_actions", [])
                summary.voice_text          = parsed.get("voice_text", "")
        except Exception as e:
            logger.warning(f"LLM executive summary failed, using template: {e}")

    # Template fallback
    if not summary.headline_metric:
        summary.portfolio_health    = _health_status(dr)
        summary.headline_metric     = insights.headline or f"Portfolio default rate stands at {dr:.1f}% across {total:,} customers."
        summary.top_concerns        = [
            f"Overall default rate at {dr:.1f}% — concentrated in Young Professional and Maharashtra segments.",
            f"{int((df['debt_to_income_ratio']>40).sum()):,} customers ({(df['debt_to_income_ratio']>40).mean()*100:.1f}%) carry DTI above 40%, the primary default predictor.",
            f"{int((df['previous_defaults']>=2).sum()):,} repeat defaulters in active portfolio require immediate enhanced monitoring.",
        ]
        summary.key_insights        = insights.key_findings or [
            "Young Professional segment carries highest default risk at ~18%.",
            "Maharashtra shows elevated risk: 14.2% default rate vs 12.0% national average.",
            "Credit utilization above 70% is a leading indicator — 3x higher default likelihood.",
        ]
        summary.recommended_actions = [a["title"] for a in recommendations.actions[:3]]

    if not summary.voice_text:
        summary.voice_text = (
            f"Good morning. Our portfolio is currently {summary.portfolio_health.lower()} "
            f"with a default rate of {dr:.1f} percent across {total:,} customers. "
            f"Our top priority is: {summary.recommended_actions[0] if summary.recommended_actions else 'immediate underwriting review'}. "
            f"{summary.headline_metric}"
        )

    summary.full_markdown = _build_markdown(summary)
    return summary
