"""
Synthetic Credit Risk Dataset Generator
======================================
Generates 30,000 realistic records modelling an Indian financial services
portfolio.  The dataset is deliberately designed to contain:
  - A compelling default narrative (Maharashtra + Young Professionals)
  - Intentional data quality issues (missing values)
  - Time-based default trend (increase 2022→2023, plateau 2024)
  - Realistic feature correlations matching real-world credit behaviour
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Domain constants
# ──────────────────────────────────────────────
STATES = [
    "Maharashtra", "Gujarat", "Karnataka", "Tamil Nadu", "Delhi",
    "Uttar Pradesh", "Rajasthan", "West Bengal", "Telangana", "Punjab",
    "Kerala", "Madhya Pradesh", "Bihar", "Haryana", "Andhra Pradesh",
]
# Rough population weights
STATE_PROBS = [0.15, 0.09, 0.08, 0.09, 0.12, 0.10, 0.07, 0.08,
               0.06, 0.04, 0.03, 0.03, 0.02, 0.02, 0.02]

EMPLOYMENT_TYPES = ["Salaried", "Self-Employed", "Business Owner",
                    "Freelancer", "Government", "Retired"]
EMPLOYMENT_PROBS = [0.45, 0.20, 0.12, 0.08, 0.10, 0.05]

LOAN_PURPOSES = ["Home Loan", "Personal Loan", "Vehicle Loan",
                 "Business Loan", "Education Loan", "Credit Card"]
LOAN_PROBS = [0.25, 0.30, 0.15, 0.12, 0.10, 0.08]

MARITAL_STATUS = ["Single", "Married", "Divorced", "Widowed"]
MARITAL_PROBS  = [0.35, 0.50, 0.10, 0.05]

EDUCATION_LEVELS = ["High School", "Diploma", "Bachelor", "Master", "PhD"]
EDUCATION_PROBS  = [0.15, 0.20, 0.40, 0.20, 0.05]

EDUCATION_INCOME_MULT = {
    "High School": 0.55,
    "Diploma": 0.75,
    "Bachelor": 1.00,
    "Master": 1.50,
    "PhD": 2.00,
}


# ──────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────
def _customer_segment(age: int) -> str:
    if age < 26:   return "Student"
    if age < 35:   return "Young Professional"
    if age < 50:   return "Mid-Career"
    if age < 60:   return "Senior"
    return "Retired"


def generate_dataset(n: int = 30_000, seed: int = 42) -> pd.DataFrame:
    """Return a fully-featured synthetic credit-risk DataFrame."""
    logger.info(f"Generating synthetic dataset with {n:,} records …")
    rng = np.random.default_rng(seed)

    # ── Demographics ──────────────────────────────────────────
    ages = rng.normal(38, 12, n).clip(21, 75).astype(int)

    edu_idx   = rng.choice(len(EDUCATION_LEVELS), n, p=EDUCATION_PROBS)
    education = np.array(EDUCATION_LEVELS)[edu_idx]

    edu_mult  = np.array([EDUCATION_INCOME_MULT[e] for e in education])
    base_inc  = 220_000 + (ages - 21) * 9_000
    income    = (base_inc * edu_mult * rng.lognormal(0, 0.45, n) / 2
                ).clip(100_000, 10_000_000).astype(int)

    marital_status   = rng.choice(MARITAL_STATUS, n, p=MARITAL_PROBS)
    employment_types = rng.choice(EMPLOYMENT_TYPES, n, p=EMPLOYMENT_PROBS)
    states           = rng.choice(STATES, n, p=STATE_PROBS)
    loan_purposes    = rng.choice(LOAN_PURPOSES, n, p=LOAN_PROBS)
    segments         = [_customer_segment(a) for a in ages]

    # ── Credit profile ────────────────────────────────────────
    credit_scores     = rng.normal(680, 78, n).clip(300, 900).astype(int)
    loan_amounts      = (income * rng.uniform(0.5, 5.0, n)
                        ).clip(50_000, 15_000_000).astype(int)
    loan_term_months  = rng.choice(
        [12, 24, 36, 48, 60, 84, 120, 180, 240, 360], n,
        p=[0.05, 0.10, 0.15, 0.12, 0.18, 0.12, 0.10, 0.08, 0.05, 0.05]
    )
    dti_ratios        = (rng.beta(2, 5, n) * 80 + 5).round(2)   # 5–85 %
    prev_defaults     = rng.choice([0, 1, 2, 3], n, p=[0.75, 0.15, 0.07, 0.03])
    credit_util       = (rng.beta(2, 4, n) * 100).round(2)
    num_accounts      = rng.poisson(3, n).clip(0, 15)
    savings_ratio     = (rng.beta(2, 5, n) * 50).round(2)

    # Interest rate tier (CIBIL-like)
    interest_rate = np.where(credit_scores >= 750, 0.08,
                    np.where(credit_scores >= 650, 0.12,
                    np.where(credit_scores >= 550, 0.16, 0.22)))

    # ── Application dates  (Jan 2022 – Dec 2024) ─────────────
    start_date = datetime(2022, 1, 1)
    total_days = (datetime(2024, 12, 31) - start_date).days
    day_offsets = rng.integers(0, total_days, n)
    app_dates   = [start_date + timedelta(days=int(d)) for d in day_offsets]

    # ── Default probability (logistic model) ─────────────────
    # Designed to yield ~12 % overall default rate with realistic drivers
    log_odds = (
        -2.90
        - 0.018 * (credit_scores - 600)
        + 0.90  * (dti_ratios > 40).astype(float)
        + 1.60  * (prev_defaults >= 1).astype(float)
        + 0.90  * (prev_defaults >= 2).astype(float)
        + 0.75  * (credit_util > 70).astype(float)
        - 0.45  * (income > 700_000).astype(float)
        + 0.65  * (ages < 26).astype(float)
        - 0.35  * (employment_types == "Government").astype(float)
        + 0.45  * (employment_types == "Freelancer").astype(float)
        + 0.35  * (np.array(states) == "Maharashtra").astype(float)
        + 0.25  * np.array([1 if d.year == 2023 else 0 for d in app_dates])
        + rng.normal(0, 0.18, n)
    )
    default_probs = 1 / (1 + np.exp(-log_odds))
    defaults = (rng.random(n) < default_probs).astype(int)

    # ── Assemble DataFrame ────────────────────────────────────
    df = pd.DataFrame({
        "customer_id":           [f"CUST{i:06d}" for i in range(1, n + 1)],
        "age":                   ages,
        "income":                income,
        "credit_score":          credit_scores,
        "loan_amount":           loan_amounts,
        "loan_term_months":      loan_term_months,
        "debt_to_income_ratio":  dti_ratios,
        "previous_defaults":     prev_defaults,
        "credit_utilization":    credit_util,
        "num_credit_accounts":   num_accounts,
        "savings_ratio":         savings_ratio,
        "interest_rate":         interest_rate.round(4),
        "employment_type":       employment_types,
        "state":                 states,
        "loan_purpose":          loan_purposes,
        "marital_status":        marital_status,
        "education":             education,
        "customer_segment":      segments,
        "income_bracket": pd.cut(
            income,
            bins=[0, 300_000, 600_000, 1_200_000, 2_500_000, float("inf")],
            labels=["<3L", "3-6L", "6-12L", "12-25L", ">25L"],
        ).astype(str),
        "application_date":    pd.to_datetime(app_dates),
        "application_month":   [d.strftime("%Y-%m") for d in app_dates],
        "application_year":    [d.year for d in app_dates],
        "application_quarter": [f"{d.year}-Q{(d.month-1)//3+1}" for d in app_dates],
        "default":             defaults,
    })

    # ── Inject realistic missing values ──────────────────────
    df.loc[rng.random(n) < 0.020, "income"]        = np.nan
    df.loc[rng.random(n) < 0.080, "savings_ratio"] = np.nan
    df.loc[rng.random(n) < 0.030, "education"]     = np.nan

    logger.info(
        f"Dataset generated — {n:,} records | "
        f"default rate: {defaults.mean()*100:.1f}% | "
        f"missing income: {df['income'].isna().sum()} rows"
    )
    return df
