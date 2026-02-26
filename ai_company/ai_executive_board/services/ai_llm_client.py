from __future__ import annotations

import json
import time
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint


class LLMClientError(frappe.ValidationError):
    """Raised when an LLM call fails structured validation."""


class LLMClient:
    def generate(
        self,
        prompt: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if not prompt:
            raise LLMClientError(_("Prompt is required"))

        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                start = time.perf_counter()
                response_text = self._call_provider(
                    prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                payload = self._validate_json(response_text)
                payload["_meta"] = {
                    "model": model,
                    "tokens_used": cint(len(prompt) / 4),
                    "cost_estimate": 0,
                    "execution_time_ms": int((time.perf_counter() - start) * 1000),
                }
                return payload
            except Exception as exc:
                last_error = exc

        raise LLMClientError(
            _("LLM response validation failed after retry: {0}").format(str(last_error))
        )

    def _call_provider(self, prompt: str, model: str, max_tokens: int, temperature: float) -> str:
        """Provider abstraction placeholder. Replace with vendor integration."""
        if hasattr(frappe.flags, "ai_executive_board_mock_response"):
            return frappe.flags.ai_executive_board_mock_response

        # Deterministic default payload for non-configured environments.
        return json.dumps(
            {
                "recommended_strategy": "Insufficient provider configuration",
                "implementation_plan": [],
                "financial_impact_summary": "No execution",
                "risk_mitigation_plan": [],
                "final_risk_score": 50,
                "overall_confidence": 40,
            }
        )

    def _validate_json(self, response_text: str) -> dict[str, Any]:
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise LLMClientError(_("LLM response is not valid JSON")) from exc

        if not isinstance(payload, dict):
            raise LLMClientError(_("LLM response JSON must be an object"))
        return payload
