"""
RAG Document Store — TF-IDF based retrieval over enterprise policy documents.
Lightweight, no external vector DB required.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

POLICY_DIR = Path(__file__).parent / "policy_docs"


class DocumentStore:
    def __init__(self):
        self.documents: list[dict] = []
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self._matrix = None

    def load_all_docs(self):
        if not POLICY_DIR.exists():
            logger.warning(f"Policy docs directory not found: {POLICY_DIR}")
            return
        for filepath in sorted(POLICY_DIR.glob("*.txt")):
            text = filepath.read_text(encoding="utf-8")
            self._add_document(
                title=filepath.stem.replace("_", " ").title(),
                content=text,
                source=filepath.name,
            )
        self._build_index()
        logger.info(f"RAG: indexed {len(self.documents)} chunks from {len(list(POLICY_DIR.glob('*.txt')))} policy documents")

    def _add_document(self, title: str, content: str, source: str):
        for chunk in self._chunk(content):
            self.documents.append({"title": title, "content": chunk, "source": source})

    def _chunk(self, text: str, size: int = 250, overlap: int = 40) -> list[str]:
        words = text.split()
        chunks, i = [], 0
        while i < len(words):
            chunk = " ".join(words[i : i + size])
            if chunk:
                chunks.append(chunk)
            i += size - overlap
        return chunks

    def _build_index(self):
        if not self.documents:
            return
        texts = [d["content"] for d in self.documents]
        self._matrix = self.vectorizer.fit_transform(texts)

    def search(self, query: str, top_k: int = 3, threshold: float = 0.05) -> list[dict]:
        if self._matrix is None or not self.documents:
            return []
        qv   = self.vectorizer.transform([query])
        sims = cosine_similarity(qv, self._matrix).flatten()
        idxs = np.argsort(sims)[::-1][:top_k]
        return [
            {**self.documents[i], "score": round(float(sims[i]), 3)}
            for i in idxs
            if sims[i] >= threshold
        ]
