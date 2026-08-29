# Support and TAM AI

Assignment implementation for a production-minded support-ticket triage agent and TAM account-health summariser.

## Architecture

### Task 1: Support Ticket Triage


```text
┌──────────────────────────────────────────────┐
│                 Ticket Input                 │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│          Pydantic Input Validation           │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│       BM25 Knowledge-Base Retrieval          │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│   Deterministic Priority Policy and Routing  │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│  Optional OpenAI Responses API Generation    │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│          Pydantic Output Validation          │
└──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│               FastAPI Response               │
└──────────────────────────────────────────────┘
```

## Account Health Analysis Flow

```text
┌─────────────────────────────────────────────────────────────┐
│                          Account ID                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Account Summary + Dataset-Relative 90-Day Ticket Retrieval  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│     Deterministic Account-Health and Risk Detection         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│     Evidence Extraction with Direct Ticket Quotes           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│    Optional Two-Step OpenAI Responses API Chain             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Pydantic Output Validation + Deterministic Fallback         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Response                       │
└─────────────────────────────────────────────────────────────┘
```

```
Set `LLM_PROVIDER=openai` and add `OPENAI_API_KEY` to `.env` for Responses API generation. The supplied `.env.example` uses `gpt-5.6-luna`. Without a `.env` file, the app defaults to deterministic mode so tests remain repeatable. Pydantic validation and deterministic P1 rules remain mandatory guardrails.


## Setup

```bash
python -m venv .venv
.venv\\Scripts\\activate  # Windows PowerShell
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the FastAPI interface.

## Sample runs

```bash
curl -X POST http://127.0.0.1:8000/triage -H "Content-Type: application/json" -d "{\"subject\":\"Production outage\",\"body\":\"All users cannot access production.\"}"
curl http://127.0.0.1:8000/accounts/ACC-3336/brief
python -m scripts.ingest_kb
python -m eval.evaluator
pytest
```

## Task 1: triage

`POST /triage` accepts `subject` and `body`, performs BM25 retrieval over the Markdown knowledge base, classifies the ticket, applies P1-P4 policy, routes it to a team, and returns a Pydantic-validated response.

P1 is reserved for critical outage, security, data-loss, or broad production impact. P2 is high-impact blocked workflow; P3 is moderate with a workaround; P4 is a low-impact information, cosmetic, or feature request.

## Task 2: account brief

`GET /accounts/{account_id}/brief` reads account context and filters linked tickets using a deterministic, dataset-relative 90-day window. The source data contains intentionally unmatched account IDs, so missing links become `data_gaps`, not runtime failures.

When OpenAI is enabled, the account path uses two Responses API calls: evidence/risk extraction and then final structured brief generation. Direct ticket quotes are retained as risk evidence.

## Task 3: evaluation

`eval/evaluator.py` defines five cases per task, including adversarial inputs. It applies deterministic schema, severity, evidence, and missing-data checks, then writes `eval/eval_report.json` with pass/fail and a 0-1 score.

## Task 4: Design note

### Failure modes and controls

The first and most consequential failure mode is incorrect triage, especially under-prioritising a genuine P1 incident. The system therefore applies deterministic P1–P4 policy checks before any model enrichment. P1 output is protected from an LLM downgrade, and the final object is validated against a Pydantic schema. In production, I would detect priority drift with a labelled hold-out set, a dashboard of P1/P2 rates by product, and review of model-versus-rule disagreements. Mitigations include conservative escalation rules, a manual-review queue, and regression evaluation after prompt or model changes.

The second failure mode is ungrounded or misleading advice. BM25 retrieval can select a weak KB chunk, and an LLM may then invent a known-issue match or unsupported remediation step. The design keeps the KB source file, heading, excerpt, and score with every match. Each ticket-derived churn or escalation risk must carry an exact ticket quote and ID. I would monitor retrieval scores, unsupported citations, and agent overrides. A low score should suppress the “known issue” claim; a citation mismatch should return the deterministic fallback. I would add hybrid retrieval only after measuring material BM25 misses.

The third failure mode is incomplete or inconsistent source data. The supplied dataset deliberately includes tickets whose `account_id` has no matching account, which can otherwise produce an overly confident TAM brief. The service exposes this as `data_gaps` rather than silently joining unrelated data. In production, I would measure unmatched-account rate, null-field rate, ticket-ingestion lag, and stale-account-summary age. A data-quality threshold should block automated risk conclusions; the API should return a partial brief with clearly labelled gaps rather than fail.

### Latency versus quality

The main quality trade-off is the Task 2 two-step prompt chain. The first call extracts grounded facts and evidence; the second converts only those facts into a concise brief. This reduces hallucinated risks and improves auditability, but adds a second model call. Retrieval is local and fast because BM25 over a small Markdown corpus has negligible latency compared with inference. If latency were the hard constraint, I would return the deterministic brief immediately, use one model call only for optional prose, cap the recent-ticket context, and cache briefs by account ID plus latest-ticket timestamp.

### Data sensitivity

Support tickets and account records can contain names, email addresses, contract information, incident details, and other PII. The repository protects credentials with `.env` and `.gitignore`, and the current mock data is synthetic; production needs stronger controls. Data sent to an external model API should be minimised to the fields and KB chunks necessary for the request. A redaction layer should remove or tokenize email addresses, phone numbers, access tokens, credentials, payment details, and unnecessary contacts. Raw prompts and model outputs should not be logged; logs should contain correlation IDs, timings, model version, and redacted errors. Access should use least-privilege accounts, encryption, short retention, audit logs, and an approved data-processing configuration. High-risk cases can go to an internal endpoint or human workflow.

### Scaling to 10× ticket volume

At ten times the volume, synchronous model calls and repeated JSON loading will fail before BM25 becomes the main bottleneck. They increase latency, rate-limit exposure, and cost, and a P1 burst could delay ordinary triage. I would keep data and the KB index in long-lived process memory or managed storage, then add queues, concurrency limits, exponential-backoff retries, rate limiting, and P1 priority lanes. Account briefs should be asynchronous and cached, invalidating when tickets or account data change. Observability should track latency, queue depth, token use, retrieval quality, fallback rate, and evaluation regressions. CI should run deterministic evaluations on every change, with scheduled model-based regression checks.
