from __future__ import annotations

from app.models.schemas import TicketInput
from app.services.data_loader import Dataset


def triage_cases(dataset: Dataset) -> list[dict]:
    cases = []
    for priority in ("P1", "P2", "P3", "P4"):
        ticket = next(ticket for ticket in dataset.tickets if ticket["urgency"] == priority)
        cases.append({"id": ticket["ticket_id"], "input": TicketInput(subject=ticket["subject"], body=ticket["body"]), "accepted_priorities": [priority, "P2"] if priority == "P1" else [priority]})
    cases.append({"id": "adversarial-ambiguous", "input": TicketInput(subject="Something seems odd", body="A user reports an intermittent issue but provides no product, error, impact, or reproduction steps."), "accepted_priorities": ["P3", "P4"]})
    return cases


def account_cases(dataset: Dataset) -> list[dict]:
    selected = [
        next(account for account in dataset.accounts if account["health_status"] == "Healthy"),
        next(account for account in dataset.accounts if account["health_status"] == "At Risk"),
        next(account for account in dataset.accounts if account["health_status"] == "Churning"),
        next(account for account in dataset.accounts if account["health_status"] == "New"),
    ]
    return [{"id": account["account_id"], "account_id": account["account_id"], "expect_risk": account["health_status"] in {"At Risk", "Churning"}} for account in selected] + [{"id": "adversarial-missing-account", "account_id": "ACC-DOES-NOT-EXIST", "expect_risk": False}]
