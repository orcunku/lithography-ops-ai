"""Semantic retrieval (RAG) engine using sentence-transformers + FAISS.

Free and local: a small embedding model (all-MiniLM-L6-v2, ~90 MB) turns each
maintenance document into a vector; FAISS stores the vectors and does fast
nearest-neighbour search. Given a query, we embed it the same way and retrieve
the most semantically similar documents -- matching by *meaning*, not keywords.

This upgrades the Knowledge agent from exact-word lookup to true semantic
retrieval. The index is built once and saved; retrieval then loads it.

Build:    python -m lithoops.rag.engine build
Query:    python -m lithoops.rag.engine query "focus error and rising temperature"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from lithoops.config import DATA_DIR
from lithoops.rag.knowledge_base import write_docs

EMBED_MODEL = "all-MiniLM-L6-v2"
INDEX_PATH = DATA_DIR / "rag_index.faiss"
META_PATH = DATA_DIR / "rag_meta.json"


def _load_model():
    """Imported lazily so the rest of the project runs without heavy deps."""
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL)


def build_index() -> int:
    """Embed all knowledge docs and save a FAISS index + metadata."""
    import faiss

    records = write_docs()
    texts = [f"{r['title']}. {r['content']}" for r in records]

    model = _load_model()
    emb = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    emb = emb.astype("float32")

    index = faiss.IndexFlatIP(emb.shape[1])  # inner product = cosine (normalized)
    index.add(emb)

    faiss.write_index(index, str(INDEX_PATH))
    META_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return len(records)


class Retriever:
    """Loads the saved index and answers semantic queries."""

    def __init__(self):
        import faiss
        self.index = faiss.read_index(str(INDEX_PATH))
        self.records = json.loads(META_PATH.read_text(encoding="utf-8"))
        self.model = _load_model()

    def search(self, query: str, k: int = 3) -> list[dict]:
        q = self.model.encode([query], convert_to_numpy=True,
                              normalize_embeddings=True).astype("float32")
        scores, idx = self.index.search(q, k)
        out = []
        for score, i in zip(scores[0], idx[0]):
            if i < 0:
                continue
            rec = dict(self.records[i])
            rec["score"] = round(float(score), 3)
            out.append(rec)
        return out


def index_exists() -> bool:
    return INDEX_PATH.exists() and META_PATH.exists()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        n = build_index()
        print(f"Built FAISS index over {n} documents -> {INDEX_PATH.name}")
    elif cmd == "query":
        q = " ".join(sys.argv[2:]) or "rising temperature and focus error"
        for r in Retriever().search(q, k=3):
            print(f"[{r['score']}] {r['doc_id']} ({r['subsystem']}): {r['title']}")
