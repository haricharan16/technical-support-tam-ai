"""OpenAI Responses API adapter with deterministic offline mode."""
from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()


class LLMService:
    """Preserves the application-wide JSON-in/JSON-out provider contract."""

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "deterministic").lower()

    @property
    def enabled(self) -> bool:
        return self.provider == "openai"

    def json_completion(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Generate structured JSON through the OpenAI Responses API.

        The JSON-schema response format is used where a caller supplies a Pydantic
        schema. Schema-less extraction steps use JSON object mode. Parsed content is
        deliberately validated again by the existing Pydantic callers.
        """
        if self.provider == "deterministic":
            return None
        if self.provider != "openai":
            raise ValueError("LLM_PROVIDER must be openai or deterministic")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai. Use deterministic mode for offline tests.")

        from openai import OpenAI

        response_format: dict[str, Any]
        if schema:
            response_format = {
                "type": "json_schema",
                "name": "support_tam_response",
                "schema": schema,
                "strict": False,
            }
        else:
            response_format = {"type": "json_object"}

        response = OpenAI(api_key=api_key).responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            instructions=system,
            input=user,
            reasoning={"effort": "none"},
            text={"format": response_format},
        )
        return self._parse_json(response.output_text or "")

    @staticmethod
    def _parse_json(output: str) -> dict[str, Any]:
        output = output.strip()
        if not output:
            raise RuntimeError("OpenAI returned no text output.")
        if output.startswith("```"):
            output = re.sub(r"^```(?:json)?\s*|\s*```$", "", output, flags=re.IGNORECASE).strip()
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenAI returned invalid JSON: {output[:500]!r}") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("OpenAI must return a JSON object.")
        return parsed
