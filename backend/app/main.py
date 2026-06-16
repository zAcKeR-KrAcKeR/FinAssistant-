"""
FinSight AI — FastAPI Application Entry Point
============================================
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Shared singletons (set during lifespan) ────────────────
llm_client = None
rag        = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client, rag
    logger.info("=" * 60)
    logger.info("FinSight AI — Starting up …")
    logger.info("=" * 60)

    # 1. Dataset
    logger.info("Step 1/5 — Loading and preparing dataset …")
    from app.analytics.data_loader import load_and_prepare, state
    load_and_prepare(n_records=30_000, seed=42)

    # 2. ML model + SHAP
    logger.info("Step 2/5 — Training ML model and computing SHAP …")
    from app.analytics.ml_model import train_model, build_shap_explainer
    model, metrics = train_model(state.df_ml)
    state.model         = model
    state.model_metrics = metrics
    explainer, shap_vals, feat_imp = build_shap_explainer(model, state.df_ml)
    state.shap_explainer     = explainer
    state.shap_values_sample = shap_vals
    state.feature_importance = feat_imp

    # 3. Anomaly detection
    logger.info("Step 3/5 — Running anomaly detection …")
    from app.analytics.anomaly_detection import run_anomaly_detection
    anomaly_result       = run_anomaly_detection(state.df_clean)
    state.anomaly_scores = anomaly_result["anomaly_scores"]
    state.anomaly_flags  = anomaly_result["anomaly_flags"]

    # 4. RAG
    logger.info("Step 4/5 — Indexing policy documents …")
    from app.rag.document_store import DocumentStore
    rag = DocumentStore()
    rag.load_all_docs()

    # 5. LLM
    logger.info("Step 5/5 — Initialising LLM client …")
    from app.agents.llm_client import LLMClient
    llm_client = LLMClient()

    state.ready = True
    logger.info(
        f"✅ FinSight AI ready — {len(state.df_clean):,} records | "
        f"LLM: {llm_client.provider} | RAG: {len(rag.documents)} chunks"
    )
    logger.info("=" * 60)

    yield

    logger.info("FinSight AI — Shutting down.")


# ── App ────────────────────────────────────────────────────
app = FastAPI(
    title="FinSight AI",
    description="Enterprise AI-powered Financial Intelligence Copilot",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for local dev and Render previews
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health & root (defined BEFORE routers) ─────────────────
@app.get("/health", tags=["system"])
def health():
    from app.analytics.data_loader import state
    return {
        "status":       "ready" if state.ready else "initialising",
        "records":      len(state.df_clean) if state.df_clean is not None else 0,
        "llm_provider": llm_client.provider_label if llm_client else "not initialised",
        "rag_chunks":   len(rag.documents) if rag else 0,
        "model_auc":    state.model_metrics.get("auc_roc") if (hasattr(state, "model_metrics") and state.model_metrics) else None,
    }


@app.get("/", tags=["system"])
def root():
    return {"name": "FinSight AI API", "version": "1.0.0", "docs": "/docs", "health": "/health"}


# ── Routers (imported & registered here, no circular deps) ─
from app.api.dashboard import router as dashboard_router  # noqa: E402
from app.api.whatif    import router as whatif_router     # noqa: E402
from app.api.chat      import router as chat_router       # noqa: E402

app.include_router(dashboard_router)
app.include_router(whatif_router)
app.include_router(chat_router)
