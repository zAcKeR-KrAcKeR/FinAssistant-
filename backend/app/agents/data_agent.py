"""
Data Analysis Module
====================
Translates an IntentResult into actual pandas computations on the dataset.
Returns a DataResult containing:
  - summary statistics
  - aggregated DataFrame
  - Plotly chart specification (JSON-serialisable dict)
  - metadata for evidence-based responses
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.agents.intent_agent import IntentResult

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Plotly dark theme (consistent across all charts)
# ──────────────────────────────────────────────────────────
DARK_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor":  "rgba(0,0,0,0)",
    "font":          {"color": "#e2e8f0", "family": "Inter, sans-serif"},
    "xaxis":         {"gridcolor": "rgba(255,255,255,0.06)", "color": "#94a3b8",
                      "linecolor": "rgba(255,255,255,0.1)"},
    "yaxis":         {"gridcolor": "rgba(255,255,255,0.06)", "color": "#94a3b8",
                      "linecolor": "rgba(255,255,255,0.1)"},
    "legend":        {"bgcolor": "rgba(0,0,0,0)", "font": {"color": "#e2e8f0"}},
    "margin":        {"l": 40, "r": 20, "t": 40, "b": 40},
    "colorway":      ["#6366f1", "#06b6d4", "#10b981", "#f59e0b", "#ef4444",
                      "#8b5cf6", "#ec4899", "#14b8a6"],
}

COLORS = {
    "primary":   "#6366f1",
    "secondary": "#06b6d4",
    "success":   "#10b981",
    "warning":   "#f59e0b",
    "danger":    "#ef4444",
    "purple":    "#8b5cf6",
}


# ──────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────
@dataclass
class DataResult:
    records_count: int = 0
    metric_description: str = ""
    summary_stats: dict = field(default_factory=dict)
    table: list[dict] = field(default_factory=list)   # top rows as records
    chart: dict | None = None                          # Plotly spec
    key_values: dict = field(default_factory=dict)    # for text generation


# ──────────────────────────────────────────────────────────
# Chart builders
# ──────────────────────────────────────────────────────────
def _bar_chart(
    x: list, y: list, title: str, xlab: str, ylab: str,
    color: str = "#6366f1", orientation: str = "v",
) -> dict:
    layout = {**DARK_LAYOUT, "title": {"text": title, "font": {"size": 16, "color": "#e2e8f0"}}}
    if orientation == "h":
        return {
            "data": [{"type": "bar", "x": y, "y": x, "orientation": "h",
                      "marker": {"color": color, "opacity": 0.85}}],
            "layout": {**layout, "xaxis": {**DARK_LAYOUT["xaxis"], "title": ylab},
                       "yaxis": {**DARK_LAYOUT["yaxis"], "title": xlab, "autorange": "reversed"}},
        }
    return {
        "data": [{"type": "bar", "x": x, "y": y,
                  "marker": {"color": color, "opacity": 0.85}}],
        "layout": {**layout, "xaxis": {**DARK_LAYOUT["xaxis"], "title": xlab},
                   "yaxis": {**DARK_LAYOUT["yaxis"], "title": ylab}},
    }


def _line_chart(x: list, y: list, title: str, xlab: str, ylab: str) -> dict:
    layout = {**DARK_LAYOUT, "title": {"text": title, "font": {"size": 16, "color": "#e2e8f0"}}}
    return {
        "data": [{
            "type": "scatter", "mode": "lines+markers",
            "x": x, "y": y,
            "line":   {"color": COLORS["primary"], "width": 3},
            "marker": {"color": COLORS["secondary"], "size": 7},
        }],
        "layout": {**layout,
                   "xaxis": {**DARK_LAYOUT["xaxis"], "title": xlab},
                   "yaxis": {**DARK_LAYOUT["yaxis"], "title": ylab}},
    }


def _multi_bar_chart(groups: dict, x_labels: list, title: str) -> dict:
    layout = {**DARK_LAYOUT, "title": {"text": title, "font": {"size": 16, "color": "#e2e8f0"}},
              "barmode": "group"}
    data = []
    colors = list(COLORS.values())
    for i, (name, values) in enumerate(groups.items()):
        data.append({
            "type": "bar", "name": name,
            "x": x_labels, "y": values,
            "marker": {"color": colors[i % len(colors)]},
        })
    return {"data": data, "layout": layout}


# ──────────────────────────────────────────────────────────
# Analysis routines
# ──────────────────────────────────────────────────────────
def _analyse_summary(df: pd.DataFrame) -> DataResult:
    r = DataResult(records_count=len(df))
    r.metric_description = "overall portfolio summary"
    dr = df["default"].mean() * 100
    r.summary_stats = {
        "total_records":        len(df),
        "overall_default_rate": round(dr, 2),
        "avg_credit_score":     round(df["credit_score"].mean(), 0),
        "avg_income":           round(df["income"].mean(), 0),
        "avg_loan_amount":      round(df["loan_amount"].mean(), 0),
        "avg_dti":              round(df["debt_to_income_ratio"].mean(), 2),
        "high_risk_count":      int((df["previous_defaults"] >= 2).sum()),
        "avg_credit_util":      round(df["credit_utilization"].mean(), 2),
    }
    r.key_values = r.summary_stats
    return r


def _analyse_aggregation(df: pd.DataFrame, group_col: str | None) -> DataResult:
    col = group_col or "state"
    if col not in df.columns:
        col = "state"

    grp = (
        df.groupby(col)
        .agg(
            default_rate=("default", "mean"),
            total_records=("default", "count"),
            total_defaults=("default", "sum"),
            avg_credit_score=("credit_score", "mean"),
            avg_dti=("debt_to_income_ratio", "mean"),
            avg_income=("income", "mean"),
        )
        .reset_index()
    )
    grp["default_rate"] = (grp["default_rate"] * 100).round(2)
    grp["avg_credit_score"] = grp["avg_credit_score"].round(0)
    grp["avg_dti"] = grp["avg_dti"].round(2)
    grp["avg_income"] = grp["avg_income"].round(0)
    grp = grp.sort_values("default_rate", ascending=False)

    chart = _bar_chart(
        x=grp[col].tolist(),
        y=grp["default_rate"].tolist(),
        title=f"Default Rate by {col.replace('_', ' ').title()} (%)",
        xlab=col.replace("_", " ").title(),
        ylab="Default Rate (%)",
    )

    r = DataResult(records_count=len(df))
    r.metric_description = f"default rate grouped by {col}"
    r.table = grp.head(15).to_dict("records")
    r.chart = chart
    r.key_values = {
        "highest_group":      str(grp.iloc[0][col]),
        "highest_rate":       float(grp.iloc[0]["default_rate"]),
        "lowest_group":       str(grp.iloc[-1][col]),
        "lowest_rate":        float(grp.iloc[-1]["default_rate"]),
        "group_column":       col,
        "overall_avg":        round(df["default"].mean() * 100, 2),
    }
    return r


def _analyse_ranking(df: pd.DataFrame, group_col: str | None, top_n: int | None) -> DataResult:
    n = top_n or 5
    col = group_col or "state"
    if col not in df.columns:
        col = "state"

    ranked = (
        df.groupby(col)["default"]
        .agg(["mean", "count", "sum"])
        .rename(columns={"mean": "default_rate", "count": "records", "sum": "defaults"})
        .reset_index()
    )
    ranked["default_rate"] = (ranked["default_rate"] * 100).round(2)
    ranked = ranked.sort_values("default_rate", ascending=False).head(n)

    chart = _bar_chart(
        x=ranked["default_rate"].tolist(),
        y=ranked[col].tolist(),
        title=f"Top {n} {col.replace('_',' ').title()} by Default Rate",
        xlab="Default Rate (%)",
        ylab=col.replace("_", " ").title(),
        orientation="h",
        color=COLORS["danger"],
    )

    r = DataResult(records_count=len(df))
    r.metric_description = f"top {n} {col} by default rate"
    r.table = ranked.to_dict("records")
    r.chart = chart
    r.key_values = {
        "top_n": n,
        "group_column": col,
        "top_results": ranked.head(3).to_dict("records"),
    }
    return r


def _analyse_trend(df: pd.DataFrame, time_dim: str | None) -> DataResult:
    dim = time_dim or "monthly"
    col_map = {
        "monthly":   "application_month",
        "quarterly": "application_quarter",
        "yearly":    "application_year",
    }
    col = col_map.get(dim, "application_month")
    if col not in df.columns:
        col = "application_month"

    trend = (
        df.groupby(col)["default"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "default_rate", "count": "volume"})
        .reset_index()
        .sort_values(col)
    )
    trend["default_rate_pct"] = (trend["default_rate"] * 100).round(2)

    layout = {
        **DARK_LAYOUT,
        "title": {"text": f"Default Rate Trend ({dim.title()})", "font": {"size": 16, "color": "#e2e8f0"}},
    }
    chart = {
        "data": [
            {
                "type": "scatter", "mode": "lines+markers",
                "x": trend[col].astype(str).tolist(),
                "y": trend["default_rate_pct"].tolist(),
                "name": "Default Rate (%)",
                "line":   {"color": COLORS["danger"], "width": 3},
                "marker": {"size": 7},
                "yaxis": "y",
            },
            {
                "type": "bar",
                "x": trend[col].astype(str).tolist(),
                "y": trend["volume"].tolist(),
                "name": "Applications",
                "marker": {"color": COLORS["primary"], "opacity": 0.4},
                "yaxis": "y2",
            },
        ],
        "layout": {
            **layout,
            "yaxis":  {**DARK_LAYOUT["yaxis"], "title": "Default Rate (%)"},
            "yaxis2": {"title": "Applications", "overlaying": "y", "side": "right",
                       "gridcolor": "rgba(0,0,0,0)", "color": "#94a3b8"},
        },
    }

    peak_idx    = trend["default_rate_pct"].idxmax()
    trough_idx  = trend["default_rate_pct"].idxmin()

    r = DataResult(records_count=len(df))
    r.metric_description = f"{dim} default rate trend"
    r.table  = trend.head(36).to_dict("records")
    r.chart  = chart
    r.key_values = {
        "time_dimension":  dim,
        "time_column":     col,
        "peak_period":     str(trend.loc[peak_idx, col]),
        "peak_rate":       float(trend.loc[peak_idx, "default_rate_pct"]),
        "trough_period":   str(trend.loc[trough_idx, col]),
        "trough_rate":     float(trend.loc[trough_idx, "default_rate_pct"]),
        "latest_rate":     float(trend.iloc[-1]["default_rate_pct"]),
        "first_rate":      float(trend.iloc[0]["default_rate_pct"]),
        "change_pct":      round(
            float(trend.iloc[-1]["default_rate_pct"]) - float(trend.iloc[0]["default_rate_pct"]), 2
        ),
    }
    return r


def _analyse_segmentation(df: pd.DataFrame, group_col: str | None) -> DataResult:
    col = group_col or "customer_segment"
    if col not in df.columns:
        col = "customer_segment"

    seg = (
        df.groupby(col)
        .agg(
            default_rate=("default", "mean"),
            count=("default", "count"),
            avg_credit_score=("credit_score", "mean"),
            avg_income=("income", "mean"),
            avg_dti=("debt_to_income_ratio", "mean"),
            avg_util=("credit_utilization", "mean"),
        )
        .reset_index()
    )
    seg["default_rate_pct"] = (seg["default_rate"] * 100).round(2)
    seg["avg_credit_score"]  = seg["avg_credit_score"].round(0)
    seg["avg_income"]        = seg["avg_income"].round(0)
    seg["avg_dti"]           = seg["avg_dti"].round(2)
    seg["avg_util"]          = seg["avg_util"].round(2)
    seg = seg.sort_values("default_rate_pct", ascending=False)

    chart = _multi_bar_chart(
        groups={
            "Default Rate (%)":    seg["default_rate_pct"].tolist(),
            "Avg DTI (%)":         seg["avg_dti"].tolist(),
            "Avg Credit Util (%)": seg["avg_util"].tolist(),
        },
        x_labels=seg[col].tolist(),
        title=f"Segment Risk Profile — {col.replace('_',' ').title()}",
    )

    r = DataResult(records_count=len(df))
    r.metric_description = f"segmentation by {col}"
    r.table  = seg.to_dict("records")
    r.chart  = chart
    r.key_values = {
        "group_column":    col,
        "highest_risk_segment":  str(seg.iloc[0][col]),
        "highest_risk_rate":     float(seg.iloc[0]["default_rate_pct"]),
        "lowest_risk_segment":   str(seg.iloc[-1][col]),
        "lowest_risk_rate":      float(seg.iloc[-1]["default_rate_pct"]),
        "segments": seg[[col, "default_rate_pct", "count"]].to_dict("records"),
    }
    return r


# ──────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────
def analyse(intent: IntentResult, df: pd.DataFrame) -> DataResult:
    """Route intent to appropriate analysis function."""
    i = intent.intent

    if i in ("summary", "executive_summary", "policy_query"):
        return _analyse_summary(df)

    elif i in ("aggregation", "filter"):
        return _analyse_aggregation(df, intent.group_by_column)

    elif i == "ranking":
        return _analyse_ranking(df, intent.group_by_column, intent.top_n)

    elif i == "trend":
        return _analyse_trend(df, intent.time_dimension)

    elif i in ("segmentation", "risk_analysis", "explanation"):
        return _analyse_segmentation(df, intent.group_by_column)

    elif i == "anomaly":
        return _analyse_summary(df)     # anomaly module handles details separately

    elif i == "what_if":
        return _analyse_summary(df)     # what-if module overrides

    else:
        return _analyse_summary(df)
