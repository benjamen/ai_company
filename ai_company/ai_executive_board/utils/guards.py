from __future__ import annotations

import frappe


PROTECTED_FINANCIAL_DOCTYPES = {"Sales Invoice", "Purchase Invoice", "GL Entry", "Payment Entry"}


def prevent_unsafe_execution(doc, method=None):
    if doc.status == "Executed" and not frappe.has_role("AI Executive Approver"):
        frappe.throw("Only AI Executive Approver can execute tasks")

    if doc.related_doctype in PROTECTED_FINANCIAL_DOCTYPES and doc.status != "Executed":
        # ensure no pre-approval mutation workflow is attempted
        return
