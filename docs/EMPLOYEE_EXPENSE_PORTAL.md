# Employee Expense Claim portal

Employees can use **Home → Submit an Expense** at
`/volunteering/expense-claim`. The existing `/desk/expense-claim` interface is
retained for staff review, corrections, approval and accounting.

The portal creates the same Expense Claim document, not a separate reimbursement
record. Submission enters **Pending Receipt Review**. Existing independent receipt
review, reporting-authority routing, approval limits, project-budget controls and
Accounts settlement continue unchanged.

## Employee fields

- Employee and reporting manager: read-only, based on the logged-in user.
- Project: active projects where the employee is a listed member, irrespective of
  whether their membership has Basic or Financial viewing access.
- Purpose of the claim.
- Payment source: personal money, the employee's own submitted/paid/unsettled
  advance, or a reporting manager's advance subject to existing funding rules.
- Emergency expense, with an emergency date and explanation when selected.
- Up to ten expense items, each with a date, searchable project expense account,
  optional supplier and receipt number, description, amount and receipt evidence.

Each item requires a private PDF, PNG or JPEG receipt of at most 5 MB. The total
upload limit is 25 MB. Per-item receipt URLs are also stored on the existing claim
detail rows, allowing reviewers to associate each bill with its item.

Series, company, department, cost centre, payable account, ledger expense account
and sanctioned amounts are not employee-editable portal inputs. The server checks
project membership and permitted project accounts again during submission. No
Chart of Accounts, account balances or additional accounting roles are granted.

Advisory server messages are displayed with the submission confirmation; warnings
do not turn a successful submission into an error. Actual permission, budget and
validation failures still block submission.

## Verification

Focused backend tests:

```sh
bench --site sevamrita.local run-tests --app volunteering \
  --module volunteering.volunteering.test_expense_claim_portal
```

Local browser tests do not run the full-site fixture seeder:

```sh
BASE_URL=http://127.0.0.1:8001 npx playwright test \
  --config playwright.expense-portal.config.ts
```

Set `E2E_EXPENSE_PORTAL_WRITES=1` to additionally submit a fictional ₹1 local claim.
The browser suite refuses non-localhost targets.
