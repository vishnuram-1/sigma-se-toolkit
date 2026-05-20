# Scenario-Modeling Workbook Structure

The canonical page layout. Adapt the names to the domain (Forecast / Plan /
Scenario / What-If) but keep the structure.

## Pages (in order)

1. **Sources** (hidden or admin-only)
   - Base series element
   - Scenario registry input table
   - Fan-out cross-join → linked input table
   - Any single-cell input tables for global assumptions (ASP, budget cap, etc.)

2. **Scenario Editor** (primary user page)
   - Header: page-filter control on `forecast_name` (single-select, no nulls).
   - "Create new forecast" button + create-scenario modal.
   - "Submit for approval" button + submit-approval modal.
   - The linked input table (forecast_name column hidden).
   - Optional: a KPI strip showing scenario-vs-base headline numbers.
   - Optional: a comparison chart with the base series and the active scenario.
   - "View approvals" navigation button → Approval Flow page.

3. **Approval Flow** (approver page)
   - Pending queue table (filtered to `status = "Pending" AND approval_status is null`).
   - Approve column with click action → final-approval modal.
   - Approved log table (filtered to `approval_status = "Approve"`).
   - Denied / changes-requested log (filtered to other statuses).
   - "Back to editor" navigation button.

## Modals

| Modal | Triggered by | Contents | Submit action |
|---|---|---|---|
| Create scenario | "Create new forecast" button | Text: forecast name | Insert into registry, set page filter, close |
| Submit for approval | "Submit for approval" button | Text: comments | Update registry row (status, comments, submitted_by/on), close |
| Final approval | Approve column click on pending queue | Segmented: Approve/Deny/Change Requested; Text: comments | Update registry row (approval_status, comments, approval_by/on), close |
| Locked notice | Click on forecast cell when approved | Text: "No edits allowed on approved scenarios" | Close |

All modals: hide header, hide footer, use custom in-body Cancel + Submit
buttons. Cancel is outlined, Submit is filled.

## Action ordering

For every multi-step button click, list actions in this order:

1. **Clear** any modal controls about to be reused (stale text).
2. **Set** any hidden ID controls (so downstream actions know which row).
3. **Open** the modal (or close it, on submit).
4. **Insert / update** rows (so the data is written before the UI re-renders).
5. **Set** the page filter (if you want the user repositioned).

This order matters because Sigma runs them sequentially and there is no
rollback.
