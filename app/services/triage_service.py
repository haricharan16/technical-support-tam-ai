from __future__ import annotations

import re

from app.models.schemas import KnowledgeBaseMatch, Priority, TicketInput, TriageResult
from app.prompts.triage import SYSTEM as TRIAGE_SYSTEM
from app.rag.retriever import BM25Retriever

from .llm_service import LLMService


P1_TERMS = ("production down", "service down", "outage", "data breach", "security incident", "data loss", "all users", "cannot access")
P2_TERMS = ("critical", "urgent", "blocked", "failing", "failure", "timeout", "unable to", "not working")
P4_TERMS = ("how do i", "how to", "feature request", "would like", "question", "documentation", "typo", "cosmetic")


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def infer_priority(text: str) -> Priority:
    normalized = text.lower()
    if any(term in normalized for term in P1_TERMS):
        return Priority.P1
    if any(term in normalized for term in P4_TERMS):
        return Priority.P4
    if any(term in normalized for term in P2_TERMS):
        return Priority.P2
    return Priority.P3


def infer_category(text: str) -> str:
    lowered = text.lower()
    rules = {
        "Data Loss": ("data loss", "missing data", "deleted", "corrupted"),
        "Billing": ("invoice", "payment", "billing", "charge", "plan"),
        "Onboarding": ("onboarding", "setup", "new user", "provision"),
        "Integration": ("integration", "connector", "salesforce", "slack", "snowflake"),
        "Performance": ("slow", "latency", "timeout", "performance"),
        "Feature Request": ("feature request", "would like", "bulk", "enhancement"),
        "How-To": ("how do i", "how to", "where can i"),
    }
    return next((category for category, terms in rules.items() if any(term in lowered for term in terms)), "Bug")


def infer_product_area(text: str) -> str:
    lowered = text.lower()
    areas = ("Authentication", "SSO", "Connectors", "Data Ingestion", "Pipeline Monitoring", "Billing", "Onboarding", "Performance")
    return next((area for area in areas if area.lower() in lowered), "General")


def route_team(category: str, area: str) -> str:
    if category == "Billing":
        return "Billing Operations"
    if category == "Onboarding":
        return "Customer Enablement"
    if area.lower() in {"authentication", "sso"}:
        return "Identity and Access Support"
    if category in {"Data Loss", "Performance", "Integration"}:
        return "Technical Support Tier 2"
    return "Technical Support Tier 1"


class TriageService:
    def __init__(self, retriever: BM25Retriever, llm: LLMService | None = None):
        self.retriever = retriever
        self.llm = llm or LLMService()

    def triage(self, ticket: TicketInput) -> TriageResult:
        raw_text = clean_text(f"{ticket.subject}\n{ticket.body}")
        matches = self.retriever.search(raw_text, limit=1)
        category = infer_category(raw_text)
        area = infer_product_area(raw_text)
        priority = infer_priority(raw_text)
        if matches:
            top = matches[0]
            known_issue = KnowledgeBaseMatch(matched=True, source_file=top["source_file"], heading=top["section"], excerpt=top["text"][:300], score=top["score"])
        else:
            known_issue = KnowledgeBaseMatch(matched=False)
        reasoning = f"Classified as {priority.value} because {self._priority_reason(priority)}. Category signals indicate {category}."
        response = self._draft_response(priority, known_issue)
        fallback = TriageResult(product_area=area, issue_category=category, urgency=priority, reasoning=reasoning, known_issue=known_issue, recommended_team=route_team(category, area), draft_first_response=response)
        return self._llm_enrichment(ticket, matches, fallback)

    def _llm_enrichment(self, ticket: TicketInput, matches: list[dict], fallback: TriageResult) -> TriageResult:
        """LLM enrichment is optional; deterministic policy remains the safety baseline."""
        if not self.llm.enabled:
            return fallback
        context = {"ticket": ticket.model_dump(), "retrieved_kb": matches, "required_schema": TriageResult.model_json_schema(), "policy_priority": fallback.urgency.value}
        data = self.llm.json_completion(system=TRIAGE_SYSTEM, user=f"Use this JSON context and retain the policy priority unless its evidence is clearly wrong:\n{context}", schema=TriageResult.model_json_schema())
        try:
            candidate = TriageResult.model_validate(data)
            # Never permit a configured model to downgrade deterministic P1 critical incidents.
            return fallback if fallback.urgency is Priority.P1 and candidate.urgency is not Priority.P1 else candidate
        except Exception:
            return fallback

    @staticmethod
    def _priority_reason(priority: Priority) -> str:
        return {
            Priority.P1: "the ticket contains critical outage, security, data-loss, or broad-impact language",
            Priority.P2: "the ticket signals a major blocked workflow or high impact",
            Priority.P3: "the ticket describes a moderate issue without critical-impact indicators",
            Priority.P4: "the ticket is an informational, cosmetic, or feature-request style issue",
        }[priority]

    @staticmethod
    def _draft_response(priority: Priority, match: KnowledgeBaseMatch) -> str:
        escalation = "We are treating this as critical and have escalated it for immediate investigation." if priority is Priority.P1 else "We are reviewing the issue and will share the next update shortly."
        kb = f" The relevant guide is {match.source_file} ({match.heading})." if match.matched else ""
        return f"Thanks for reporting this. {escalation}{kb}"
