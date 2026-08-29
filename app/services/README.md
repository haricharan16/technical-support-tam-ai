# Service responsibilities

- `data_loader.py`: JSON loading and deterministic 90-day filtering.
- `triage_service.py`: preprocessing, P1-P4 policy, routing, retrieval orchestration.
- `account_service.py`: account health, risk checks, ticket evidence, two-step LLM chain.
- `llm_service.py`: OpenAI Responses API adapter with deterministic offline mode.
