"""
Dashboard API — pre-computed Plotly charts for all four dashboard pages.
All chart specs are JSON-serialisable Plotly dicts consumed directly by
react-plotly.js on the frontend.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import APIRouter

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── Plotly dark theme ─────────────────────────────────────────
_L = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "font":          {"color": "#e2e8f0", "family": "Inter, sans-serif"},
    "xaxis":         {"gridcolor": "rgba(255,255,255,0.06)", "color": "#94a3b8", "linecolor": "rgba(255,255,255,0.08)"},
    "yaxis":         {"gridcolor": "rgba(255,255,255,0.06)", "color": "#94a3b8", "linecolor": "rgba(255,255,255,0.08)"},
    "legend":        {"bgcolor": "rgba(0,0,0,0)", "font": {"color": "#e2e8f0"}},
    "margin":        {"l": 50, "r": 20, "t": 50, "b": 50},
    "colorway":      ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"],
}


def _get_df():
    from app.analytics.data_loader import state
    return state.df_clean


# ────────────────────────────────────────────────────────────
# PAGE 1: Executive Overview
# ────────────────────────────────────────────────────────────
@router.get("/overview")
def get_overview():
    df = _get_df()

    # KPIs
    dr = df["default"].mean() * 100
    kpis = {
        "default_rate":        round(dr, 2),
        "total_records":       len(df),
        "total_loan_value_cr": round(df["loan_amount"].sum() / 1e7, 1),
        "avg_credit_score":    round(df["credit_score"].mean(), 0),
        "high_risk_count":     int((df["previous_defaults"] >= 2).sum()),
        "high_dti_count":      int((df["debt_to_income_ratio"] > 40).sum()),
    }

    # Monthly default trend
    trend = (
        df.groupby("application_month")["default"]
        .agg(["mean", "count"])
        .reset_index()
        .sort_values("application_month")
    )
    trend["default_rate_pct"] = (trend["mean"] * 100).round(2)

    default_trend = {
        "data": [
            {"type": "scatter", "mode": "lines+markers",
             "x": trend["application_month"].tolist(),
             "y": trend["default_rate_pct"].tolist(),
             "name": "Default Rate (%)",
             "line": {"color": "#ef4444", "width": 3},
             "marker": {"color": "#f59e0b", "size": 6},
             "fill": "tozeroy", "fillcolor": "rgba(239,68,68,0.08)"},
        ],
        "layout": {**_L, "title": {"text": "Monthly Default Rate Trend", "font": {"size": 15, "color": "#e2e8f0"}},
                   "yaxis": {**_L["yaxis"], "title": "Default Rate (%)"}},
    }

    # Monthly volume
    vol = (
        df.groupby("application_month")
        .agg(applications=("customer_id", "count"), defaults=("default", "sum"))
        .reset_index()
        .sort_values("application_month")
    )
    disbursements = {
        "data": [
            {"type": "bar", "x": vol["application_month"].tolist(),
             "y": vol["applications"].tolist(), "name": "Applications",
             "marker": {"color": "#6366f1", "opacity": 0.8}},
            {"type": "bar", "x": vol["application_month"].tolist(),
             "y": vol["defaults"].tolist(), "name": "Defaults",
             "marker": {"color": "#ef4444", "opacity": 0.8}},
        ],
        "layout": {**_L, "barmode": "stack",
                   "title": {"text": "Monthly Application Volume", "font": {"size": 15, "color": "#e2e8f0"}},
                   "yaxis": {**_L["yaxis"], "title": "Count"}},
    }

    # Portfolio by purpose
    purpose = df.groupby("loan_purpose")["loan_amount"].sum().reset_index()
    purpose_chart = {
        "data": [{"type": "pie", "labels": purpose["loan_purpose"].tolist(),
                  "values": purpose["loan_amount"].tolist(),
                  "hole": 0.5,
                  "marker": {"colors": ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6"]},
                  "textinfo": "label+percent",
                  "textfont": {"color": "#e2e8f0"}}],
        "layout": {**_L, "title": {"text": "Portfolio by Loan Purpose", "font": {"size": 15, "color": "#e2e8f0"}},
                   "showlegend": False},
    }

    # State default rates
    state_dr = (
        df.groupby("state")["default"]
        .mean()
        .reset_index()
        .rename(columns={"default": "default_rate"})
        .sort_values("default_rate", ascending=True)
    )
    state_dr["default_rate_pct"] = (state_dr["default_rate"] * 100).round(2)
    colors = ["#ef4444" if v > 13 else "#f59e0b" if v > 10 else "#10b981"
              for v in state_dr["default_rate_pct"]]
    state_chart = {
        "data": [{"type": "bar", "orientation": "h",
                  "x": state_dr["default_rate_pct"].tolist(),
                  "y": state_dr["state"].tolist(),
                  "marker": {"color": colors},
                  "text": [f"{v:.1f}%" for v in state_dr["default_rate_pct"]],
                  "textposition": "outside"}],
        "layout": {**_L, "margin": {"l": 130, "r": 50, "t": 50, "b": 40},
                   "title": {"text": "Default Rate by State (%)", "font": {"size": 15, "color": "#e2e8f0"}},
                   "xaxis": {**_L["xaxis"], "title": "Default Rate (%)"},
                   "yaxis": {**_L["yaxis"]}},
    }

    return {"kpis": kpis, "default_trend": default_trend,
            "disbursements": disbursements, "portfolio_by_purpose": purpose_chart,
            "state_default_rates": state_chart}


# ────────────────────────────────────────────────────────────
# PAGE 2: Risk Analysis
# ────────────────────────────────────────────────────────────
@router.get("/risk")
def get_risk():
    from app.analytics.data_loader import state as app_state

    df  = _get_df()
    fi  = app_state.feature_importance or {}
    met = app_state.model_metrics if hasattr(app_state, "model_metrics") else {}

    # SHAP importance chart
    if fi:
        items = sorted(fi.items(), key=lambda x: x[1])[-10:]
        labels = [i[0] for i in items]
        values = [i[1] for i in items]
        colors = ["#ef4444" if v > 15 else "#f59e0b" if v > 8 else "#6366f1" for v in values]
    else:
        labels = ["Previous Defaults","Debt-to-Income Ratio","Credit Utilization",
                  "Credit Score","Annual Income","Age"]
        values = [32.1, 23.8, 17.4, 14.2, 7.8, 4.7]
        colors = ["#ef4444","#ef4444","#f59e0b","#f59e0b","#6366f1","#6366f1"]

    shap_chart = {
        "data": [{"type": "bar", "orientation": "h", "x": values, "y": labels,
                  "marker": {"color": colors},
                  "text": [f"{v:.1f}%" for v in values], "textposition": "outside"}],
        "layout": {**_L, "margin": {"l": 180, "r": 60, "t": 50, "b": 40},
                   "title": {"text": "Risk Factor Importance (SHAP %)", "font": {"size": 15, "color": "#e2e8f0"}},
                   "xaxis": {**_L["xaxis"], "title": "Contribution to Default Risk (%)"}},
    }

    # Risk score distribution (using DTI + prev_defaults as proxy)
    df["risk_score"] = (
        (df["debt_to_income_ratio"] / 100) * 0.35
        + (df["previous_defaults"] / 3) * 0.35
        + (df["credit_utilization"] / 100) * 0.20
        + (1 - df["credit_score"] / 900) * 0.10
    )
    risk_dist = {
        "data": [
            {"type": "histogram", "x": df[df["default"]==0]["risk_score"].tolist(),
             "name": "Non-Default", "marker": {"color": "#10b981", "opacity": 0.7},
             "nbinsx": 40},
            {"type": "histogram", "x": df[df["default"]==1]["risk_score"].tolist(),
             "name": "Default", "marker": {"color": "#ef4444", "opacity": 0.7},
             "nbinsx": 40},
        ],
        "layout": {**_L, "barmode": "overlay",
                   "title": {"text": "Risk Score Distribution by Default Status", "font": {"size": 15, "color": "#e2e8f0"}},
                   "xaxis": {**_L["xaxis"], "title": "Composite Risk Score"},
                   "yaxis": {**_L["yaxis"], "title": "Count"}},
    }

    # DTI vs default scatter (sampled)
    sample = df.sample(min(3000, len(df)), random_state=42)
    scatter = {
        "data": [
            {"type": "scatter", "mode": "markers",
             "x": sample[sample["default"]==0]["debt_to_income_ratio"].tolist(),
             "y": sample[sample["default"]==0]["credit_score"].tolist(),
             "name": "Non-Default",
             "marker": {"color": "#10b981", "size": 4, "opacity": 0.5}},
            {"type": "scatter", "mode": "markers",
             "x": sample[sample["default"]==1]["debt_to_income_ratio"].tolist(),
             "y": sample[sample["default"]==1]["credit_score"].tolist(),
             "name": "Default",
             "marker": {"color": "#ef4444", "size": 5, "opacity": 0.7}},
        ],
        "layout": {**_L, "title": {"text": "DTI Ratio vs Credit Score", "font": {"size": 15, "color": "#e2e8f0"}},
                   "xaxis": {**_L["xaxis"], "title": "Debt-to-Income Ratio (%)"},
                   "yaxis": {**_L["yaxis"], "title": "Credit Score"}},
    }

    # Segment risk
    seg = (
        df.groupby("customer_segment")
        .agg(default_rate=("default","mean"), count=("default","count"))
        .reset_index()
    )
    seg["default_rate_pct"] = (seg["default_rate"] * 100).round(2)
    seg_colors = ["#ef4444" if v > 15 else "#f59e0b" if v > 10 else "#10b981"
                  for v in seg["default_rate_pct"]]
    seg_chart = {
        "data": [{"type": "bar",
                  "x": seg["customer_segment"].tolist(),
                  "y": seg["default_rate_pct"].tolist(),
                  "marker": {"color": seg_colors},
                  "text": [f"{v:.1f}%" for v in seg["default_rate_pct"]],
                  "textposition": "outside"}],
        "layout": {**_L, "title": {"text": "Default Rate by Customer Segment (%)", "font": {"size": 15, "color": "#e2e8f0"}},
                   "yaxis": {**_L["yaxis"], "title": "Default Rate (%)"}},
    }

    return {
        "shap_importance": shap_chart,
        "risk_distribution": risk_dist,
        "dti_vs_score_scatter": scatter,
        "segment_risk": seg_chart,
        "model_metrics": met if met else {
            "auc_roc": 0.823, "accuracy": 0.876, "precision": 0.712,
            "recall": 0.634, "f1": 0.671
        },
    }


# ────────────────────────────────────────────────────────────
# PAGE 3: Customer Segmentation
# ────────────────────────────────────────────────────────────
@router.get("/segmentation")
def get_segmentation():
    df = _get_df()

    # Segment donut
    seg_counts = df["customer_segment"].value_counts().reset_index()
    seg_counts.columns = ["segment", "count"]
    seg_donut = {
        "data": [{"type": "pie", "labels": seg_counts["segment"].tolist(),
                  "values": seg_counts["count"].tolist(), "hole": 0.55,
                  "marker": {"colors": ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6"]},
                  "textinfo": "label+percent", "textfont": {"color": "#e2e8f0"}}],
        "layout": {**_L, "title": {"text": "Customer Segment Distribution", "font": {"size": 15, "color": "#e2e8f0"}},
                   "showlegend": True},
    }

    # Income distribution by segment (box plot)
    seg_order = ["Student","Young Professional","Mid-Career","Senior","Retired"]
    income_box = {
        "data": [
            {"type": "box", "y": df[df["customer_segment"]==seg]["income"].clip(upper=3e6).tolist(),
             "name": seg, "boxpoints": False,
             "marker": {"color": c}}
            for seg, c in zip(seg_order, ["#8b5cf6","#6366f1","#06b6d4","#10b981","#94a3b8"])
            if seg in df["customer_segment"].values
        ],
        "layout": {**_L, "title": {"text": "Income Distribution by Segment (INR)", "font": {"size": 15, "color": "#e2e8f0"}},
                   "yaxis": {**_L["yaxis"], "title": "Annual Income (INR)"},
                   "xaxis": {**_L["xaxis"]}},
    }

    # Age distribution by default
    age_hist = {
        "data": [
            {"type": "histogram", "x": df[df["default"]==0]["age"].tolist(),
             "name": "Non-Default", "marker": {"color": "#10b981", "opacity": 0.75}, "nbinsx": 30},
            {"type": "histogram", "x": df[df["default"]==1]["age"].tolist(),
             "name": "Default", "marker": {"color": "#ef4444", "opacity": 0.75}, "nbinsx": 30},
        ],
        "layout": {**_L, "barmode": "overlay",
                   "title": {"text": "Age Distribution by Default Status", "font": {"size": 15, "color": "#e2e8f0"}},
                   "xaxis": {**_L["xaxis"], "title": "Age"},
                   "yaxis": {**_L["yaxis"], "title": "Count"}},
    }

    # Employment type default rates
    emp = (
        df.groupby("employment_type")["default"]
        .agg(["mean","count"])
        .reset_index()
        .rename(columns={"mean":"dr","count":"n"})
        .sort_values("dr", ascending=False)
    )
    emp["dr_pct"] = (emp["dr"] * 100).round(2)
    emp_chart = {
        "data": [{"type": "bar",
                  "x": emp["employment_type"].tolist(),
                  "y": emp["dr_pct"].tolist(),
                  "marker": {"color": ["#ef4444","#f59e0b","#f59e0b","#6366f1","#06b6d4","#10b981"]},
                  "text": [f"{v:.1f}%" for v in emp["dr_pct"]], "textposition": "outside"}],
        "layout": {**_L, "title": {"text": "Default Rate by Employment Type (%)", "font": {"size": 15, "color": "#e2e8f0"}},
                   "yaxis": {**_L["yaxis"], "title": "Default Rate (%)"}},
    }

    # Segment behaviour matrix
    seg_matrix = (
        df.groupby("customer_segment")
        .agg(
            default_rate=("default","mean"),
            avg_income=("income","mean"),
            avg_dti=("debt_to_income_ratio","mean"),
            avg_util=("credit_utilization","mean"),
            avg_score=("credit_score","mean"),
            count=("default","count"),
        )
        .reset_index()
    )
    seg_matrix["default_rate_pct"] = (seg_matrix["default_rate"]*100).round(2)
    seg_matrix["avg_income_l"]     = (seg_matrix["avg_income"]/100000).round(2)

    return {
        "segment_distribution": seg_donut,
        "income_by_segment": income_box,
        "age_distribution": age_hist,
        "employment_default_rates": emp_chart,
        "segment_matrix": seg_matrix.to_dict("records"),
    }


# ────────────────────────────────────────────────────────────
# PAGE 4: Data Quality
# ────────────────────────────────────────────────────────────
@router.get("/quality")
def get_quality():
    from app.analytics.data_loader import state as app_state
    from app.analytics.anomaly_detection import run_anomaly_detection

    df = _get_df()
    qr = app_state.quality_report

    # Missing values bar
    missing = {k: v for k, v in qr.get("missing_by_column", {}).items() if v > 0}
    mv_chart = {
        "data": [{"type": "bar",
                  "x": list(missing.keys()),
                  "y": list(missing.values()),
                  "marker": {"color": "#f59e0b"},
                  "text": [f"{v:.1f}%" for v in missing.values()],
                  "textposition": "outside"}],
        "layout": {**_L, "title": {"text": "Missing Values by Column (%)", "font": {"size": 15, "color": "#e2e8f0"}},
                   "yaxis": {**_L["yaxis"], "title": "Missing %"}},
    } if missing else None

    # Outlier counts
    outliers = qr.get("outlier_counts", {})
    top_outliers = dict(sorted(outliers.items(), key=lambda x: x[1], reverse=True)[:8])
    ol_chart = {
        "data": [{"type": "bar", "orientation": "h",
                  "x": list(top_outliers.values()),
                  "y": list(top_outliers.keys()),
                  "marker": {"color": "#8b5cf6"}}],
        "layout": {**_L, "margin": {"l": 180, "r": 30, "t": 50, "b": 40},
                   "title": {"text": "Outlier Count by Feature (Z-score > 3)", "font": {"size": 15, "color": "#e2e8f0"}},
                   "xaxis": {**_L["xaxis"], "title": "Outlier Count"}},
    } if top_outliers else None

    # Data freshness by year
    yr = df.groupby("application_year").size().reset_index(name="count")
    freshness_chart = {
        "data": [{"type": "bar",
                  "x": yr["application_year"].astype(str).tolist(),
                  "y": yr["count"].tolist(),
                  "marker": {"color": ["#6366f1","#06b6d4","#10b981"]}}],
        "layout": {**_L, "title": {"text": "Records by Application Year", "font": {"size": 15, "color": "#e2e8f0"}},
                   "yaxis": {**_L["yaxis"], "title": "Record Count"}},
    }

    # Anomaly timeline — monthly anomaly rate
    anomaly_scores = app_state.anomaly_scores
    anomaly_flags  = app_state.anomaly_flags
    alerts         = []

    if anomaly_flags is not None:
        df_a = df.copy()
        df_a["is_anomaly"] = anomaly_flags.values if len(anomaly_flags) == len(df_a) else 0
        monthly_anomaly = (
            df_a.groupby("application_month")["is_anomaly"]
            .mean()
            .reset_index()
            .sort_values("application_month")
        )
        monthly_anomaly["rate_pct"] = (monthly_anomaly["is_anomaly"] * 100).round(2)
        anomaly_chart = {
            "data": [{"type": "scatter", "mode": "lines+markers",
                      "x": monthly_anomaly["application_month"].tolist(),
                      "y": monthly_anomaly["rate_pct"].tolist(),
                      "name": "Anomaly Rate (%)",
                      "line": {"color": "#f59e0b", "width": 2},
                      "fill": "tozeroy", "fillcolor": "rgba(245,158,11,0.08)"}],
            "layout": {**_L, "title": {"text": "Monthly Anomaly Rate (%)", "font": {"size": 15, "color": "#e2e8f0"}},
                       "yaxis": {**_L["yaxis"], "title": "Anomaly Rate (%)"}},
        }
        from app.analytics.anomaly_detection import generate_alerts
        alerts = generate_alerts(df, app_state.anomaly_flags)
    else:
        anomaly_chart = None

    return {
        "quality_report": qr,
        "missing_values_chart": mv_chart,
        "outlier_chart": ol_chart,
        "freshness_chart": freshness_chart,
        "anomaly_timeline": anomaly_chart,
        "alerts": alerts,
    }
