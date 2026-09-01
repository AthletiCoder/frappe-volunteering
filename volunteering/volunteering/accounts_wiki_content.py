# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""In-app Wiki content for Accounts (spending, Tally map, configuration).

Written in simple English so it is easy to read for everyone.
"""

HOW_TO_SPEND = """# How to spend

This page shows the right way to spend money. Pick **one** path for each expense.

Start here:

- [Home](/volunteering/home) — leave, work, advances, and claims

## The three ways to spend

| Way | When to use it |
|-----|----------------|
| **1. Pay the vendor** (best) | The organisation pays the shop or supplier directly. |
| **2. Take an advance** | You need money *before* you buy (travel, events, local shopping). You return the bills later. |
| **3. Claim money back** | You already paid with your own money and want it back. Use only when the first two were not possible. |

## 1. Pay the vendor (best way)

For anything above the **Vendor Payment Threshold** (default ₹5,000), do not pay from your own money. Create a [Purchase Order](/app/purchase-order/new) so the organisation pays the vendor.

Who does each step:

| Step | Who does it |
|------|-------------|
| Purchase Order (the plan to buy) | Accounts or the buying team |
| Purchase Invoice (the vendor bill) | Staff **or** Accounts — made from the approved order, with the bill attached |
| Payment Entry (the actual payment) | **Accounts only** |

### If you must pay the vendor before the bill arrives

1. First get a Purchase Order that is **approved and submitted**.
2. Accounts pays the vendor against that order (this is an advance to the vendor).
3. When the bill arrives, staff or Accounts make the Purchase Invoice from the order and link the advance.

If you really must use your own money above the threshold, you must write a short reason in **Vendor Payment Override Reason**.

## 2. Take an advance

An advance is money the organisation gives you **before** you buy something.

- You can take an advance **only for yourself**. (Accounts or HR can do it for others.)
- Do **not** tag an advance to a project. It is cash in your hands, not program spend yet.
- When you settle, make an [Expense Claim](/app/expense-claim/new), **choose the Project** the bills belong to, and link the advance. Budget Health checks that project.
- You cannot take a new advance while an old one still has a large **leftover** (more than 10% of what you were paid).
- If the leftover is small (10% or less), you may take another advance. But you must still return or claim the leftover — it is never ignored.
- Check the status of your advances on the [Advance Portal](/volunteering/advances).
- To close an advance, make an [Expense Claim](/app/expense-claim/new) and link it to the advance.

> **Note:** The **Get Advances** button only shows advances that are **approved and already paid** to you.

Open: [New Employee Advance](/app/employee-advance/new)

## 3. Claim money back (reimbursement)

A claim means: *"I already paid with my own money. Please pay me back."*

1. You pay the vendor or expense yourself (or settle an advance).
2. Make an [Expense Claim](/app/expense-claim/new), **set the Project**, and attach the receipts.
3. Your manager or Accounts approves it (live department budget on that project is checked on Approve).
4. Accounts pays you. The claim is then marked **Paid**.

There is no separate "already paid" checkbox. Making the claim *is* how you say you already paid.

Your organisation may set a **Monthly Reimbursement Cap** (a limit per person per month). If it is 0, there is no limit.

## A vendor bill paid outside the system

If a [Purchase Invoice](/app/purchase-invoice) was paid in cash or by another way, Accounts can click **Mark Paid (outside system)** on that bill.

## How approvals work

Approvals follow two things: your **manager chain** (Reports To) and your **grade** (seniority band on your Employee record). Designation is only your job title — it does not decide amounts.

- If your grade limit covers the amount: you can **Approve** or **Reject**.
- If the amount is above your limit: you can **Reject** or **Escalate** (send it to a higher person). You cannot approve it.
- You can never approve your own request.

## What Accounts does

Accounts does **not** approve daily spending. The operations team approves. After approval, Accounts makes the [Payment Entry](/app/payment-entry) to pay.

See also: [Accounts: Tally → ERPNext](/help/accounts/tally-to-erpnext) · [Accounts Configuration](/help/accounts/configuration) · [HR Home](/help/hr/home)
"""

TALLY_GUIDE = """# Accounts: Tally → ERPNext

This page is for Accounts users who know **Tally**. ERPNext keeps the same voucher names (Payment Entry, Journal Entry) so your CA and auditors will recognise them.

> If you still enter the same payment in Tally, do **not** enter it twice. Use ERPNext as the main record unless leadership tells you otherwise.

## The main difference

| In Tally | In ERPNext |
|----------|------------|
| You enter a voucher, and the books update | Staff **request** → manager **approves** → Accounts **pays** |
| Alter or Delete an entry | **Cancel** or **Amend** (the history is kept) |
| Day Book | [General Ledger](/app/query-report/General%20Ledger) and the list of vouchers |

Your main job here: **check the books and make payments**. Not approve daily spending.

## The three spend paths

| Path | Steps | Same as in Tally |
|------|-------|------------------|
| Pay vendor on credit | Order → Bill → Payment | Purchase + Payment |
| Pay vendor before bill | Approved Order → Payment on order → Bill later | Advance to a creditor |
| Staff advance / own money | Advance or Claim → Payment to the person | Payment to staff |

Every vendor bill must link to an **approved, submitted** order. Staff or Accounts can make the bill, but only Accounts pays.

## Voucher map

| Tally | ERPNext | When |
|-------|---------|------|
| Payment voucher | [Payment Entry](/app/payment-entry) (Pay) | Pay a vendor or a staff member after approval |
| Receipt voucher | Payment Entry (Receive) | Donations and other money received |
| Journal | [Journal Entry](/app/journal-entry) | Adjustments and clearing entries |
| Purchase | [Purchase Invoice](/app/purchase-invoice) | A vendor bill (must link an approved order) |
| — | [Purchase Order](/app/purchase-order) | A plan to buy, before the bill |
| — | [Expense Claim](/app/expense-claim) | Pay a staff member back (only when needed) |
| — | [Employee Advance](/app/employee-advance) | Give a staff member money before they buy |

## Master map

| Tally | ERPNext |
|-------|---------|
| Ledger / Group | [Chart of Accounts](/app/chart-of-accounts) |
| Sundry Creditor | [Supplier](/app/supplier) |
| Sundry Debtor | [Customer](/app/customer) |
| Cost Centre | [Cost Center](/app/cost-center) |
| Job / cost category | [Project](/app/project) |
| Cash / Bank ledger | Account + [Mode of Payment](/app/mode-of-payment) |

## Daily work

1. [Home](/volunteering/home) — bills to pay, claims to pay back, advances
2. [Advances with leftover](/app/query-report/Employee%20Advances%20with%20Residual)
3. [Bank Reconciliation](/app/bank-reconciliation-tool)
4. [Budget Health](/volunteering/budget-health)
5. [General Ledger](/app/query-report/General%20Ledger)

## Donations (Cashfree)

Donations first land in a **Cashfree Clearing** account via an auto **Payment Entry (Receive)**. An income **Journal Entry** (Debtors → Donation Income) is posted at the same time when Auto Create Payment Entry is enabled. When the money reaches your real bank, make a separate Journal Entry: money into Bank, out of Clearing (handle fees as your CA advises).

## What Accounts does not do

Accounts does not approve daily spending. Operations approve. Accounts pays and checks the books.

## Related

- [How to spend](/help/accounts/how-to-spend)
- [Accounts Configuration](/help/accounts/configuration)
- [HR Home](/help/hr/home)
"""

ACCOUNTS_CONFIG = """# Accounts Configuration

This page shows **where** to set spending limits and rules, and **who** can change them. It is for Accounts Managers and System Managers.

## Who can change what

| Setting | Who can change it | Who can only view |
|---------|-------------------|-------------------|
| Approval & Advance Limits | Accounts Manager, System Manager | HR Manager, Employees |
| Accounting Settings | Accounts Manager, System Manager | — |

## 1. Set approval and advance limits (by grade)

Limits are set for each **grade** (seniority band), not for each person. You give each person the right grade on their Employee record, and they get that grade's limits. See [HR Configuration](/help/hr/configuration) for how to set a grade.

**Open the page:** [Home](/volunteering/home) → Setup → **Approval & Advance Limits**, or go to [Approval and Advance Limits](/app/approval-and-advance-limits).

Each grade has two separate limits:

| Column | Meaning |
|--------|---------|
| **Max Approval Authority** | The biggest amount this person can **approve for other people**. |
| **Max Self Advance** | The biggest advance this person can take **for themselves**. |

Anyone on the **Board of Directors** grade can approve **any** amount.

### How to edit

1. Open the page.
2. Change the amounts in the table, or add a row for a grade that is missing.
3. Click **Save**.
4. To go back to the standard values, click **Reset to Defaults**.

### Standard values

| Grade | Can approve for others | Own advance limit |
|-------------|------------------------|-------------------|
| Associate | 0 | 2,000 |
| Manager | 2,000 | 5,000 |
| Vice President | 5,000 | 10,000 |
| President | 10,000 | 15,000 |
| Director | 25,000 | 50,000 |
| CEO | 50,000 | 50,000 |
| Executive Board | 100,000 | 100,000 |
| Board of Directors | Unlimited | — |

## 2. Turn grade approval on or off

Open [Accounting Settings](/app/volunteering-accounting-settings) → **Approval Authority**.

- **On** (normal): approvals use the grade limits above and the manager chain (Reports To).
- **Off**: the system uses simple amount tiers instead. Keep this **on** unless leadership asks otherwise.

## 3. Other spending rules

All of these are on [Accounting Settings](/app/volunteering-accounting-settings).

| Setting | What it does | Default |
|---------|--------------|---------|
| Vendor Payment Threshold | Above this amount, staff should ask the organisation to pay the vendor, not use their own money. | 5,000 |
| Cash Payment Limit | Largest amount allowed to be paid in cash. | 2,000 |
| Monthly Reimbursement Cap | Most a person can claim back in one month (0 = no limit). | 0 |
| Advance Replenish Leftover % | If an advance's leftover is at or below this, the person may take a new advance. | 10% |
| Max Blocking Advances | How many large-leftover advances block a new one. | 1 |

## 4. Budget controls

Also on [Accounting Settings](/app/volunteering-accounting-settings) → **Budget Controls**.

Project **department budgets** are checked on **Expense Claims** and **Purchase Orders** (not on Employee Advances). Purchase Invoices do not double-count a PO.

| Setting | What it does | Default |
|---------|--------------|---------|
| Enable Soft Budget Warnings | Show a warning when spending is near the budget. | On |
| Budget Hard-Block % | Block approval when spending goes over the budget by more than this. | 25% |
| Budget Hard-Block override | Who may approve past the hard limit. | Board of Directors grade |

See project budget status any time on [Budget Health](/volunteering/budget-health).

## Related

- [How to spend](/help/accounts/how-to-spend)
- [Accounts: Tally → ERPNext](/help/accounts/tally-to-erpnext)
- [HR Configuration](/help/hr/configuration)
"""
