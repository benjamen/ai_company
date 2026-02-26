from __future__ import annotations

import frappe
from frappe.model.document import Document


class AIExecutiveTask(Document):
    def validate(self):
        if self.status == "Approved" and not frappe.has_role("AI Executive Approver"):
            frappe.throw("Only AI Executive Approver can approve")

        if self.status == "Rejected":
            self.executed_at = None
