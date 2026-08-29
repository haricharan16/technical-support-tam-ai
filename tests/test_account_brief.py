from pathlib import Path

from app.services.account_service import AccountBriefService
from app.services.data_loader import Dataset


ROOT = Path(__file__).resolve().parents[1]


def test_missing_account_is_graceful():
    result = AccountBriefService(Dataset(ROOT / "data")).build_brief("ACC-MISSING")
    assert result.company is None
    assert result.data_gaps


def test_at_risk_account_has_risk():
    dataset = Dataset(ROOT / "data")
    account = next(account for account in dataset.accounts if account["health_status"] == "At Risk")
    result = AccountBriefService(dataset).build_brief(account["account_id"])
    assert result.open_risks_and_flagged_issues
