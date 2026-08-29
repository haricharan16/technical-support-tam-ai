from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Priority(str, Enum):
    P1 = "P1"  # Critical: outage, security incident, data loss, broad production impact.
    P2 = "P2"  # High: major workflow blocked, limited workaround.
    P3 = "P3"  # Medium: partial impact, practical workaround.
    P4 = "P4"  # Low: how-to, cosmetic issue, informational request, feature request.


class TicketInput(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=12_000)


class KnowledgeBaseMatch(BaseModel):
    matched: bool
    source_file: str | None = None
    heading: str | None = None
    excerpt: str | None = None
    score: float = 0.0


class TriageResult(BaseModel):
    product_area: str
    issue_category: str
    urgency: Priority
    reasoning: str
    known_issue: KnowledgeBaseMatch
    recommended_team: str
    draft_first_response: str


class Evidence(BaseModel):
    source: Literal["ticket", "account"]
    source_id: str
    quote: str
    reason: str


class RiskFlag(BaseModel):
    severity: Literal["high", "medium", "low"]
    title: str
    rationale: str
    evidence: list[Evidence] = Field(default_factory=list)


class AccountBrief(BaseModel):
    account_id: str
    company: str | None
    executive_summary: str
    open_risks_and_flagged_issues: list[RiskFlag]
    recommended_talking_points: list[str]
    tickets_considered: int
    data_gaps: list[str] = Field(default_factory=list)
