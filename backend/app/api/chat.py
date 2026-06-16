"""
Chat & Voice API
=================
Primary AI assistant endpoint.
Handles both text and voice queries through the multi-agent pipeline.

POST /api/chat        — text query
POST /api/voice/query — voice query (transcription done client-side via Web Speech API;
                        this endpoint receives text and returns voice_text for TTS)
GET  /api/examples    — sample questions + failure analysis
GET  /api/executive   — trigger executive summary
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)

CONVERSATION_HISTORY: dict[str, list[dict]] = {}   # session_id → messages


# ── Request / Response models ─────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str = Field(default="default")
    mode: str = Field(default="normal", description="normal | executive | voice")
    voice_mode: bool = Field(default=False)


class VoiceQueryRequest(BaseModel):
    transcript: str = Field(..., description="Text transcribed from user voice input")
    conversation_id: str = Field(default="default")


class WhatIfRequest(BaseModel):
    message: str


# ── Helpers (lazy — avoids circular import with app.main) ─
def _get_state():
    from app.analytics.data_loader import state
    return state

def _get_llm():
    import app.main as _main
    return _main.llm_client

def _get_rag():
    import app.main as _main
    return _main.rag


def _serialize(obj):
    """Convert ChatResponse dataclass to dict for JSON serialisation."""
    from dataclasses import asdict
    return asdict(obj)


# ── Main chat endpoint ────────────────────────────────────
@router.post("/api/chat")
async def chat(req: ChatRequest):
    from app.agents.orchestrator import process_query

    app_state = _get_state()
    if not app_state.ready:
        return {"error": "System still initialising. Please wait a few seconds.", "ready": False}

    history = CONVERSATION_HISTORY.setdefault(req.conversation_id, [])

    response = await process_query(
        message=req.message,
        df=app_state.df_clean,
        llm=_get_llm(),
        mode=req.mode,
        rag=_get_rag(),
        feature_importance=app_state.feature_importance,
        model=app_state.model,
        conversation_history=history,
    )

    # Store history
    history.append({"role": "user",      "content": req.message})
    history.append({"role": "assistant", "content": response.answer})
    if len(history) > 20:
        history[:] = history[-20:]

    result = _serialize(response)

    # Add voice_text for TTS if voice_mode
    if req.voice_mode or req.mode == "voice":
        if not result.get("voice_text"):
            # Generate concise voice-friendly version
            result["voice_text"] = _to_voice_text(response.answer)

    return result


# ── Voice query endpoint ───────────────────────────────────
@router.post("/api/voice/query")
async def voice_query(req: VoiceQueryRequest):
    """Receives browser-transcribed text, processes through agents, returns voice_text."""
    from app.agents.orchestrator import process_query

    app_state = _get_state()
    if not app_state.ready:
        return {"error": "System still initialising.", "voice_text": "The system is still starting up. Please try again in a moment."}

    history = CONVERSATION_HISTORY.setdefault(req.conversation_id, [])

    response = await process_query(
        message=req.transcript,
        df=app_state.df_clean,
        llm=_get_llm(),
        mode="normal",
        rag=_get_rag(),
        feature_importance=app_state.feature_importance,
        model=app_state.model,
        conversation_history=history,
    )

    history.append({"role": "user",      "content": req.transcript})
    history.append({"role": "assistant", "content": response.answer})

    result = _serialize(response)
    # Ensure we always have voice_text
    if not result.get("voice_text"):
        result["voice_text"] = _to_voice_text(response.answer)

    return result


def _to_voice_text(markdown_answer: str) -> str:
    """Strip markdown formatting for clean TTS playback."""
    import re
    text = markdown_answer
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)       # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)             # italic
    text = re.sub(r"^#{1,3}\s+", "", text, flags=re.M)   # headers
    text = re.sub(r"•\s+", "", text)                      # bullets
    text = re.sub(r"🔴|🟡|🟢|📊|💡|✅|↳|→", "", text) # emoji
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)
    # Truncate to ~800 chars for comfortable TTS
    if len(text) > 800:
        text = text[:797] + "..."
    return text.strip()


# ── Executive summary endpoint ────────────────────────────
@router.get("/api/executive")
async def executive_summary():
    """Generates a full executive summary + voice text."""
    from app.agents.orchestrator import process_query
    app_state = _get_state()
    if not app_state.ready:
        return {"error": "System still initialising."}

    response = await process_query(
        message="Generate a complete executive summary of the portfolio",
        df=app_state.df_clean,
        llm=_get_llm(),
        mode="executive",
        rag=_get_rag(),
        feature_importance=app_state.feature_importance,
        model=app_state.model,
    )
    result = _serialize(response)
    if not result.get("voice_text"):
        result["voice_text"] = _to_voice_text(response.answer)
    return result


# ── Example questions ─────────────────────────────────────
@router.get("/api/examples")
def get_examples():
    return {
        "answers_well": [
            {
                "question": "Which customer segment has the highest default rate and what are the main drivers?",
                "why": "Requires segment aggregation, SHAP-based driver analysis, and business recommendations — all within agent capability.",
                "expected_output": "Young Professionals at ~18% default rate, driven by low income, high DTI, and limited credit history. With actionable recommendations."
            },
            {
                "question": "How has the default rate changed from 2022 to 2024, and what caused the change?",
                "why": "Time-series trend analysis with insight generation — data is structured by application_month.",
                "expected_output": "Trend chart showing 2022–2024 trajectory, peak identification, driver analysis."
            },
            {
                "question": "What would happen to our portfolio if we rejected all applications with DTI above 45%?",
                "why": "What-if simulation is directly implemented in the WhatIf agent with quantified impact.",
                "expected_output": "Approval rate change, default rate reduction, segment-by-segment impact breakdown."
            },
        ],
        "fails_gracefully": [
            {
                "question": "What will the default rate be next month?",
                "why": "Requires a time-series forecasting model (ARIMA, LSTM). The current system is retrospective, not predictive. It will acknowledge this limitation.",
                "what_it_does": "Returns current trend data with a clear note that forecasting is beyond current scope."
            },
            {
                "question": "Tell me about customer CUST000042 — is he a good borrower?",
                "why": "Individual customer PII lookup violates data privacy rules. The system is designed for portfolio-level analysis.",
                "what_it_does": "Explains the limitation and offers to analyse the risk profile for that customer's segment instead."
            },
            {
                "question": "How do we compare to HDFC Bank's default rate?",
                "why": "No external benchmarking data is available. The system only has internal portfolio data.",
                "what_it_does": "Acknowledges the gap and provides internal baseline metrics with industry context where possible."
            },
        ],
    }
