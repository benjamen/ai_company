from __future__ import annotations

import frappe
from frappe import _


class ProductionExecutionService:
    @staticmethod
    def execute(task):
        if not frappe.has_permission("AI Executive Task", "write", task):
            raise frappe.PermissionError(_("Insufficient permission to execute task"))

        if not frappe.has_role("AI Executive Approver"):
            raise frappe.PermissionError(_("AI Executive Approver role required"))

        if task.status != "Approved":
            raise frappe.ValidationError(_("Task must be Approved before execution"))

        task.executed_at = frappe.utils.now_datetime()
        task.status = "Executed"
        task.save(ignore_permissions=True)
