EXTRACT_VERSION = "account-extract-v1"
WRITE_VERSION = "account-write-v1"

EXTRACT_SYSTEM = """Extract only support risks grounded in the provided account and ticket data.
Each ticket-derived risk must include an exact short ticket quote and its ticket ID. Return JSON only."""

WRITE_SYSTEM = """Write a concise TAM account brief from the supplied extracted facts. Do not invent facts.
Return JSON with an executive summary, risks, and recommended talking points only."""
