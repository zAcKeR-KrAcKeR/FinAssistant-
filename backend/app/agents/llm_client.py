"""
LLM Client — Mistral (primary) / OpenAI / Template fallback
============================================================
mistralai 2.x changed its package structure:
  from mistralai.client import Mistral   (not from mistralai import Mistral)

As a belt-and-suspenders approach we also support calling the Mistral REST
API directly via httpx if the SDK import fails.

Priority:
  1. MISTRAL_API_KEY  → Mistral AI (mistral-large-latest)
  2. OPENAI_API_KEY   → OpenAI GPT-4o-mini
  3. Neither          → Template-based fallback (always works)
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


class LLMClient:
    def __init__(self):
        self.provider = "template"
        self._mistral_sdk = None
        self._mistral_model = "mistral-large-latest"
        self._mistral_key = os.getenv("MISTRAL_API_KEY", "")
        self._openai_client = None

        # ── Mistral via REST (always available if key present) ──
        if self._mistral_key:
            self.provider = "mistral"
            logger.info("LLM: Mistral AI (mistral-large-latest) via REST API ✓")

            # Also try the SDK for richer error handling
            try:
                from mistralai.client import Mistral
                self._mistral_sdk = Mistral(api_key=self._mistral_key)
                logger.info("LLM: Mistral SDK loaded ✓")
            except Exception as e:
                logger.info(f"Mistral SDK unavailable (will use REST): {e}")

        # ── OpenAI (fallback) ──────────────────────────────────
        elif os.getenv("OPENAI_API_KEY"):
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                self.provider = "openai"
                logger.info("LLM: OpenAI GPT-4o-mini initialised ✓")
            except Exception as e:
                logger.warning(f"OpenAI init failed: {e}")

        if self.provider == "template":
            logger.warning(
                "No LLM API key found → template mode. "
                "Set MISTRAL_API_KEY in backend/.env for AI responses."
            )

    # ──────────────────────────────────────────────────────────
    # Core completion — tries SDK first, then REST, then None
    # ──────────────────────────────────────────────────────────
    async def complete(self, system: str, user: str) -> str | None:
        if self.provider == "mistral":
            # Try SDK
            if self._mistral_sdk:
                try:
                    resp = await asyncio.to_thread(
                        self._mistral_sdk.chat.complete,
                        model=self._mistral_model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user",   "content": user},
                        ],
                        temperature=0.3,
                        max_tokens=1024,
                    )
                    return resp.choices[0].message.content.strip()
                except Exception as e:
                    logger.warning(f"Mistral SDK call failed, trying REST: {e}")

            # Fallback: direct httpx REST call
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(
                        MISTRAL_API_URL,
                        headers={
                            "Authorization": f"Bearer {self._mistral_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self._mistral_model,
                            "messages": [
                                {"role": "system", "content": system},
                                {"role": "user",   "content": user},
                            ],
                            "temperature": 0.3,
                            "max_tokens": 1024,
                        },
                    )
                    r.raise_for_status()
                    data = r.json()
                    return data["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"Mistral REST call failed: {e}")
                return None

        elif self.provider == "openai" and self._openai_client:
            try:
                resp = await self._openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    temperature=0.3,
                    max_tokens=1024,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI call failed: {e}")

        return None   # → template fallback in agents

    @property
    def is_available(self) -> bool:
        return self.provider != "template"

    @property
    def provider_label(self) -> str:
        labels = {
            "mistral":  "Mistral AI (mistral-large-latest)",
            "openai":   "OpenAI GPT-4o-mini",
            "template": "Template Mode (no LLM key)",
        }
        return labels.get(self.provider, self.provider)
