"""
RAG retrieval layer for the investigation pipeline — Phase 3, Step 8.

Uses TF-IDF + cosine similarity (sklearn) to retrieve relevant fraud
playbook / SOP documents given a query string derived from the case.
No external API, no LLM, no new dependencies — sklearn is already installed.

Knowledge base: plain-text files in data/knowledge/ relative to the project root.
The vector store is built lazily on first call and cached for the process lifetime.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger("investigation-retriever")

# ---------------------------------------------------------------------------
# Knowledge base location
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", str(_REPO_ROOT / "data" / "knowledge")))


# ---------------------------------------------------------------------------
# Internal types
# ---------------------------------------------------------------------------

class _VectorStore(NamedTuple):
    vectorizer: TfidfVectorizer
    matrix: Any             # scipy sparse matrix, shape (n_docs, n_features)
    documents: list[str]    # raw text, aligned with matrix rows
    sources: list[str]      # file stem names, aligned with matrix rows


# Module-level cache — built once per process on first retrieve_knowledge() call.
_store: _VectorStore | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_documents(knowledge_dir: Path = KNOWLEDGE_DIR) -> tuple[list[str], list[str]]:
    """
    Load all .txt files from knowledge_dir.

    Returns:
        (documents, sources) — parallel lists of raw text and file stem names.

    Raises:
        FileNotFoundError: if knowledge_dir does not exist or contains no .txt files.
    """
    if not knowledge_dir.exists():
        raise FileNotFoundError(
            f"Knowledge base directory not found: {knowledge_dir}. "
            "Create data/knowledge/ and populate it with .txt playbook files."
        )

    txt_files = sorted(knowledge_dir.glob("*.txt"))

    if not txt_files:
        raise FileNotFoundError(
            f"No .txt files found in knowledge base directory: {knowledge_dir}"
        )

    documents: list[str] = []
    sources: list[str] = []

    for path in txt_files:
        try:
            text = path.read_text(encoding="utf-8").strip()
            if text:
                documents.append(text)
                sources.append(path.stem)
                logger.debug("Loaded knowledge document: %s (%d chars)", path.stem, len(text))
        except OSError as exc:
            logger.warning("Skipping %s — could not read file: %s", path, exc)

    logger.info(
        "load_documents: loaded %d documents from %s",
        len(documents),
        knowledge_dir,
    )
    return documents, sources


def create_vector_store(
    documents: list[str],
    sources: list[str],
) -> _VectorStore:
    """
    Fit a TF-IDF vectorizer on documents and return a _VectorStore.

    Args:
        documents: List of raw document text strings.
        sources:   Parallel list of source identifiers (file stems).

    Returns:
        _VectorStore with vectorizer, TF-IDF matrix, documents, and sources.
    """
    vectorizer = TfidfVectorizer(
        strip_accents="unicode",
        lowercase=True,
        ngram_range=(1, 2),     # unigrams + bigrams for better phrase matching
        min_df=1,
        sublinear_tf=True,      # log-normalise term frequencies
    )

    matrix = vectorizer.fit_transform(documents)

    logger.info(
        "create_vector_store: fitted TF-IDF on %d documents, vocab_size=%d",
        len(documents),
        len(vectorizer.vocabulary_),
    )

    return _VectorStore(
        vectorizer=vectorizer,
        matrix=matrix,
        documents=documents,
        sources=sources,
    )


def retrieve_knowledge(query: str, top_k: int = 3) -> list[dict]:
    """
    Return the top_k most relevant documents for the given query.

    Builds and caches the vector store on first call. Subsequent calls reuse
    the cached store — no re-fitting on every investigation.

    Args:
        query:  Free-text search string derived from the case context.
        top_k:  Maximum number of documents to return (default 3).

    Returns:
        List of dicts ranked by cosine similarity (highest first), each with:
          source  — file stem of the matched playbook document
          content — full raw text of the document
          score   — cosine similarity score (float, 0.0–1.0)
        Returns an empty list if the knowledge base cannot be loaded or if
        no document has non-zero overlap with the query.
    """
    global _store

    if not query or not query.strip():
        logger.warning("retrieve_knowledge: empty query — returning no documents")
        return []

    if _store is None:
        try:
            documents, sources = load_documents()
            _store = create_vector_store(documents, sources)
        except FileNotFoundError as exc:
            logger.error("retrieve_knowledge: knowledge base unavailable — %s", exc)
            return []

    query_vec = _store.vectorizer.transform([query])
    similarities = cosine_similarity(query_vec, _store.matrix)[0]

    # Sort descending by similarity; take at most top_k
    ranked_indices = np.argsort(similarities)[::-1][:top_k]

    results: list[dict] = []
    for idx in ranked_indices:
        score = float(similarities[idx])
        if score <= 0.0:
            break   # remaining documents have zero overlap with query
        results.append({
            "source": _store.sources[idx],
            "content": _store.documents[idx],
            "score": score,
        })
        logger.debug(
            "retrieve_knowledge: rank=%d source=%s score=%.4f",
            len(results),
            _store.sources[idx],
            score,
        )

    logger.info(
        "retrieve_knowledge: query=%r top_k=%d retrieved=%d",
        query[:120],
        top_k,
        len(results),
    )

    return results


def build_query(
    case: dict,
    rules_triggered: list[str],
    feature_breakdown: dict,
) -> str:
    """
    Construct a free-text search query from case signals for knowledge retrieval.

    Assembles human-readable signal terms so the TF-IDF retriever can match
    them against playbook vocabulary without requiring exact keyword overlap.

    Args:
        case:              Predictions row dict from Postgres.
        rules_triggered:   List of rule explanation strings from get_rule_explanations.
        feature_breakdown: Feature dict from get_feature_breakdown.

    Returns:
        A single query string, e.g.
        "high amount fraud night transaction unusual behaviour risk score 0.85"
    """
    terms: list[str] = []

    # Decision signal
    decision = (case.get("decision") or "").strip().upper()
    if decision in ("REVIEW", "BLOCK"):
        terms.append("fraud suspicious transaction")

    # Amount signal
    amount_vs_threshold = feature_breakdown.get("amount_vs_threshold")
    if amount_vs_threshold is not None and amount_vs_threshold >= 1.0:
        terms.append("high amount large transaction")

    # Night signal
    if feature_breakdown.get("is_night_transaction"):
        terms.append("night transaction out of hours")

    # Risk score signal
    risk_score = feature_breakdown.get("risk_score", 0.0)
    if isinstance(risk_score, (int, float)):
        if risk_score >= 0.7:
            terms.append("high risk score model flagged")
        elif risk_score >= 0.3:
            terms.append("moderate risk score review")

    # Rule signals — extract key phrases from explanation strings
    for explanation in rules_triggered:
        explanation_lower = explanation.lower()
        if "velocity" in explanation_lower:
            terms.append("velocity spike card testing account takeover")
        if "night" in explanation_lower:
            terms.append("night transaction out of hours fraud")
        if "amount" in explanation_lower or "threshold" in explanation_lower:
            terms.append("high amount large purchase fraud")
        if "merchant" in explanation_lower:
            terms.append("new merchant unknown merchant fraud")
        if "cross-border" in explanation_lower or "country" in explanation_lower:
            terms.append("cross border foreign transaction fraud")
        if "ip" in explanation_lower or "subnet" in explanation_lower:
            terms.append("suspicious ip account takeover proxy")
        if "card not present" in explanation_lower:
            terms.append("card not present CNP e-commerce fraud")

    # Rule flag
    if case.get("rule_flag") == 1:
        terms.append("rule flagged deterministic signal")

    # Fallback — ensure the query is never empty
    if not terms:
        terms.append("fraud transaction review")

    query = " ".join(terms)

    logger.info("build_query: %r", query[:200])

    return query
