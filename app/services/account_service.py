from __future__ import annotations

from datetime import datetime

from app.models.schemas import AccountBrief, Evidence, RiskFlag
from app.prompts.account_brief import EXTRACT_SYSTEM, WRITE_SYSTEM

from .data_loader import Dataset
from .llm_service import LLMService


CHURN_TERMS = ("cancel", "churn", "competitor", "alternative", "frustrated", "escalat", "unacceptable", "switch")


class AccountBriefService:
    def __init__(self, dataset: Dataset, llm: LLMService | None = None):
        self.dataset = dataset
        self.llm = llm or LLMService()

    def build_brief(self, account_id: str, *, as_of: datetime | None = None) -> AccountBrief:
        account = self.dataset.account(account_id)
        if not account:
            return AccountBrief(account_id=account_id, company=None, executive_summary="Account was not found in the supplied account dataset.", open_risks_and_flagged_issues=[], recommended_talking_points=["Confirm the account identifier and repair the account-to-ticket mapping."], tickets_considered=0, data_gaps=["Account record is missing."])

        tickets = self.dataset.recent_tickets(account_id, as_of=as_of)
        risks = self._deterministic_risks(account, tickets)
        active_ratio = account["seats_active"] / max(account["seats_licensed"], 1)
        summary = f"{account['company']} is {account['health_status'].lower()} on the {account['plan_tier']} plan with {active_ratio:.0%} active-seat utilisation and a {account['usage_trend'].lower()} usage trend. {len(tickets)} linked tickets were found in the dataset-relative 90-day window."
        gaps = []
        if not tickets:
            gaps.append("No recent tickets link to this account ID; ticket-history conclusions are limited.")
        points = self._talking_points(account, risks, tickets)
        fallback = AccountBrief(account_id=account_id, company=account["company"], executive_summary=summary, open_risks_and_flagged_issues=risks, recommended_talking_points=points, tickets_considered=len(tickets), data_gaps=gaps)
        return self._llm_chain(account, tickets, fallback)

    def _llm_chain(self, account: dict, tickets: list[dict], fallback: AccountBrief) -> AccountBrief:
        """Two-call chain: extract evidence first, then format a concise account brief."""
        if not self.llm.enabled:
            return fallback
        facts = self.llm.json_completion(system=EXTRACT_SYSTEM, user=f"Account: {account}\nTickets: {tickets}\nReturn a JSON object with only grounded facts and ticket quotes.")
        if not facts:
            return fallback
        final = self.llm.json_completion(system=WRITE_SYSTEM, user=f"Deterministic baseline: {fallback.model_dump()}\nExtracted facts: {facts}", schema=AccountBrief.model_json_schema())
        try:
            candidate = AccountBrief.model_validate(final)
            # Guard against cross-account or structurally incomplete model output.
            if candidate.account_id != fallback.account_id or candidate.company != fallback.company:
                return fallback
            return candidate
        except Exception:
            return fallback

    def _deterministic_risks(self, account: dict, tickets: list[dict]) -> list[RiskFlag]:
        risks: list[RiskFlag] = []
        if account["health_status"] in {"At Risk", "Churning"} or account["usage_trend"] in {"Declining", "Inactive"}:
            evidence = [Evidence(source="account", source_id=account["account_id"], quote=note, reason="Account escalation note") for note in account.get("escalation_notes", [])]
            risks.append(RiskFlag(severity="high" if account["health_status"] == "Churning" else "medium", title="Account-health decline", rationale=f"Health is {account['health_status']} and usage is {account['usage_trend']}.", evidence=evidence))
        if account["p1_tickets_last_30d"] > 0:
            risks.append(RiskFlag(severity="high", title="Recent critical support history", rationale=f"Account reports {account['p1_tickets_last_30d']} P1 tickets in the last 30 days."))
        for ticket in tickets:
            text = f"{ticket['subject']} {ticket['body']}"
            if any(term in text.lower() for term in CHURN_TERMS):
                quote = next((line.strip() for line in ticket["body"].splitlines() if any(term in line.lower() for term in CHURN_TERMS)), ticket["subject"])
                risks.append(RiskFlag(severity="high", title="Ticket escalation or churn signal", rationale="A recent ticket includes escalation or churn language.", evidence=[Evidence(source="ticket", source_id=ticket["ticket_id"], quote=quote[:500], reason="Direct customer language")]))
        return risks

    @staticmethod
    def _talking_points(account: dict, risks: list[RiskFlag], tickets: list[dict]) -> list[str]:
        points = [f"Review {account['usage_trend'].lower()} usage and the active-seat adoption plan."]
        if risks:
            points.append("Acknowledge the identified risks and agree on owners and dates for mitigation.")
        if not tickets:
            points.append("Confirm support-history data is complete because no tickets currently join to this account.")
        return points
