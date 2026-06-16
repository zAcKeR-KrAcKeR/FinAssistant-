"""
Anomaly Detection
==================
Three complementary methods:
  1. Isolation Forest — unsupervised, catches multivariate outliers
  2. Z-score per numeric column — univariate statistical outliers
  3. IQR — distribution-based outliers

Results are stored in the AppState as anomaly_scores / anomaly_flags
and surfaced as real-time Risk Alerts in the dashboard.
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.analytics.data_loader import NUMERIC_FEATURES

logger = logging.getLogger(__name__)

CONTAMINATION = 0.05     # expected fraction of anomalies


# ──────────────────────────────────────────────────────────
# Isolation Forest
# ──────────────────────────────────────────────────────────
def run_isolation_forest(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Return (anomaly_scores, anomaly_flags).  Flag = 1 means anomaly."""
    cols = [c for c in NUMERIC_FEATURES if c in df.columns]
    X = df[cols].fillna(df[cols].median())

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    iso = IsolationForest(
        n_estimators=100,
        contamination=CONTAMINATION,
        random_state=42,
        n_jobs=-1,
    )
    iso.fit(X_scaled)

    # score_samples returns negative anomaly score; more negative = more anomalous
    raw_scores  = iso.score_samples(X_scaled)
    flags       = pd.Series((iso.predict(X_scaled) == -1).astype(int), index=df.index)
    scores      = pd.Series(-raw_scores, index=df.index)   # invert so higher = more anomalous

    logger.info(f"Isolation Forest: {flags.sum():,} anomalies detected ({flags.mean()*100:.1f}%)")
    return scores, flags


# ──────────────────────────────────────────────────────────
# Z-score anomalies
# ──────────────────────────────────────────────────────────
def zscore_outliers(df: pd.DataFrame, threshold: float = 3.5) -> pd.DataFrame:
    cols = [c for c in NUMERIC_FEATURES if c in df.columns]
    num  = df[cols].fillna(df[cols].median())
    z    = (num - num.mean()) / num.std()
    result = []
    for col in cols:
        mask = z[col].abs() > threshold
        outlier_rows = df[mask][["customer_id", col]].copy()
        outlier_rows["feature"] = col
        outlier_rows["z_score"] = z.loc[mask, col].round(2)
        outlier_rows["value"]   = outlier_rows[col]
        result.append(outlier_rows[["customer_id", "feature", "value", "z_score"]])
    if result:
        return pd.concat(result, ignore_index=True)
    return pd.DataFrame(columns=["customer_id", "feature", "value", "z_score"])


# ──────────────────────────────────────────────────────────
# IQR outliers
# ──────────────────────────────────────────────────────────
def iqr_outliers(df: pd.DataFrame, multiplier: float = 2.5) -> dict:
    cols = [c for c in NUMERIC_FEATURES if c in df.columns]
    num  = df[cols].fillna(df[cols].median())
    Q1, Q3 = num.quantile(0.25), num.quantile(0.75)
    IQR = Q3 - Q1
    lower, upper = Q1 - multiplier * IQR, Q3 + multiplier * IQR

    result = {}
    for col in cols:
        mask = (num[col] < lower[col]) | (num[col] > upper[col])
        result[col] = {
            "count": int(mask.sum()),
            "pct": round(mask.mean() * 100, 2),
            "lower_bound": round(float(lower[col]), 2),
            "upper_bound": round(float(upper[col]), 2),
        }
    return result


# ──────────────────────────────────────────────────────────
# Alert generation
# ──────────────────────────────────────────────────────────
def generate_alerts(df: pd.DataFrame, anomaly_flags: pd.Series) -> list[dict]:
    """Generate human-readable Risk Alerts for the dashboard."""
    alerts = []
    anomalies = df[anomaly_flags == 1]

    if len(anomalies) == 0:
        return alerts

    # Alert 1: Anomaly concentration by state
    state_anomaly = (
        anomalies.groupby("state").size()
        / df.groupby("state").size()
        * 100
    ).sort_values(ascending=False)

    top_state = state_anomaly.index[0]
    top_pct   = round(state_anomaly.iloc[0], 1)
    if top_pct > 8:
        alerts.append({
            "id":       "state_concentration",
            "severity": "HIGH" if top_pct > 15 else "MEDIUM",
            "title":    f"Anomaly Concentration — {top_state}",
            "message":  (
                f"{top_pct}% of {top_state} applicants show anomalous behaviour patterns, "
                f"compared to {CONTAMINATION*100:.0f}% expected. "
                f"Recommend enhanced manual review for this region."
            ),
            "detected_at": datetime.utcnow().isoformat(),
            "records_affected": int(state_anomaly.iloc[0] / 100 * df[df["state"] == top_state].shape[0]),
        })

    # Alert 2: DTI spike
    high_dti = anomalies[anomalies["debt_to_income_ratio"] > 60]
    if len(high_dti) > 50:
        alerts.append({
            "id":       "high_dti_spike",
            "severity": "HIGH",
            "title":    "Elevated Debt-to-Income Ratio Detected",
            "message":  (
                f"{len(high_dti):,} anomalous customers have DTI > 60%. "
                f"Average DTI in this group: {high_dti['debt_to_income_ratio'].mean():.1f}%. "
                f"Strong predictor of default — recommend immediate underwriting review."
            ),
            "detected_at": datetime.utcnow().isoformat(),
            "records_affected": len(high_dti),
        })

    # Alert 3: Young + high credit utilization
    young_util = anomalies[
        (anomalies["age"] < 30) & (anomalies["credit_utilization"] > 75)
    ]
    if len(young_util) > 20:
        alerts.append({
            "id":       "young_high_utilization",
            "severity": "MEDIUM",
            "title":    "Young Borrowers with High Credit Utilization",
            "message":  (
                f"{len(young_util):,} customers under 30 show anomalous credit utilization (>75%). "
                f"This segment historically has {18:.0f}% default rate. "
                f"Consider credit counselling programme."
            ),
            "detected_at": datetime.utcnow().isoformat(),
            "records_affected": len(young_util),
        })

    # Alert 4: Previous defaults + new applications
    repeat_defaulters = anomalies[anomalies["previous_defaults"] >= 2]
    if len(repeat_defaulters) > 10:
        alerts.append({
            "id":       "repeat_defaulters",
            "severity": "CRITICAL",
            "title":    "Repeat Default Applicants in Anomaly Pool",
            "message":  (
                f"{len(repeat_defaulters):,} applicants with 2+ previous defaults show "
                f"anomalous application patterns. Recommend automatic escalation to senior underwriting."
            ),
            "detected_at": datetime.utcnow().isoformat(),
            "records_affected": len(repeat_defaulters),
        })

    return alerts


# ──────────────────────────────────────────────────────────
# Master function
# ──────────────────────────────────────────────────────────
def run_anomaly_detection(df: pd.DataFrame) -> dict:
    """Full anomaly detection pipeline. Returns results dict."""
    scores, flags = run_isolation_forest(df)
    z_outliers    = zscore_outliers(df)
    iqr_summary   = iqr_outliers(df)
    alerts        = generate_alerts(df, flags)

    logger.info(f"Anomaly detection complete — {len(alerts)} alerts generated")

    return {
        "anomaly_scores":   scores,
        "anomaly_flags":    flags,
        "zscore_outliers":  z_outliers,
        "iqr_summary":      iqr_summary,
        "alerts":           alerts,
        "total_anomalies":  int(flags.sum()),
        "anomaly_rate_pct": round(flags.mean() * 100, 2),
    }
