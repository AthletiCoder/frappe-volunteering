# Expense claim retries and withdrawal

## Submission safety

Updated web and Android clients generate a request key before submitting an
uploaded invoice, a group of invoices, or a generated invoice with its claim.
The server saves the result in **Expense Claim Request** in the same transaction
as the claims, receipts and invoice numbering. Repeating that key and payload
returns the original result. Reusing the key with different details is rejected.

Creation and recovery lock the employee row until commit or rollback. Recovery
therefore waits for an in-flight submission before reporting whether it exists.
MariaDB snapshot conflicts restart the operation at most twice; a service caller
with earlier uncommitted writes is never automatically restarted.

The clients retain uncertain attempts and attachments on the device. Android
uses encrypted, atomic storage; the web uses IndexedDB scoped by origin and
employee. Receipt/signature bytes are removed after confirmation. Retry checks
the server first and uses the original key. Storage failure prevents sending.
After confirmation, the web offers **Submit another** to start a new attempt.
Android retains confirmation across restart if loading the result screen fails.
These changes protect updated clients; older clients without request keys retain
their existing API compatibility and should be updated.

## Closing claims

Employees can withdraw their own unapproved, unposted claims from claim details,
with a required reason. Receipts, amounts and history remain available. The
terminal **Withdrawn** state cannot be edited, reopened or submitted. It leaves
review queues and Home action counts and releases the pending project budget
reservation. Unposted advance allocations are retained as evidence; withdrawal
does not change actual advance disbursements or posted ledger balances.

Only a genuine unsubmitted **Draft** can be deleted. Manager-approved,
accounting-posted or paid claims require Accounts to handle cancellation.
Withdrawal, receipt review and approval take a claim row lock before changing it.

**Approved** and **Outstanding** show **Awaiting approval** until approval occurs,
instead of displaying the provisional sanctioned amount as an approved debt.
Rejected and withdrawn claims show no outstanding liability.

## Deployment and existing duplicates

Normal app migration must install the new DocType, withdrawal fields and updated
Expense Claim workflow before serving the updated clients. Deploy the backend
and built web assets together, and distribute the updated ERP Android app.
This document does not authorize deployment.

Existing duplicate claims are not deleted or automatically matched. Verify the
employee, project, supplier, invoice number/date, amount, receipt and accounting
status. Keep the valid original. Its employee can then withdraw the duplicate
with a reason after deployment; Accounts must handle anything already approved
or posted. No production records were changed during local verification.

## Verification

Verified locally on 24 November 2026: 120 backend tests (34 claim portal, 19
approval/receipt review, 7 routing, 14 budget, 8 manager float and 38 invoice
generation), 24 frontend tests, 12 desktop/mobile browser checks, and 138 Android
JVM tests in each of the debug and release configurations. ERP debug/release
builds and release APK signature verification passed.

- Backend: claim portal, approval, routing, budget, manager float and invoice
  generation regressions, including request reuse, mismatched payloads, rollback,
  ownership, version checks and withdrawal after approval.
- Browser: `e2e/tests/portal-regression/claim-retry.spec.ts` and
  `multi-invoice.spec.ts`, desktop and mobile, against an isolated local site.
  Covers lost responses, refresh recovery, concurrent retries, independent
  concurrent requests, withdrawal and separately dated invoices.
- Frontend: `npm run test:frontend`.
- Android: debug/release JVM tests and ERP APK builds. Physical-phone testing is
  separate; the phone was not connected for this verification.

Submission processing over three seconds is logged to `expense_submissions`
without receipt contents or employee details. Approval email uses the normal
email queue instead of waiting for SMTP during the request. Receipt attachment
pointers are persisted without an extra full claim save; workflow submission
still reloads and validates the complete claim.
