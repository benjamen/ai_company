from __future__ import annotations

import frappe
from frappe import _

from ai_company.ai_executive_board.services.execution_service import ProductionExecutionService
from ai_company.ai_executive_board.tasks import enqueue_executive_task


def _require_role(role: str):
    if not frappe.has_role(role):
        raise frappe.PermissionError(_("Role required: {0}").format(role))


@frappe.whitelist()
def create_executive_task(title: str, problem_statement: str, strategic_priority: str, related_doctype=None, related_name=None):
    _require_role("AI Executive System")
    doc = frappe.get_doc(
        {
            "doctype": "AI Executive Task",
            "title": title,
            "problem_statement": problem_statement,
            "strategic_priority": strategic_priority,
            "related_doctype": related_doctype,
            "related_name": related_name,
            "status": "Draft",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def trigger_debate(task_name: str):
    _require_role("AI Executive System")
    task = frappe.get_doc("AI Executive Task", task_name)
    if task.status not in {"Draft", "Rejected"}:
        raise frappe.ValidationError(_("Task must be Draft or Rejected"))
    task.db_set("status", "Round1")
    enqueue_executive_task(task_name)
    return {"queued": True, "task": task_name}


@frappe.whitelist()
def approve_executive_task(task_name: str):
    _require_role("AI Executive Approver")
    task = frappe.get_doc("AI Executive Task", task_name)
    task.human_decision = "Approve"
    task.status = "Approved"
    task.save(ignore_permissions=True)
    ProductionExecutionService.execute(task)
    return {"status": task.status, "executed_at": task.executed_at}


@frappe.whitelist()
def reject_executive_task(task_name: str):
    _require_role("AI Executive Approver")
    task = frappe.get_doc("AI Executive Task", task_name)
    task.human_decision = "Reject"
    task.status = "Rejected"
    task.save(ignore_permissions=True)
    return {"status": task.status}


@frappe.whitelist()
def rerun_debate(task_name: str):
    _require_role("AI Executive System")
    task = frappe.get_doc("AI Executive Task", task_name)
    if task.status not in {"Rejected", "PendingHuman"}:
        raise frappe.ValidationError(_("Task must be Rejected or PendingHuman"))
    task.db_set("status", "Round1")
    enqueue_executive_task(task_name)
    return {"queued": True, "task": task_name}
