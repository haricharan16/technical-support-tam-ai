from __future__ import annotations

import json
from pathlib import Path

from app.rag.ingest import load_kb_chunks, serialise_chunks


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    chunks = load_kb_chunks(root / "knowledge-base")
    output = root / "data" / "kb_chunks.json"
    output.write_text(json.dumps(serialise_chunks(chunks), indent=2), encoding="utf-8")
    print(f"Wrote {len(chunks)} chunks to {output}")
