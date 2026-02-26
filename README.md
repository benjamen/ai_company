## ai_company

Frappe app containing the **AI Executive Board** implementation.

## Installation

```bash
bench get-app ai_company
bench --site <site_name> install-app ai_company
bench --site <site_name> migrate
```

## Bench Commands

```bash
bench --site <site_name> execute ai_company.ai_executive_board.api.executive_task.create_executive_task --kwargs "{'title':'Market Expansion','problem_statement':'Choose expansion strategy','strategic_priority':'Growth'}"
bench --site <site_name> execute ai_company.ai_executive_board.api.executive_task.trigger_debate --kwargs "{'task_name':'AET-.00001'}"
bench --site <site_name> execute ai_company.ai_executive_board.api.executive_task.approve_executive_task --kwargs "{'task_name':'AET-.00001'}"
```

## Migration Notes

- Includes module `Ai Executive Board` and five DocTypes:
  - `AI Executive Task`
  - `AI Deliberation Round` (child table)
  - `AI Department Position` (child table)
  - `AI Department Config`
  - `AI Audit Log`
- Post model sync patch creates roles:
  - `AI Executive System`
  - `AI Executive Approver`
  - `AI Auditor`
- Debate execution runs via background job queue (`long`) using `enqueue_executive_task`.

## API Endpoints

- `ai_company.ai_executive_board.api.executive_task.create_executive_task`
- `ai_company.ai_executive_board.api.executive_task.trigger_debate`
- `ai_company.ai_executive_board.api.executive_task.approve_executive_task`
- `ai_company.ai_executive_board.api.executive_task.reject_executive_task`
- `ai_company.ai_executive_board.api.executive_task.rerun_debate`
