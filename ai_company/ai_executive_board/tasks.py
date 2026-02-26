from __future__ import annotations

import frappe

from ai_company.ai_executive_board.services.executive_debate_engine import ExecutiveDebateEngine


def enqueue_executive_task(task_name: str):
    frappe.enqueue(
        method="ai_company.ai_executive_board.tasks.run_executive_task",
        queue="long",
        job_name=f"ai_executive_task::{task_name}",
        task_name=task_name,
    )


def run_executive_task(task_name: str):
    engine = ExecutiveDebateEngine(task_name)
    engine.run()
