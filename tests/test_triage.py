from pathlib import Path

from app.models.schemas import Priority, TicketInput
from app.rag.ingest import load_kb_chunks
from app.rag.retriever import BM25Retriever
from app.services.triage_service import TriageService


ROOT = Path(__file__).resolve().parents[1]
service = TriageService(BM25Retriever(load_kb_chunks(ROOT / "knowledge-base")))


def test_p1_is_critical():
    result = service.triage(TicketInput(subject="Production outage", body="All users cannot access the production service. This is a security incident risk."))
    assert result.urgency is Priority.P1


def test_p4_how_to_is_low_priority():
    result = service.triage(TicketInput(subject="How do I configure SSO?", body="This is a documentation question."))
    assert result.urgency is Priority.P4
    assert result.known_issue.matched


def test_output_is_deterministic():
    input_ = TicketInput(subject="Slow dashboard", body="Dashboard performance timeout affects our reporting workflow.")
    assert service.triage(input_) == service.triage(input_)
