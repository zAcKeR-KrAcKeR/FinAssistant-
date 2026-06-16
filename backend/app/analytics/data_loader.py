"""
Data Loader & Preprocessor
===========================
Loads the raw synthetic dataset, performs data quality assessment,
cleans and preprocesses features for downstream analytics and ML.
Exposes a global `AppState` singleton that holds all runtime objects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.data.generate_dataset import generate_dataset

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Categorical feature order used consistently across ML + API
# ──────────────────────────────────────────────────────────
CATEGORICAL_FEATURES = [
    "employment_type", "state", "loan_purpose",
    "marital_status", "education", "customer_segment", "income_bracket",
]

NUMERIC_FEATURES = [
    "age", "income", "credit_score", "loan_amount",
    "loan_term_months", "debt_to_income_ratio", "previous_defaults",
    "credit_utilization", "num_credit_accounts", "savings_ratio",
    "interest_rate",
]

ML_FEATURES = NUMERIC_FEATURES + [f"{c}_enc" for c in CATEGORICAL_FEATURES]

TARGET = "default"


# ──────────────────────────────────────────────────────────
# App-level singleton
# ──────────────────────────────────────────────────────────
@dataclass
class AppState:
    df_raw: pd.DataFrame | None = None
    df_clean: pd.DataFrame | None = None
    df_ml: pd.DataFrame | None = None          # features only (encoded)
    label_encoders: dict = field(default_factory=dict)
    quality_report: dict = field(default_factory=dict)
    model: Any = None
    shap_explainer: Any = None
    shap_values_sample: Any = None
    feature_importance: dict = field(default_factory=dict)
    anomaly_scores: pd.Series | None = None
    anomaly_flags: pd.Series | None = None
    rag: Any = None
    ready: bool = False


# Module-level singleton
state = AppState()


# ──────────────────────────────────────────────────────────
# Quality assessment
# ──────────────────────────────────────────────────────────
def _assess_quality(df: pd.DataFrame) -> dict:
    n = len(df)
    missing_pct = (df.isna().sum() / n * 100).round(2).to_dict()
    missing_cols = {k: v for k, v in missing_pct.items() if v > 0}

    numeric_df = df.select_dtypes(include="number")
    z_scores = ((numeric_df - numeric_df.mean()) / numeric_df.std()).abs()
    outlier_counts = (z_scores > 3).sum().to_dict()

    duplicates = int(df.duplicated().sum())

    overall_score = max(
        0,
        100
        - sum(missing_cols.values())
        - (duplicates / n * 100)
        - (sum(outlier_counts.values()) / (n * len(outlier_counts)) * 100 if outlier_counts else 0),
    )

    return {
        "total_records": n,
        "missing_by_column": missing_cols,
        "total_missing_pct": round(df.isna().any(axis=1).mean() * 100, 2),
        "duplicate_records": duplicates,
        "outlier_counts": outlier_counts,
        "overall_health_score": round(overall_score, 1),
        "date_range_start": str(df["application_date"].min().date()),
        "date_range_end": str(df["application_date"].max().date()),
        "columns": list(df.columns),
        "default_rate_pct": round(df["default"].mean() * 100, 2),
    }


# ──────────────────────────────────────────────────────────
# Cleaning
# ──────────────────────────────────────────────────────────
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Fill missing income with segment median
    seg_med = df.groupby("customer_segment")["income"].transform("median")
    df["income"] = df["income"].fillna(seg_med)

    # Fill missing savings_ratio with 0 (unknown = assume none)
    df["savings_ratio"] = df["savings_ratio"].fillna(0.0)

    # Fill missing education with mode
    edu_mode = df["education"].mode()[0]
    df["education"] = df["education"].fillna(edu_mode)

    # Drop any remaining NAs (should be 0 after above)
    df = df.dropna(subset=NUMERIC_FEATURES + [TARGET])
    df = df.drop_duplicates(subset="customer_id")

    return df.reset_index(drop=True)


# ──────────────────────────────────────────────────────────
# Label encoding for ML
# ──────────────────────────────────────────────────────────
def _encode(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    from sklearn.preprocessing import LabelEncoder

    encoders: dict[str, LabelEncoder] = {}
    df = df.copy()
    for col in CATEGORICAL_FEATURES:
        le = LabelEncoder()
        df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
        encoders[col] = le
    return df, encoders


# ──────────────────────────────────────────────────────────
# Public entry-point
# ──────────────────────────────────────────────────────────
def load_and_prepare(n_records: int = 30_000, seed: int = 42) -> AppState:
    """Generate → assess → clean → encode. Populates global `state`."""
    logger.info("Loading and preparing dataset …")

    state.df_raw = generate_dataset(n=n_records, seed=seed)
    state.quality_report = _assess_quality(state.df_raw)

    logger.info(
        f"Quality report: health={state.quality_report['overall_health_score']}, "
        f"missing={state.quality_report['total_missing_pct']}%, "
        f"duplicates={state.quality_report['duplicate_records']}"
    )

    state.df_clean = _clean(state.df_raw)
    state.df_clean, state.label_encoders = _encode(state.df_clean)

    # ML-ready numeric matrix
    state.df_ml = state.df_clean[ML_FEATURES + [TARGET]].copy()

    logger.info(
        f"Dataset ready — {len(state.df_clean):,} clean records | "
        f"default rate: {state.df_clean[TARGET].mean()*100:.2f}%"
    )
    return state
