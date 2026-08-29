from __future__ import annotations

import re
from dataclasses import asdict

from rank_bm25 import BM25Okapi

from .ingest import KBChunk


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Retriever:
    def __init__(self, chunks: list[KBChunk]):
        if not chunks:
            raise ValueError("KB index cannot be empty")
        self.chunks = chunks
        self._index = BM25Okapi([tokenize(chunk.text) for chunk in chunks])

    def search(self, query: str, limit: int = 3) -> list[dict]:
        scores = self._index.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda item: (-float(item[1]), item[0]))[:limit]
        return [{**asdict(self.chunks[index]), "score": round(float(score), 4)} for index, score in ranked if score > 0]
