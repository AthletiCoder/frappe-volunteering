# Fund disbursement — ops checklist

Run after deploying the volunteering app changes:

```bash
bench --site YOUR_SITE migrate
bench --site YOUR_SITE clear-cache
```

## 1. Masters

1. Confirm Designations exist (Associate → Board of Directors) — seeded on migrate.
2. On each **Employee**: set **Designation** and **Reports To**.
3. Open **Volunteering Accounting Settings**:
   - Designation Approval Limits (seeded defaults)
   - Vendor Payment Threshold (₹5,000)
   - Cash Payment Limit (₹2,000)
   - Budget Hard-Block Overspend % (25)
   - Max Blocking Unsettled Advances (1)
   - Advance Replenish Residual % (10)
   - Payout Provider = `manual` (Cashfree later)

## 2. Company / Accounts

1. Default **Employee Advance Account** on Company (HR settings).
2. Mode of Payment: Bank / UPI / NEFT; Cash for small amounts only.
3. Projects: set **Project Type** (Campaign / Event / Admin), Cost Center, Department Budgets, Budget Status = Active.
4. Budget exceedance: on Approve, the pending manager must enter **Budget Exceedance Reason** if over budget. Above the hard-block %, escalate to the Budget Override Role (default NGO Board Chairperson).

## 3. Workflows

Migrate reloads fixtures. Confirm:

- Expense Claim Approval → Pending Approval
- Purchase Order Approval → Pending Approval (no Accounts review)
- Employee Advance Approval
- Purchase Invoice → Submit goes straight to Approved (PO chain still enforced)
- Supplier Payment Entry may reference Approved PO (advance) or Approved PI

## 4. Hubs / Desk

After migrate, confirm workspaces renamed:

- **My Work** (was Quick Links) — Attendance Request label (not WFH)
- **My Expenses** (was Accounts) — Expense Claim, Advance, PO, PI; no Payment Entry shortcut for staff
- Desk icons: How to Spend, My Approval, Budget Health

## 5. Wiki

Requires the **wiki** app on the site. After migrate, open:

- `/help/accounts/how-to-spend`
- `/help/accounts/tally-to-erpnext`
- `/help/hr/home`

Edit in Desk → **Wiki Document**. If pages already existed, paste updated content from `wiki_setup.py` once.

## 6. Smoke test

1. Small Expense Claim → Pending Approver = reports_to manager → Approve (primary).
2. Amount above manager limit → Escalate or Reject only (no Approve).
3. EC above vendor threshold without override reason → blocked on submit path.
4. Second Employee Advance while first residual >10% → blocked; residual ≤10% → allowed with warning.
5. Supplier Payment Entry against Approved PO → allowed; against Draft PO → blocked.
6. Cash Payment Entry above limit → blocked.
7. Accounts creates Payment Entry only after Approved (PI or PO as applicable).
