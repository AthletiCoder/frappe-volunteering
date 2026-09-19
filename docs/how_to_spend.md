# How to spend (staff guide)

Mirror of the in-app Wiki page `How-to-Spend`. Prefer the Wiki in Desk after migrate.

Every expenditure should follow **one** path. Start at **Home** (`/volunteering/home`) for leave, work, advances, claims, and payments.

1. **Vendor payment (preferred)** — Purchase Order → Purchase Invoice → Payment Entry
2. **Employee Advance** — float before buying (local purchase, travel, events); settle with Expense Claim
3. **Reimbursement (exception)** — Expense Claim only when advance/vendor was not feasible

## Prefer vendor payment

Above the **Vendor Payment Threshold** (default ₹5,000, configurable in Volunteering Accounting Settings), use a Purchase Order.

| Step | Who |
|------|-----|
| Purchase Order | Accounts / procurement |
| Purchase Invoice | Either staff or Accounts (from approved PO + attach bill) |
| Payment Entry | Accounts only |

**Pay before tax invoice:** Approved PO → Payment Entry against PO (supplier advance) → later PI from PO clears the advance.

If you must reimburse above the threshold, fill **Vendor Payment Override Reason**.

## Employee Advance

- Multiple advance requests of any positive amount are allowed regardless of grade or previous outstanding balances. Each request starts with the reporting manager and moves up one reviewer at a time. At each step, the reviewer is allowed to approve only if their authority covers the employee's live total outstanding advances, including this request; otherwise they must escalate. Project/bank eligibility and freeze controls still apply.
- Leftovers must still be claimed or returned; new requests do not clear earlier balances ([Advances with Residual](query report)).
- Select an intended active project in which you are a member; this is informational and does not commit budget. Settle via Expense Claim **on the Project** the spend belongs to — that is what budget controls check.

## Expense Claim

Set **Project** (required). Its Cost Centre is applied automatically. The Project's independent whole-budget and Expense Account controls are checked; linking an advance does not move budget by itself.

Each control is set on the Project as **No Control**, **Warn Only**, or **Strict**. Strict overruns require an authorised override and a Budget Exceedance Reason.

## Approvals

Approvals follow **Reports To** and **Designation** limits. If under limit: Approve or Reject. If over limit: Reject or Escalate only. No self-approval.

## Accounts

Accounts does not approve day-to-day spends. After approval they create Payment Entry.

See also: [tally_to_erpnext_accounts_guide.md](tally_to_erpnext_accounts_guide.md)
