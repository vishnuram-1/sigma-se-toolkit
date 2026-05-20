# Action Cheatsheet — Sigma primitives used in scenario apps

Every action below is a built-in Sigma action that can be wired to a button
click, a cell click, or a control change. Names are verbatim — use them
exactly as written.

## Insert row

Writes a new row to an input table.

- Target: scenario registry (input table on the Sources page).
- Source values: pull from modal controls (text inputs, segmented controls).
- Combine with `Set control value` to also update the page filter so the
  user lands on the row they just created.

## Update row

Edits an existing row in an input table. **Requires a row ID** — Sigma will
prompt you to add one the first time. The hidden `id` column then becomes
addressable.

- Pass the ID into the action via a `Lookup` formula on a scratch column, OR
  via a hidden control populated by the row's `select` action.
- For the approval flow, the approver's row-click sets a hidden
  `approval_target_id` control; the modal's Submit reads from it.

## Set control value

Programmatic write to a control's value.

- Use to position the page filter onto a freshly-created scenario.
- Use to pass a row ID from the pending-queue click into the approval modal.

## Clear control

Empties a control's value. **Run this before re-opening any modal** that has
text or segmented controls — otherwise stale values from the previous flow
show through.

## Open modal / Close modal

Standard modal lifecycle. Open is on the trigger button; Close is on every
in-modal button (Cancel, Submit, and on the success path after the data
mutation).

Best practice: hide the modal's default header and footer (so the close-X
isn't there), and provide your own Cancel / Submit buttons in the body. This
lets you control button positioning and styling.

## Navigate in this workbook

Page-to-page navigation. Use for the "View approvals" and "Back to editor"
buttons.

- Target: page ID + scroll position ("top of page" is the default).

## Conditional action

Wraps any of the above with an `if` predicate. Used for the lock-down notice:

> On select of forecast cell, IF `approval_status = "Approve"` THEN open
> "Locked" modal.

If the predicate is false, the action is skipped silently — no error.

## Conditional editing rule

Not a click action — lives in the **data model's Data Entry tab**, on the
linked input table. States the condition under which a column **is editable**.

For the forecast lock:

```
allow editing on [forecast] when
  approval_status != "Approve" OR approval_status is null
```

The `OR is null` clause is what lets a brand-new scenario be edited before
it has any approval status.

## Audit field formulas

Set these in the SAME action as the status change (insert / update row), not
in a separate writer:

- `submitted_by` = `CurrentUserEmail()`
- `submitted_on` = `Now()`
- `approval_by` = `CurrentUserEmail()`
- `approval_on` = `Now()`

`CurrentUserEmail()` is reliable for SSO'd Sigma users; for embed contexts
substitute the embed `userId` or `email` claim.
