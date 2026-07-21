"""Pure-Python BM25 retrieval for the educational explainer knowledge base.

This module implements BM25 scoring without external dependencies (no chromadb,
sentence-transformers, llama-index). The interface matches the spec in
07-explainer.md so a vector backend can replace it later.

Key design choices:
- BM25 with k1=1.5, b=0.75 (standard defaults)
- Level-aware boosting: beginner prefers teaching_note, advanced prefers ecl_td
- Module-level cache for lazy KB loading
- KB built offline via build_knowledge_base(), persisted as JSON
- Falls back to teaching notes if KB not built and source dirs missing
"""

from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opm_ai.explainer.models import Citation, ExplanationLevel


# ---- BM25 Core ----

@dataclass(slots=True)
class BM25Index:
    """In-memory BM25 index."""
    chunks: list[dict[str, Any]]      # Original chunk dicts
    doc_freqs: dict[str, int]         # term -> document frequency
    doc_lengths: list[int]            # Token count per chunk
    avgdl: float                      # Average document length
    N: int                            # Total number of chunks


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, alphanumeric split."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _build_bm25_index(chunks: list[dict[str, Any]]) -> BM25Index:
    """Build BM25 index from chunk list."""
    N = len(chunks)
    doc_freqs: dict[str, int] = {}
    doc_lengths: list[int] = []

    # First pass: tokenize and count document frequencies
    tokenized_chunks: list[list[str]] = []
    for chunk in chunks:
        tokens = _tokenize(chunk["text"])
        tokenized_chunks.append(tokens)
        doc_lengths.append(len(tokens))
        # Unique terms in this document
        for term in set(tokens):
            doc_freqs[term] = doc_freqs.get(term, 0) + 1

    avgdl = sum(doc_lengths) / N if N > 0 else 0.0

    return BM25Index(
        chunks=chunks,
        doc_freqs=doc_freqs,
        doc_lengths=doc_lengths,
        avgdl=avgdl,
        N=N,
    )


def _bm25_score(query_tokens: list[str], index: BM25Index, doc_idx: int, k1: float = 1.5, b: float = 0.75) -> float:
    """Compute BM25 score for a single document."""
    score = 0.0
    doc_len = index.doc_lengths[doc_idx]
    tokens = _tokenize(index.chunks[doc_idx]["text"])  # Re-tokenize for term freq

    # Term frequency in this document
    tf: dict[str, int] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1

    for term in query_tokens:
        if term not in index.doc_freqs:
            continue
        df = index.doc_freqs[term]
        idf = math.log((index.N - df + 0.5) / (df + 0.5) + 1.0)
        term_tf = tf.get(term, 0)
        if term_tf == 0:
            continue
        numerator = term_tf * (k1 + 1)
        denominator = term_tf + k1 * (1 - b + b * doc_len / index.avgdl)
        score += idf * (numerator / denominator)

    return score


# ---- Level-aware boosting ----

SOURCE_TYPE_BOOST = {
    "beginner": {
        "teaching_note": 2.0,
        "deck_comment": 1.0,
        "ecl_rm": 0.8,
        "ecl_td": 0.5,
    },
    "intermediate": {
        "teaching_note": 1.5,
        "deck_comment": 1.2,
        "ecl_rm": 1.0,
        "ecl_td": 1.0,
    },
    "advanced": {
        "teaching_note": 0.8,
        "deck_comment": 1.0,
        "ecl_rm": 1.2,
        "ecl_td": 2.0,
    },
}


def _apply_level_boost(score: float, source_type: str, level: ExplanationLevel) -> float:
    """Apply level-aware boost based on source type."""
    boost = SOURCE_TYPE_BOOST.get(level, {}).get(source_type, 1.0)
    return score * boost


# ---- Knowledge Base Persistence ----

DEFAULT_PERSIST_DIR = Path(__file__).parent / "kb"
# Repo root is three parents up: opm_ai/explainer/retrieve.py -> repo/
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIRS = [
    _REPO_ROOT / "tests/eclipse/ecl_rm",
    _REPO_ROOT / "tests/eclipse/ecl_td",
    _REPO_ROOT / "tests/fixtures",
]
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def build_knowledge_base(
    source_dirs: list[Path],
    persist_dir: Path,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> None:
    """
    Build knowledge base from source directories and persist to JSON.

    This is run OFFLINE (at Docker build time). The embedding_model parameter
    is accepted for API compatibility with vector backends but is IGNORED
    by this BM25 implementation (we use token-based BM25, not embeddings).

    Args:
        source_dirs: List of directories to ingest (ecl_rm, ecl_td, fixtures)
        persist_dir: Output directory for kb.json
        embedding_model: Ignored (kept for interface compatibility)
    """
    # Import here to avoid circular import
    from opm_ai.explainer.ingest import read_eclipse_html, read_deck_comments, read_teaching_notes

    all_chunks: list[dict[str, Any]] = []

    for src_dir in source_dirs:
        src_dir = Path(src_dir)
        if not src_dir.exists():
            continue

        if src_dir.name == "ecl_rm":
            all_chunks.extend(read_eclipse_html(src_dir, "ecl_rm"))
        elif src_dir.name == "ecl_td":
            all_chunks.extend(read_eclipse_html(src_dir, "ecl_td"))
        elif src_dir.name == "fixtures":
            all_chunks.extend(read_deck_comments(src_dir))

    # Always add teaching notes (they ship with the package)
    all_chunks.extend(read_teaching_notes())

    # Cap ecl_rm files if too many (keep build under 60s)
    ecl_rm_chunks = [c for c in all_chunks if c["source_type"] == "ecl_rm"]
    if len(ecl_rm_chunks) > 500:
        # Keep first 500 (they're sorted by filename)
        other_chunks = [c for c in all_chunks if c["source_type"] != "ecl_rm"]
        all_chunks = other_chunks + ecl_rm_chunks[:500]

    print(f"Building KB with {len(all_chunks)} chunks...")

    # Build BM25 index
    index = _build_bm25_index(all_chunks)

    # Persist
    persist_dir.mkdir(parents=True, exist_ok=True)
    kb_data = {
        "chunks": index.chunks,
        "doc_freqs": index.doc_freqs,
        "doc_lengths": index.doc_lengths,
        "avgdl": index.avgdl,
        "N": index.N,
        "built_at": time.time(),
        "embedding_model": embedding_model,  # Stored for metadata only
    }

    kb_path = persist_dir / "kb.json"
    with kb_path.open("w", encoding="utf-8") as f:
        json.dump(kb_data, f)

    print(f"KB built and saved to {kb_path} ({len(all_chunks)} chunks)")


# ---- Module-level cache for lazy loading ----

import threading

_KB_CACHE: BM25Index | None = None
_KB_PATH: Path | None = None
_KB_LOCK = threading.Lock()


def _load_kb(persist_dir: Path = DEFAULT_PERSIST_DIR) -> BM25Index:
    """Load KB from disk (lazy, cached, thread-safe)."""
    global _KB_CACHE, _KB_PATH

    # First check without lock (fast path)
    if _KB_CACHE is not None and _KB_PATH == persist_dir:
        return _KB_CACHE

    # Slow path with lock
    with _KB_LOCK:
        # Double-check inside lock
        if _KB_CACHE is not None and _KB_PATH == persist_dir:
            return _KB_CACHE

        kb_path = persist_dir / "kb.json"
        if not kb_path.exists():
            # Try to build from default sources if they exist
            if all(d.exists() for d in DEFAULT_SOURCE_DIRS):
                print("KB not found, building from default sources...")
                build_knowledge_base(DEFAULT_SOURCE_DIRS, persist_dir)
            else:
                # Fall back to teaching notes only (always available)
                from opm_ai.explainer.ingest import read_teaching_notes
                teaching_chunks = read_teaching_notes()
                _KB_CACHE = _build_bm25_index(teaching_chunks)
                _KB_PATH = persist_dir
                return _KB_CACHE

        with kb_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        _KB_CACHE = BM25Index(
            chunks=data["chunks"],
            doc_freqs=data["doc_freqs"],
            doc_lengths=data["doc_lengths"],
            avgdl=data["avgdl"],
            N=data["N"],
        )
        _KB_PATH = persist_dir
        return _KB_CACHE


# ---- Public Retrieval API ----

def retrieve_chunks(
    query: str,
    k: int = 5,
    level: ExplanationLevel = "intermediate",
    persist_dir: Path = DEFAULT_PERSIST_DIR,
) -> list[Citation]:
    """
    Semantic search over the knowledge base using BM25.

    Args:
        query: Search query string
        k: Number of results to return
        level: Explanation level for boosting (beginner/intermediate/advanced)
        persist_dir: Directory containing kb.json

    Returns:
        List of Citation objects (top k by BM25 score with level boosting)
    """
    index = _load_kb(persist_dir)

    if index.N == 0:
        return []

    query_tokens = _tokenize(query)

    # Score all chunks
    scored: list[tuple[float, int]] = []
    for i in range(index.N):
        score = _bm25_score(query_tokens, index, i)
        # Apply level-aware boost
        source_type = index.chunks[i]["source_type"]
        score = _apply_level_boost(score, source_type, level)
        scored.append((score, i))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Build citations from top k
    citations: list[Citation] = []
    for score, idx in scored[:k]:
        chunk = index.chunks[idx]
        snippet = chunk["text"][:200] + ("..." if len(chunk["text"]) > 200 else "")
        citations.append(Citation(
            source_id=chunk["source_id"],
            title=chunk["title"],
            url_or_path=chunk["path"],
            snippet=snippet,
        ))

    return citations