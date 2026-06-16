"""
ML Model — RandomForest Credit Risk Classifier + SHAP Explainability
=====================================================================
Trains a Random Forest on the synthetic credit risk dataset.
Computes global SHAP values on a held-out sample for the Risk Analysis
dashboard and per-query explanations in the Risk Assessment Agent.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    roc_auc_score,
    confusion_matrix,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.analytics.data_loader import ML_FEATURES, TARGET

logger = logging.getLogger(__name__)

SHAP_SAMPLE_SIZE = 1000  # SHAP computed on this many rows (speed)


# ──────────────────────────────────────────────────────────
# Training
# ──────────────────────────────────────────────────────────
def train_model(df_ml: pd.DataFrame, n_estimators: int = 100, max_depth: int = 12):
    """Train RandomForest; return (model, metrics_dict, scaler)."""
    X = df_ml[ML_FEATURES]
    y = df_ml[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    rf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=10,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )
    rf.fit(X_train, y_train)

    y_pred = rf.predict(X_test)
    y_prob = rf.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_prob)
    cm  = confusion_matrix(y_test, y_pred).tolist()
    report = classification_report(y_test, y_pred, output_dict=True)

    fpr, tpr, _ = roc_curve(y_test, y_prob)

    metrics = {
        "auc_roc": round(auc, 4),
        "accuracy": round(report["accuracy"], 4),
        "precision": round(report["1"]["precision"], 4),
        "recall": round(report["1"]["recall"], 4),
        "f1": round(report["1"]["f1-score"], 4),
        "confusion_matrix": cm,
        "roc_curve": {
            "fpr": fpr.tolist()[::5],    # downsample for JSON size
            "tpr": tpr.tolist()[::5],
        },
        "test_size": len(X_test),
        "train_size": len(X_train),
    }

    logger.info(
        f"Model trained — AUC-ROC: {auc:.4f} | "
        f"Accuracy: {report['accuracy']:.4f} | "
        f"F1 (default): {report['1']['f1-score']:.4f}"
    )
    return rf, metrics


# ──────────────────────────────────────────────────────────
# SHAP explainability
# ──────────────────────────────────────────────────────────
def build_shap_explainer(
    model: RandomForestClassifier,
    df_ml: pd.DataFrame,
    feature_names: list[str] | None = None,
) -> tuple[Any, Any, dict]:
    """
    Returns (explainer, shap_values_sample, feature_importance_dict).
    shap_values_sample shape: (SHAP_SAMPLE_SIZE, n_features)
    """
    X = df_ml[ML_FEATURES]
    sample = X.sample(min(SHAP_SAMPLE_SIZE, len(X)), random_state=42)

    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(sample)

    # SHAP 0.45-: list [neg_class_arr, pos_class_arr]
    # SHAP 0.52+: single 3D ndarray (samples, features, classes)
    if isinstance(sv, list):
        sv_positive = np.array(sv[1])          # old API
    elif isinstance(sv, np.ndarray) and sv.ndim == 3:
        sv_positive = sv[:, :, 1]              # new API — take class 1
    else:
        sv_positive = np.array(sv)

    # Mean absolute SHAP → global importance (all scalars, no array ambiguity)
    mean_abs = np.abs(sv_positive).mean(axis=0)   # shape: (n_features,)
    total    = float(mean_abs.sum())
    importance = {
        feat: round(float(imp) / total * 100, 2)
        for feat, imp in sorted(
            zip(ML_FEATURES, mean_abs.tolist()),   # tolist() → plain Python floats
            key=lambda x: x[1],
            reverse=True,
        )
    }

    # Human-readable name mapping
    readable = {
        "previous_defaults":    "Previous Defaults",
        "debt_to_income_ratio": "Debt-to-Income Ratio",
        "credit_utilization":   "Credit Utilization",
        "credit_score":         "Credit Score",
        "income":               "Annual Income",
        "age":                  "Age",
        "loan_amount":          "Loan Amount",
        "savings_ratio":        "Savings Ratio",
        "num_credit_accounts":  "No. of Credit Accounts",
        "loan_term_months":     "Loan Term (months)",
        "interest_rate":        "Interest Rate",
    }

    importance_readable = {}
    for k, v in list(importance.items())[:12]:
        label = readable.get(k, k.replace("_enc", "").replace("_", " ").title())
        importance_readable[label] = v

    logger.info(
        f"SHAP computed on {len(sample)} samples. "
        f"Top driver: {list(importance_readable.keys())[0]}"
    )
    return explainer, sv_positive, importance_readable


# ──────────────────────────────────────────────────────────
# Per-customer risk score
# ──────────────────────────────────────────────────────────
def predict_risk(
    model: RandomForestClassifier,
    explainer,
    shap_values_sample,
    customer_row: pd.DataFrame,
) -> dict:
    """Compute default probability + SHAP breakdown for one customer."""
    X = customer_row[ML_FEATURES]
    prob = model.predict_proba(X)[:, 1][0]
    sv   = explainer.shap_values(X)
    if isinstance(sv, list):
        sv_row = np.array(sv[1])[0]
    elif isinstance(sv, np.ndarray) and sv.ndim == 3:
        sv_row = sv[0, :, 1]          # new API
    else:
        sv_row = np.array(sv)[0]

    readable = {
        "previous_defaults":    "Previous Defaults",
        "debt_to_income_ratio": "Debt-to-Income Ratio",
        "credit_utilization":   "Credit Utilization",
        "credit_score":         "Credit Score",
        "income":               "Annual Income",
        "age":                  "Age",
        "loan_amount":          "Loan Amount",
        "savings_ratio":        "Savings Ratio",
    }

    breakdown = sorted(
        [
            {
                "factor": readable.get(f, f.replace("_enc","").replace("_"," ").title()),
                "shap_value": round(float(s), 4),
                "impact": "increases" if s > 0 else "decreases",
                "impact_pct": round(abs(float(s)) / abs(sv_row).sum() * 100, 1),
            }
            for f, s in zip(ML_FEATURES, sv_row)
        ],
        key=lambda x: abs(x["shap_value"]),
        reverse=True,
    )[:8]

    risk_tier = (
        "Critical" if prob > 0.60
        else "High" if prob > 0.40
        else "Medium" if prob > 0.20
        else "Low"
    )

    return {
        "default_probability_pct": round(prob * 100, 1),
        "risk_tier": risk_tier,
        "shap_breakdown": breakdown,
    }
