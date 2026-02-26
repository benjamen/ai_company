from __future__ import annotations

import frappe


ROLES = ["AI Executive System", "AI Executive Approver", "AI Auditor"]


def after_install():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role}).insert(ignore_permissions=True)
