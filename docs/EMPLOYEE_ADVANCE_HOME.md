# Employee advances and supervisor Home

Employee advance requests now use `/volunteering/advances?new=1` from Home. The existing Desk forms remain available. Every eligible employee can request any positive amount; Employee Grade determines approval authority, never request eligibility or a request-amount cap.

Employees may create and submit multiple requests regardless of the count or outstanding balance of earlier advances, including unpaid/pending requests and fully outstanding paid advances. There is no aggregate outstanding-advance cap or replenishment-percentage gate. Existing balances are still tracked and must be reconciled through bills or returns. The legacy `max_unsettled_advances` setting is hidden and ignored, including on old databases; the residual percentage still used for Manager Advance expense-source selection/reporting does not restrict new requests.

## Eligibility and request fields

The requester must be an active Employee, be the owner or listed participant of an approved, active, non-archived Project in the same company, and have an Accounts Manager-approved reimbursement bank account. All these rules are enforced on the server, including requests originating in Desk.

Employees choose their intended project, amount, purpose, required-by date, expected settlement date and whether the funds are for their own or team expenses. Estimates/quotations and additional notes are optional. Series, employee, company, currency, ledger account and approval routing are assigned by the server. Bank details are shown masked.

An intended project is informational: an advance does not consume project budget. Expense Claims and Purchase Orders continue to commit spend under the existing budget rules.

Team expenses are available only to a requester with active direct reports. New requests marked My expenses are not offered as manager float to subordinates. Legacy manager floats without the new intended-project field remain usable for compatibility.

Save draft does not request approval or disburse funds. Submit enters the existing Pending Approval workflow. The advance list shows request/paid/claimed/returned/open amounts, supporting documents, dates and linked claims. Submit bills opens the employee Expense Claim form with the selected paid advance.

## Sequential approval

Advance requests always start with the immediate reporting manager. At every review step, approval authority is checked against the employee's live total outstanding exposure: the current request plus all other active pending, approved or unpaid advances. It is recalculated when the reviewer opens or acts on the request, so later requests, rejections and settlements immediately change whether that reviewer may approve or must escalate. The route is not frozen when the request is submitted.

Other active advances reserve their requested amount less recorded claims and returns, including an approved but not-yet-disbursed remainder. That unpaid remainder still counts even if HRMS labels the paid portion Claimed or Returned. Draft, rejected, cancelled and fully settled advances do not contribute. This authority exposure is distinct from the disbursed residual shown for bill reconciliation.

If the live total exceeds that person's authority, they must review and Escalate (with a reason) to the next linked person in Reports To, without skipping actual linked reviewers. The first reviewer with sufficient authority may Approve or Reject. Lower-authority reviewers may Reject but cannot Approve, even through the server API. Higher approvers get access only to the pending request currently assigned to them, not all employee advances. An approver cannot rewrite the employee's request details or approve their own advance.

Default approval thresholds for others are: Associate 0, Manager INR 2,000, Vice President INR 5,000, President INR 10,000, Director INR 25,000, CEO INR 50,000, Executive Board INR 100,000, Board of Directors unlimited. Saved authority configuration still takes precedence. When the reporting chain ends, the existing Board fallback applies. Reporting chains must link each person who should review; an absent grade does not create a fictional reviewer.

Legacy self-advance values are retained for old database compatibility but hidden and ignored. Expense Claims use a separate, Accounts Manager-configurable authority limit by Employee Grade. They follow the same person-by-person Reports To chain, but test only the individual claim amount rather than total outstanding exposure. Purchase Order routing is unchanged.

## Supervisor dashboard and freeze

Any active Employee with active direct reports gets My team in Home and navigation at `/volunteering/team`; no new broad HR or Accounts role is required.

The dashboard is restricted to current direct reports. It shows work details, project memberships, attendance today/month, request counts and recent advances. It does not expose salaries, bank details, receipt files or ledger balances. Manager advance approval still uses the existing Desk workflow.

A reporting manager can freeze or unfreeze new advances for a direct report with a required reason. Freeze prevents new requests and submission/resubmission of existing drafts, including through Desk. It does not cancel, confiscate or prevent reconciliation of an existing advance. Each decision is recorded in append-only Employee Advance Freeze Event history; direct editing/deletion is blocked.

## Verification

Focused backend suites: `test_advance_portal`, `test_employee_advance_controls`, `test_designation_approval`, `test_manager_float_service`, `test_home_service`, `test_accounting_budget`, `test_employee_bank_accounts`, and `test_expense_claim_portal`. The supplemental browser regression `AC-ADV-012` checks that a new pending request removes Approve from both the native menu and primary action, and rejecting it restores Approve. The frontend production build and local browser checks cover the employee form and supervisor dashboard. This is focused regression coverage, not a claim that every legacy HR test passes.
