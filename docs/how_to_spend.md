# How to spend (staff guide)

Mirror of the in-app Wiki page `How-to-Spend`. Prefer the Wiki in Desk after migrate.

Every expenditure should follow **one** path. Hubs: **My Work** (attendance) and **My Expenses** (advances, claims, PO/PI).

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

- New advance blocked while residual on another is **above** replenish threshold (default **10%**)
- Residual ≤10% allows replenishment; leftovers must still be claimed or returned ([Advances with Residual](query report))
- Settle via Expense Claim linked to the Advance

## Approvals

Approvals follow **Reports To** and **Designation** limits. If under limit: Approve or Reject. If over limit: Reject or Escalate only. No self-approval.

## Accounts

Accounts does not approve day-to-day spends. After approval they create Payment Entry.

See also: [tally_to_erpnext_accounts_guide.md](tally_to_erpnext_accounts_guide.md)
