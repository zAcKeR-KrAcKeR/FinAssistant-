"""
What-If Analysis API
=====================
Simulates policy changes and returns portfolio impact metrics.
Supports: income threshold, credit score minimum, DTI cap, utilization cap.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/whatif", tags=["whatif"])


class WhatIfRequest(BaseModel):
    parameter: str = Field(..., description="income | credit_score | dti | credit_utilization")
    direction: str = Field("raise", description="raise | lower")
    change_pct: float = Field(..., ge=1, le=100, description="Percentage change")


@router.post("")
def run_whatif(req: WhatIfRequest):
    from app.analytics.data_loader import state
    df = state.df_clean

    n_total = len(df)
    baseline_dr = df["default"].mean() * 100

    # ── Apply the policy change ────────────────────────────────
    if req.parameter == "income":
        # Raise/lower minimum income threshold
        factor = (1 + req.change_pct / 100) if req.direction == "raise" else (1 - req.change_pct / 100)
        current_min = df["income"].quantile(0.10)
        new_min = current_min * factor
        filtered = df[df["income"] >= new_min]
        change_label = f"Minimum income raised to ₹{new_min/100000:.1f}L (+{req.change_pct:.0f}%)"

    elif req.parameter == "credit_score":
        factor = (1 + req.change_pct / 100) if req.direction == "raise" else (1 - req.change_pct / 100)
        current_min = 600
        new_min = min(900, int(current_min * factor))
        filtered = df[df["credit_score"] >= new_min]
        change_label = f"Minimum credit score raised to {new_min} (+{req.change_pct:.0f}%)"

    elif req.parameter == "dti":
        current_max = 50.0
        new_max = current_max * (1 - req.change_pct / 100) if req.direction == "lower" else current_max * (1 + req.change_pct / 100)
        filtered = df[df["debt_to_income_ratio"] <= new_max]
        change_label = f"Maximum DTI capped at {new_max:.1f}% (reduced by {req.change_pct:.0f}%)"

    elif req.parameter == "credit_utilization":
        current_max = 80.0
        new_max = current_max * (1 - req.change_pct / 100)
        filtered = df[df["credit_utilization"] <= new_max]
        change_label = f"Maximum credit utilization capped at {new_max:.1f}%"

    else:
        return {"error": f"Unknown parameter: {req.parameter}"}

    # ── Compute impact ─────────────────────────────────────────
    n_filtered   = len(filtered)
    new_dr       = filtered["default"].mean() * 100
    approved_pct = n_filtered / n_total * 100
    rejected_pct = 100 - approved_pct

    dr_change    = new_dr - baseline_dr
    dr_change_pct = (dr_change / baseline_dr) * 100

    defaults_prevented = int((baseline_dr - new_dr) / 100 * n_filtered)
    lost_good_customers = int(n_total - n_filtered - (df[df["default"]==1].shape[0] - filtered[filtered["default"]==1].shape[0]))

    # Portfolio metrics comparison
    comparison = {
        "baseline": {
            "approval_rate_pct":      100.0,
            "default_rate_pct":       round(baseline_dr, 2),
            "avg_credit_score":       round(df["credit_score"].mean(), 0),
            "avg_income":             round(df["income"].mean(), 0),
            "total_loan_value_cr":    round(df["loan_amount"].sum() / 1e7, 1),
        },
        "scenario": {
            "approval_rate_pct":      round(approved_pct, 2),
            "default_rate_pct":       round(new_dr, 2),
            "avg_credit_score":       round(filtered["credit_score"].mean(), 0) if len(filtered) else 0,
            "avg_income":             round(filtered["income"].mean(), 0) if len(filtered) else 0,
            "total_loan_value_cr":    round(filtered["loan_amount"].sum() / 1e7, 1) if len(filtered) else 0,
        },
    }

    # Segment impact
    seg_impact = []
    for seg in df["customer_segment"].unique():
        base_seg = df[df["customer_segment"]==seg]
        filt_seg = filtered[filtered["customer_segment"]==seg]
        if len(base_seg) == 0:
            continue
        seg_impact.append({
            "segment":         seg,
            "base_count":      len(base_seg),
            "filtered_count":  len(filt_seg),
            "retention_pct":   round(len(filt_seg)/len(base_seg)*100, 1),
            "base_dr":         round(base_seg["default"].mean()*100, 2),
            "new_dr":          round(filt_seg["default"].mean()*100, 2) if len(filt_seg) else 0.0,
        })

    return {
        "parameter":             req.parameter,
        "change_label":          change_label,
        "direction":             req.direction,
        "change_pct":            req.change_pct,
        "defaults_prevented":    defaults_prevented,
        "applications_rejected": n_total - n_filtered,
        "lost_good_customers":   max(0, lost_good_customers),
        "default_rate_change_pp": round(dr_change, 2),
        "default_rate_change_pct": round(dr_change_pct, 1),
        "comparison":            comparison,
        "segment_impact":        seg_impact,
        "interpretation": (
            f"If {change_label}, the portfolio default rate would change from "
            f"{baseline_dr:.1f}% to {new_dr:.1f}% ({dr_change:+.1f}pp). "
            f"Loan approval rate would drop to {approved_pct:.1f}%, "
            f"rejecting {n_total - n_filtered:,} applications. "
            f"Estimated defaults prevented: {defaults_prevented:,}."
        ),
    }
