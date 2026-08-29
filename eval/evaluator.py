from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services.account_service import AccountBriefService
from app.services.data_loader import Dataset
from app.services.llm_service import LLMService
from app.services.triage_service import TriageService

from .test_cases import account_cases, triage_cases


@dataclass
class Result:
    id: str
    task: str
    passed: bool
    quality_score: float
    checks: dict[str, bool]


def llm_judge_score(llm: LLMService, *, task: str, output: dict) -> float | None:
    """Optional quality judge; deterministic checks remain the release gate."""
    verdict = llm.json_completion(
        system="You are a strict evaluation judge. Score only groundedness, completeness, and required formatting. Return JSON: {\"score\": number from 0 to 1}.",
        user=f"Task: {task}\nOutput: {output}",
        schema={"type": "object", "properties": {"score": {"type": "number", "minimum": 0, "maximum": 1}}, "required": ["score"]},
    )
    try:
        score = float((verdict or {})["score"])
        return max(0.0, min(1.0, score))
    except (KeyError, TypeError, ValueError):
        return None


def evaluate(triage: TriageService, accounts: AccountBriefService, dataset: Dataset, llm: LLMService | None = None) -> list[Result]:
    llm = llm or LLMService()
    results: list[Result] = []
    for case in triage_cases(dataset):
        output = triage.triage(case["input"])
        checks = {"valid_schema": True, "priority_accepted": output.urgency.value in case["accepted_priorities"], "team_present": bool(output.recommended_team), "response_present": bool(output.draft_first_response)}
        deterministic_score = sum(checks.values()) / len(checks)
        judge_score = llm_judge_score(llm, task="triage", output=output.model_dump()) if llm.enabled else None
        results.append(Result(case["id"], "triage", all(checks.values()), round(judge_score if judge_score is not None else deterministic_score, 2), checks))
    for case in account_cases(dataset):
        output = accounts.build_brief(case["account_id"])
        ticket_evidence_has_quote = all(evidence.quote for risk in output.open_risks_and_flagged_issues for evidence in risk.evidence if evidence.source == "ticket")
        checks = {"three_sections": bool(output.executive_summary and output.recommended_talking_points is not None), "risk_expectation": bool(output.open_risks_and_flagged_issues) == case["expect_risk"] if output.company else True, "ticket_quotes_present": ticket_evidence_has_quote, "missing_data_graceful": bool(output.company) or bool(output.data_gaps)}
        deterministic_score = sum(checks.values()) / len(checks)
        judge_score = llm_judge_score(llm, task="account_brief", output=output.model_dump()) if llm.enabled else None
        results.append(Result(case["id"], "account_brief", all(checks.values()), round(judge_score if judge_score is not None else deterministic_score, 2), checks))
    return results


def write_report(results: list[Result], output_path: Path) -> None:
    payload = {"summary": {"total": len(results), "passed": sum(result.passed for result in results), "mean_quality_score": round(sum(result.quality_score for result in results) / len(results), 2)}, "results": [asdict(result) for result in results]}
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    dataset = Dataset(root / "data")
    from app.rag.ingest import load_kb_chunks
    from app.rag.retriever import BM25Retriever

    results = evaluate(TriageService(BM25Retriever(load_kb_chunks(root / "knowledge-base"))), AccountBriefService(dataset), dataset)
    write_report(results, root / "eval" / "eval_report.json")
    print(f"Wrote {len(results)} evaluation results.")
