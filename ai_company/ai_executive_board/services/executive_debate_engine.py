from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from ai_company.ai_executive_board.services.ai_llm_client import LLMClient, LLMClientError


class ExecutiveDebateEngine:
    def __init__(self, task_name: str):
        self.task = frappe.get_doc("AI Executive Task", task_name)
        self.client = LLMClient()

    def run(self) -> None:
        try:
            self.run_round_1()
            self.run_round_2()
            self.run_consolidation()
            self.run_risk_audit()
            self.task.db_set("status", "PendingHuman")
        except Exception as exc:
            frappe.log_error(frappe.get_traceback(), "Executive debate failed")
            self.task.db_set("status", "Error")
            self._notify_admin(str(exc))
            raise

    def run_round_1(self) -> None:
        round_doc = self._ensure_round(1, "Independent")
        for department in self._active_departments():
            prompt = self._build_round_prompt(department, round_number=1)
            payload = self.client.generate(prompt=prompt)
            self._validate_stage_payload(payload, ("initial_position", "risk_score", "confidence_score"))
            self._validate_score_range(payload["risk_score"], "risk_score")
            self._validate_score_range(payload["confidence_score"], "confidence_score")

            round_doc.append(
                "positions",
                {
                    "department": department.name,
                    "initial_position": payload["initial_position"],
                    "risk_score": cint(payload["risk_score"]),
                    "confidence_score": cint(payload["confidence_score"]),
                    "influence_weight_used": flt(department.influence_weight),
                },
            )
            self._log_audit(department.name, "Independent", prompt, payload)

        round_doc.completed = 1
        round_doc.save(ignore_permissions=True)
        self.task.db_set("status", "Round2")

    def run_round_2(self) -> None:
        round_1 = frappe.get_doc("AI Deliberation Round", {"parent": self.task.name, "round_number": 1})
        round_doc = self._ensure_round(2, "CrossReview")

        for position in round_1.positions:
            department = frappe.get_doc("AI Department Config", position.department)
            others = [
                {"department": p.department, "initial_position": p.initial_position}
                for p in round_1.positions
                if p.department != position.department
            ]
            prompt = department.prompt_template_round2.format(
                problem_statement=self.task.problem_statement,
                own_position=position.initial_position,
                other_positions=json.dumps(others, indent=2),
                strategic_priority=self.task.strategic_priority,
            )
            payload = self.client.generate(prompt=prompt)
            self._validate_stage_payload(payload, ("conflicts_identified", "revised_position", "risk_score"))
            self._validate_score_range(payload["risk_score"], "risk_score")

            round_doc.append(
                "positions",
                {
                    "department": department.name,
                    "initial_position": position.initial_position,
                    "revised_position": payload["revised_position"],
                    "conflicts_identified": payload["conflicts_identified"],
                    "risk_score": cint(payload["risk_score"]),
                    "confidence_score": cint(position.confidence_score),
                    "influence_weight_used": self._effective_weight(department),
                },
            )
            self._log_audit(department.name, "CrossReview", prompt, payload)

        round_doc.completed = 1
        round_doc.save(ignore_permissions=True)
        self.task.db_set("status", "Consolidation")

    def run_consolidation(self) -> None:
        round_2 = frappe.get_doc("AI Deliberation Round", {"parent": self.task.name, "round_number": 2})
        weighted = []
        for p in round_2.positions:
            weighted.append(
                {
                    "department": p.department,
                    "revised_position": p.revised_position,
                    "weighted_risk": flt(p.risk_score) * flt(p.influence_weight_used),
                    "risk_score": p.risk_score,
                    "confidence_score": p.confidence_score,
                }
            )

        prompt = json.dumps({"task": self.task.name, "weighted_positions": weighted}, indent=2)
        payload = self.client.generate(prompt=prompt)
        required = (
            "recommended_strategy",
            "implementation_plan",
            "financial_impact_summary",
            "risk_mitigation_plan",
            "final_risk_score",
            "overall_confidence",
        )
        self._validate_stage_payload(payload, required)
        self._validate_score_range(payload["final_risk_score"], "final_risk_score")
        self._validate_score_range(payload["overall_confidence"], "overall_confidence")

        round_doc = self._ensure_round(3, "Consolidation")
        round_doc.consolidated_output = json.dumps(payload, indent=2)
        round_doc.completed = 1
        round_doc.save(ignore_permissions=True)
        self._log_audit("AI COO", "Consolidation", prompt, payload)
        self.task.db_set("status", "RiskReview")

    def run_risk_audit(self) -> None:
        consolidation = frappe.get_doc(
            "AI Deliberation Round", {"parent": self.task.name, "stage": "Consolidation"}
        )
        prompt = consolidation.consolidated_output
        payload = self.client.generate(prompt=prompt)
        required = (
            "logical_flaws",
            "hidden_assumptions",
            "regulatory_risks",
            "adjusted_risk_score",
            "adjusted_confidence_score",
        )
        self._validate_stage_payload(payload, required)
        self._validate_score_range(payload["adjusted_risk_score"], "adjusted_risk_score")
        self._validate_score_range(payload["adjusted_confidence_score"], "adjusted_confidence_score")

        round_doc = self._ensure_round(4, "RiskAudit")
        round_doc.consolidated_output = json.dumps(payload, indent=2)
        round_doc.completed = 1
        round_doc.save(ignore_permissions=True)
        self._log_audit("AI Auditor", "RiskAudit", prompt, payload)

        self.task.db_set("overall_risk_score", cint(payload["adjusted_risk_score"]))
        self.task.db_set("overall_confidence_score", cint(payload["adjusted_confidence_score"]))

    def _ensure_round(self, round_number: int, stage: str):
        existing = frappe.db.get_value(
            "AI Deliberation Round", {"parent": self.task.name, "round_number": round_number}, "name"
        )
        if existing:
            return frappe.get_doc("AI Deliberation Round", existing)
        round_doc = frappe.get_doc(
            {
                "doctype": "AI Deliberation Round",
                "parent": self.task.name,
                "parentfield": "deliberation_rounds",
                "parenttype": "AI Executive Task",
                "round_number": round_number,
                "stage": stage,
            }
        )
        round_doc.insert(ignore_permissions=True)
        return round_doc

    def _build_round_prompt(self, department, round_number: int) -> str:
        template = department.prompt_template_round1 if round_number == 1 else department.prompt_template_round2
        context = self._fetch_related_record()
        return template.format(
            problem_statement=self.task.problem_statement,
            related_data=json.dumps(context, indent=2),
            strategic_priority=self.task.strategic_priority,
        )

    def _fetch_related_record(self) -> dict[str, Any]:
        if not (self.task.related_doctype and self.task.related_name):
            return {}
        return frappe.get_doc(self.task.related_doctype, self.task.related_name).as_dict()

    def _active_departments(self):
        return frappe.get_all(
            "AI Department Config",
            filters={"active": 1},
            fields=["name", "department_name", "strategic_bias", "influence_weight", "prompt_template_round1", "prompt_template_round2"],
        )

    def _effective_weight(self, department) -> float:
        weight = flt(department.influence_weight)
        if self.task.strategic_priority == department.strategic_bias:
            weight *= 1.2
        return weight

    def _validate_stage_payload(self, payload: dict[str, Any], required_keys: tuple[str, ...]) -> None:
        missing = [key for key in required_keys if key not in payload]
        if missing:
            raise LLMClientError(_("Missing required keys: {0}").format(", ".join(missing)))

    def _validate_score_range(self, value: Any, label: str) -> None:
        numeric = cint(value)
        if numeric < 0 or numeric > 100:
            raise LLMClientError(_("{0} must be between 0 and 100").format(label))

    def _log_audit(self, department: str, stage: str, prompt_payload: str, response_payload: dict[str, Any]) -> None:
        meta = response_payload.get("_meta", {})
        frappe.get_doc(
            {
                "doctype": "AI Audit Log",
                "executive_task": self.task.name,
                "department": department,
                "stage": stage,
                "prompt_payload": prompt_payload,
                "response_payload": json.dumps(response_payload, indent=2),
                "model_used": meta.get("model"),
                "tokens_used": cint(meta.get("tokens_used")),
                "cost_estimate": flt(meta.get("cost_estimate")),
                "execution_time_ms": cint(meta.get("execution_time_ms")),
                "created_at": frappe.utils.now_datetime(),
            }
        ).insert(ignore_permissions=True)

    def _notify_admin(self, error_message: str) -> None:
        frappe.sendmail(
            recipients=[frappe.db.get_single_value("System Settings", "email")],
            subject=_("AI Executive Debate Failure"),
            message=error_message,
        )
