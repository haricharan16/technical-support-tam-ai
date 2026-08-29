from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.models.schemas import AccountBrief, TicketInput, TriageResult
from app.rag.ingest import load_kb_chunks
from app.rag.retriever import BM25Retriever
from app.services.account_service import AccountBriefService
from app.services.data_loader import Dataset
from app.services.llm_service import LLMService
from app.services.triage_service import TriageService

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Support and TAM AI", version="1.0.0")


@lru_cache
def dataset() -> Dataset:
    return Dataset(ROOT / "data")


@lru_cache
def triage_service() -> TriageService:
    return TriageService(BM25Retriever(load_kb_chunks(ROOT / "knowledge-base")), LLMService())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/triage", response_model=TriageResult)
def triage(ticket: TicketInput) -> TriageResult:
    return triage_service().triage(ticket)


@app.get("/accounts/{account_id}/brief", response_model=AccountBrief)
def account_brief(account_id: str) -> AccountBrief:
    result = AccountBriefService(dataset(), LLMService()).build_brief(account_id)
    if result.company is None:
        raise HTTPException(status_code=404, detail=result.executive_summary)
    return result
