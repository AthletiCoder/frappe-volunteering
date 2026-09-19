# Local portal E2E and staging-readiness report

Test window: 18–19 September 2026, Asia/Kolkata.

## Result

The current local working tree is browser-test green:

**195 passed, 0 failed, 0 skipped, 0 flaky; runtime 36.8 minutes.**

This includes one authentication/setup case and 194 functional cases. The tests
targeted `http://127.0.0.1:8001`, site `sevamrita.local`, with one Chromium worker
and no retries. The tested branch is `codex/receipt-review-workflow`; its saved
Git HEAD is `66bab83fa5e8046cd340d0b135d9f7db0a6db5f1`, but the run also includes the
current uncommitted working-tree changes.

This is a clean localhost release gate. It is not proof that an older Frappe Cloud
database will migrate successfully. Staging still needs a backup, deployment of
the exact intended commit, successful migration, and role-based smoke testing.

No commit, push, deployment, real bank transfer, or external remittance was made
during this test-update task.

## What was modernised

The broad suite originally contained assumptions from older versions of the
product. The tests and fixtures now represent the current implementation:

- advances require an eligible project and an approved reimbursement bank account;
- employees may have multiple outstanding advances and may request any amount;
- approval actions use live total outstanding exposure and the current Reports To chain;
- the canonical E2E project is approved, has members and financial access, and has
  employee-facing expense labels mapped by Accounts;
- expense claims enter receipt review before manager approval;
- employees use the current Home labels and portal routes;
- Daily Work Log rows select an accessible project;
- Purchase Invoice test data carries the Purchase Order project and cost centre;
- time-dependent attendance, leave and WFH assertions poll for the committed record;
- security tests send a valid authenticated request so they verify permission denial,
  rather than stopping at CSRF validation; and
- the unpaid-person scenario now verifies that an advance is not created before
  bank-account approval instead of expecting the obsolete unrestricted save.

One real product defect was found while modernising the tests. A reporting manager
could see a subordinate's Attendance Request but Frappe rejected Approve/Cancel
because document submission checks `write` permission first. The scoped permission
logic now grants the direct reporting manager write/submit/cancel access to that
subordinate's saved request, while still denying create and delete. The focused
backend permission tests pass 4/4, and the actual browser WFH approval/cancellation
flows pass in the full suite.

The complete reimbursement lifecycle has its own 240-second timeout because it
deliberately crosses five real UI stages. It passed without retries:

1. Employee submits an expense with private receipt evidence.
2. Manager cannot approve before receipt review.
3. Independent receipt reviewer verifies the evidence.
4. Reporting manager approves the claim.
5. Accounts creates and submits a local cash Payment Entry.
6. The claim becomes Paid and the employee can view the result.

## Coverage represented in the green run

| Area | Verified behavior |
| --- | --- |
| Advances | Home form, project and bank eligibility, private quotations, drafts, multiple requests, live total-outstanding escalation, Reports To chain, freeze/unfreeze, manager float and settlement |
| Expense claims | Home form, safe account choices, receipt evidence, receipt review, manager approval/rejection, caps, project budgets, strict override, payment and Paid status |
| Projects | Proposals, one-manager approval, manager editing, later-change approval, basic/financial visibility, claimant membership, viewer access and Accounts mapping |
| Bank details and invoices | Employee submission, masked data, Accounts Manager approval, Accounts User denial, GST/non-GST PDF and Word, signer variants, optional fields and office addresses |
| Accounting | Vendor purchase flow, Purchase Invoice safeguards, Payment Entry permissions, ledgers, bank reconciliation, budget settings and manager float |
| HR | Attendance, work logs, leave, WFH, manager notes, reporting hierarchy, thresholds, backdating, unpaid exclusions and scheduled attendance behavior |
| Portal and security | Profile privacy, logout, mobile layouts, dark theme, role-specific navigation, protected APIs and volunteering/coordinator access |

## Evidence and repeat command

Final artifacts:

- JSON: `/private/tmp/sevamrita-staging-e2e-final.json`
- HTML: `/private/tmp/sevamrita-staging-e2e-final-html/index.html`
- Downloads and run metadata: `/private/tmp/sevamrita-staging-e2e-final-results/`
- Production frontend build: `/private/tmp/sevamrita-staging-build-final/`

The HTML/JSON reports can contain local test-user and trace details. Keep them out
of public repositories.

The exact final browser command was:

```bash
BASE_URL=http://127.0.0.1:8001 \
E2E_FORCE_AUTH=1 \
E2E_EXPENSE_PORTAL_WRITES=1 \
E2E_PROJECT_DEMOS=1 \
PLAYWRIGHT_JSON_OUTPUT_NAME=/private/tmp/sevamrita-staging-e2e-final.json \
PLAYWRIGHT_HTML_OUTPUT_DIR=/private/tmp/sevamrita-staging-e2e-final-html \
npx playwright test --project=chromium --reporter=line,json,html \
  --output=/private/tmp/sevamrita-staging-e2e-final-results --workers=1
```

The production frontend build also passed: 64 modules, 1.15 seconds. Vite emitted
one non-blocking chunking warning because `frappe.js` is imported both statically
and dynamically. Ruff passes for the backend fixture and Attendance Request
permission files changed during this test task. `git diff --check` passes.

The broader application-wide Ruff scan is not yet a green project gate: it reports
55 existing style/lint findings across older and unrelated modules. These are not
browser-test failures and were not automatically rewritten during this task.

## Backend verification already completed

The focused accounting, advance, invoice and portal backend set previously passed
125 tests across nine modules. After the scoped Attendance Request permission
change, its dedicated backend module was rerun and passed 4/4. The full browser run
then exercised the corresponding manager approval and cancellation paths.

## Staging deployment gate

Before treating staging as ready:

1. Review the intended working-tree diff and decide exactly which files belong in
   the release commit.
2. Commit and push only after explicit authorisation.
3. Back up the staging database and public/private files.
4. Deploy the exact branch commit and require successful build, release and site
   migration jobs.
5. On the old staging database, verify project owners/members, approved project
   proposals and changes, account mappings, approved employee bank details,
   Employee grades, reporting chains and receipt-reviewer roles.
6. Smoke-test with employee, receipt reviewer, reporting manager, Projects Manager,
   Project Viewer, Accounts User and Accounts Manager personas.
7. Run one fictional end-to-end claim without invoking real payment or notification
   integrations.

The write-enabled local E2E suite intentionally must not be pointed at staging or
production without a separate safe-data plan.
