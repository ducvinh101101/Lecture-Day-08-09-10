"""Domain retrieval agent backed by the cleaned Day 10 Chroma collection."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
        if len(token) > 1
    }


def _lexical_score(question: str, text: str) -> float:
    query_tokens = _tokens(question)
    if not query_tokens:
        return 0.0
    overlap = query_tokens & _tokens(text)
    return len(overlap) / len(query_tokens)


@lru_cache(maxsize=1)
def _collection():
    import chromadb
    from chromadb.utils import embedding_functions

    db_path = os.environ.get("CHROMA_DB_PATH", str(ROOT / "chroma_db"))
    name = os.environ.get("CHROMA_COLLECTION", "day10_kb")
    model = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=db_path)
    emb = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model)
    return client.get_collection(name=name, embedding_function=emb)


def _query_for_sources(col, question: str, sources: Iterable[str], candidate_k: int) -> list[dict]:
    chunks: list[dict] = []
    source_list = list(sources)
    if not source_list:
        result = col.query(query_texts=[question], n_results=candidate_k)
        source_results = [result]
    else:
        source_results = [
            col.query(
                query_texts=[question],
                n_results=candidate_k,
                where={"doc_id": source},
            )
            for source in source_list
        ]

    for result in source_results:
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]
        for chunk_id, text, meta, distance in zip(ids, docs, metas, distances):
            dense_score = max(0.0, 1.0 - float(distance))
            lexical_score = _lexical_score(question, text)
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": text,
                    "doc_id": (meta or {}).get("doc_id", ""),
                    "effective_date": (meta or {}).get("effective_date", ""),
                    "dense_score": round(dense_score, 4),
                    "lexical_score": round(lexical_score, 4),
                    "score": round((dense_score * 0.7) + (lexical_score * 0.3), 4),
                }
            )
    return chunks


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("intent") == "capabilities":
        state["evidence"] = []
        state["workers_called"].append("retrieval_agent")
        state["events"].append(
            {
                "agent": "retrieval_agent",
                "retrieved": 0,
                "sources": [],
                "skipped": "capabilities intent does not require document retrieval",
            }
        )
        return state

    top_k = int(state.get("top_k", 5))
    candidate_k = max(top_k * 2, 8)
    try:
        chunks = _query_for_sources(
            _collection(),
            state["question"],
            state.get("domain_filters", []),
            candidate_k,
        )
        unique = {chunk["chunk_id"]: chunk for chunk in chunks}
        ranked = sorted(unique.values(), key=lambda item: item["score"], reverse=True)[:top_k]
        state["evidence"] = ranked
        state["workers_called"].append("retrieval_agent")
        state["events"].append(
            {
                "agent": "retrieval_agent",
                "retrieved": len(ranked),
                "sources": sorted({item["doc_id"] for item in ranked}),
            }
        )
    except Exception as exc:
        state["errors"].append(f"retrieval_agent: {type(exc).__name__}: {exc}")
        state["evidence"] = []
    return state
