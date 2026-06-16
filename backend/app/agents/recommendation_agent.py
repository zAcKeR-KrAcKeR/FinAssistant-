"""
Recommendation Engine
======================
Generates actionable, evidence-based business recommendations.
LLM-powered with rich template fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.agents.data_agent import DataResult
from app.agents.insight_agent import InsightResult
from app.agents.intent_agent import IntentResult
from app.agents.risk_agent import RiskResult

logger = logging.getLogger(__name__)


@dataclass
class RecommendationResult:
    actions: list[dict] = field(default_factory=list)
    priority_action: str = ""
    expected_impact: str = ""


REC_SYSTEM = """You are a Chief Risk Officer at a major Indian lending institution.
Based on the analysis provided, generate 3 specific, actionable business recommendations.

Rules:
- Each recommendation must be grounded in the data (cite numbers)
- Include expected impact where possible
- Prioritise by business impact (high/medium/low)
- Be specific: "tighten underwriting for X segment" not "improve risk management"
- Include a timeline hint (immediate / 30 days / next quarter)

Return ONLY valid JSON:
{
  "actions": [
    {
      "priority": "HIGH",
      "title": "Short action title",
      "recommendation": "Specific, data-backed recommendation",
      "expected_impact": "Quantified expected outcome",
      "timeline": "Immediate | 30 days | Next quarter"
    }
  ],
  "priority_action": "The single most important action right now",
  "expected_impact": "Portfolio-level expected improvement"
}"""


def _template_recommendations(
    intent: IntentResult,
    insights: InsightResult,
    risk: RiskResult | None,
    data: DataResult,
) -> RecommendationResult:
    kv = data.key_values
    i  = intent.intent

    if i == "trend":
        change = kv.get("change_pct", 0)
        return RecommendationResult(
            actions=[
                {
                    "priority": "HIGH",
                    "title": "Tighten Underwriting Criteria",
                    "recommendation": (
                        f"Default rate has shifted {change:+.1f}pp. "
                        "Implement stricter DTI cap (reduce from 50% to 40%) for new applications "
                        "and mandatory savings ratio verification for all loan amounts >₹5L."
                    ),
                    "expected_impact": "Estimated 2–3pp reduction in new cohort default rate within 6 months.",
                    "timeline": "Immediate",
                },
                {
                    "priority": "MEDIUM",
                    "title": "Launch Early Warning Monitoring System",
                    "recommendation": (
                        "Deploy automated alerts for customers whose DTI exceeds 45% post-disbursement. "
                        "Trigger outreach at 30/60/90 DPD milestones with personalised repayment options."
                    ),
                    "expected_impact": "Reduce roll-rate from 30DPD to NPA by ~15%.",
                    "timeline": "30 days",
                },
                {
                    "priority": "LOW",
                    "title": "Portfolio Rebalancing",
                    "recommendation": (
                        "Review loan mix — increase proportion of secured (home/vehicle) vs unsecured (personal) loans "
                        "to reduce portfolio credit risk without sacrificing volume."
                    ),
                    "expected_impact": "0.5–1pp improvement in portfolio default rate over 2 quarters.",
                    "timeline": "Next quarter",
                },
            ],
            priority_action="Immediate underwriting tightening to arrest default trend.",
            expected_impact="Aggregate 2–4pp reduction in portfolio default rate within 2 quarters.",
        )

    elif i == "ranking":
        top_group = kv.get("top_results", [{}])
        top_name = top_group[0].get(kv.get("group_column", "state"), "flagged segment") if top_group else "flagged segment"
        top_rate = top_group[0].get("default_rate", 15.0) if top_group else 15.0
        return RecommendationResult(
            actions=[
                {
                    "priority": "HIGH",
                    "title": f"Targeted Intervention in {top_name}",
                    "recommendation": (
                        f"{top_name} shows {top_rate:.1f}% default rate. "
                        "Implement enhanced due diligence: require 2 years of income proof, "
                        "reduce maximum LTV by 10%, and mandate guarantor for loan amounts >₹3L."
                    ),
                    "expected_impact": f"Reduce {top_name} default rate from {top_rate:.1f}% to <10% within 6 months.",
                    "timeline": "Immediate",
                },
                {
                    "priority": "MEDIUM",
                    "title": "Differential Pricing Strategy",
                    "recommendation": (
                        f"Apply risk-based pricing: increase interest rates by 2–3% for high-default {kv.get('group_column', 'segment')}s "
                        "to compensate for elevated credit risk and improve portfolio risk-adjusted returns."
                    ),
                    "expected_impact": "Improve net interest margin by 0.3–0.5% while maintaining volume.",
                    "timeline": "30 days",
                },
                {
                    "priority": "LOW",
                    "title": "Financial Literacy Programme",
                    "recommendation": (
                        "Partner with NGOs and fintech players to run credit health workshops "
                        "in high-default areas. Focus on DTI management and repayment discipline."
                    ),
                    "expected_impact": "Long-term default reduction of 1–2pp over 12–18 months.",
                    "timeline": "Next quarter",
                },
            ],
            priority_action=f"Immediate underwriting hardening for {top_name} segment.",
            expected_impact="Portfolio-level default rate improvement of 1.5–2.5pp over 2 quarters.",
        )

    else:
        dr = kv.get("overall_default_rate", 12.0)
        return RecommendationResult(
            actions=[
                {
                    "priority": "HIGH",
                    "title": "Risk-Tiered Underwriting Framework",
                    "recommendation": (
                        f"With {dr:.1f}% default rate, implement a 3-tier risk framework: "
                        "Green (auto-approve, CS>720, DTI<30%), Yellow (manual review), "
                        "Red (decline or guarantee required). Reduces manual workload by 40%."
                    ),
                    "expected_impact": "1.5–2pp reduction in default rate; 25% faster processing.",
                    "timeline": "30 days",
                },
                {
                    "priority": "MEDIUM",
                    "title": "Young Professional Segment Strategy",
                    "recommendation": (
                        "Young Professionals show ~18% default rate. Introduce income-share agreements "
                        "or co-borrower requirements for this segment. Offer financial planning support "
                        "as a value-add to improve engagement and repayment."
                    ),
                    "expected_impact": "Reduce Young Professional defaults by 4–5pp.",
                    "timeline": "30 days",
                },
                {
                    "priority": "LOW",
                    "title": "Portfolio Diversification",
                    "recommendation": (
                        "Reduce concentration in Maharashtra (currently 15% of portfolio but >14% default rate). "
                        "Expand origination in lower-risk states: Kerala, Punjab, Karnataka."
                    ),
                    "expected_impact": "0.5pp portfolio default rate improvement per 5% rebalancing.",
                    "timeline": "Next quarter",
                },
            ],
            priority_action="Deploy risk-tiered underwriting framework immediately.",
            expected_impact="Overall portfolio default rate reduction from current level by 2–3pp within 6 months.",
        )


async def generate(
    query: str,
    insights: InsightResult,
    risk: RiskResult | None,
    intent: IntentResult,
    data: DataResult,
    llm=None,
) -> RecommendationResult:
    if llm and llm.is_available:
        try:
            import json
            user_prompt = (
                f"User question: {query}\n\n"
                f"Key insight: {insights.headline}\n"
                f"Findings: {chr(10).join(insights.key_findings)}\n\n"
                f"Risk summary: {json.dumps(risk.risk_summary if risk else {}, default=str)}\n"
                f"Top risk factors: {[f['factor'] for f in (risk.top_factors[:3] if risk else [])]}\n\n"
                "Generate 3 specific, data-backed business recommendations."
            )
            raw = await llm.complete(REC_SYSTEM, user_prompt)
            if raw:
                clean = raw.strip().strip("```json").strip("```").strip()
                parsed = json.loads(clean)
                return RecommendationResult(
                    actions=parsed.get("actions", []),
                    priority_action=parsed.get("priority_action", ""),
                    expected_impact=parsed.get("expected_impact", ""),
                )
        except Exception as e:
            logger.warning(f"LLM recommendation failed, using template: {e}")

    return _template_recommendations(intent, insights, risk, data)
