from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class KBChunk:
    source_file: str
    section: str
    text: str


def chunk_markdown(path: Path, root: Path) -> list[KBChunk]:
    """Split a KB document on headings, retaining a stable source and section."""
    text = path.read_text(encoding="utf-8")
    parts = re.split(r"(?=^#{1,3}\s+)", text, flags=re.MULTILINE)
    chunks: list[KBChunk] = []
    current_heading = path.stem.replace("-", " ").title()
    for part in parts:
        if not part.strip():
            continue
        heading = re.match(r"^#{1,3}\s+(.+)$", part, re.MULTILINE)
        if heading:
            current_heading = heading.group(1).strip()
        for section in re.split(r"\n---+\n", part):
            cleaned = section.strip()
            if cleaned:
                chunks.append(KBChunk(str(path.relative_to(root)).replace("\\", "/"), current_heading, cleaned))
    return chunks


def load_kb_chunks(kb_root: Path) -> list[KBChunk]:
    return [chunk for path in sorted(kb_root.rglob("*.md")) for chunk in chunk_markdown(path, kb_root)]


def serialise_chunks(chunks: list[KBChunk]) -> list[dict[str, str]]:
    return [asdict(chunk) for chunk in chunks]
