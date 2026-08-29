from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Dataset:
    def __init__(self, data_dir: Path):
        self.accounts = json.loads((data_dir / "accounts.json").read_text(encoding="utf-8"))
        self.tickets = json.loads((data_dir / "tickets.json").read_text(encoding="utf-8"))
        self.accounts_by_id = {account["account_id"]: account for account in self.accounts}
        self.latest_ticket_at = max(self.parse_time(ticket["created_at"]) for ticket in self.tickets)

    @staticmethod
    def parse_time(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def account(self, account_id: str) -> dict | None:
        return self.accounts_by_id.get(account_id)

    def recent_tickets(self, account_id: str, *, as_of: datetime | None = None, days: int = 90) -> list[dict]:
        # Dataset-relative default keeps demos reproducible after the synthetic dates pass.
        reference = as_of or self.latest_ticket_at
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        cutoff = reference - timedelta(days=days)
        return sorted(
            (ticket for ticket in self.tickets if ticket["account_id"] == account_id and self.parse_time(ticket["created_at"]) >= cutoff),
            key=lambda ticket: ticket["created_at"],
            reverse=True,
        )
