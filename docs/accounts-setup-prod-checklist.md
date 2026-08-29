# Accounts — prod setup checklist

One-page mirror of dev/E2E. Run **`bench --site YOUR_SITE migrate`** + **`clear-cache`** after deploying volunteering app updates.

Related: [fund_disbursement_ops_checklist.md](fund_disbursement_ops_checklist.md) · [cashfree_accounting_checklist.md](cashfree_accounting_checklist.md)

---

## 1. Deploy (required — fixes most permission / form issues)

| On migrate | Why it matters |
|------------|----------------|
| **Employee Advances** account + Company default + Employee backfill | Advance GL; not Debtors |
| **EC payable repair** if pointing at Cash | EC submit / approval crashes |
| **Employee role read/select:** Project, Currency, Cost Center, Expense Claim Type | EC project tag; EA currency; no manual Role Permission Manager |
| **Hide GL fields** + `ignore_user_permissions` on EC payable / advance link fields | Stops “Insufficient Permission for Account” for staff |
| **EA approval tab** after amount fields (not after employee) | Purpose & amount stay on Details |
| Workflows, grades, limits, departments | Approvals |

**Do not** manually add Employee→Account unless migrate failed — app sets GL server-side.

---

## 2. COA & Company (manual)

| Item | Company field / use |
|------|---------------------|
| **Creditors** | `default_payable_account`, `default_expense_claim_payable_account` (must be Payable) |
| **Employee Advances** | `default_employee_advance_account` (migrate creates) |
| **Operating bank** | `default_bank_account` |
| **Cash** | `default_cash_account` (≤ ₹2k cash PE limit) |
| **Debtors** | `default_receivable_account` (donations) |
| **Expense heads** | Map on each **Expense Claim Type** → Accounts → default account **per company** |
| **Cashfree Clearing** + **Donation Income** | Donations only — see Cashfree checklist |

---

## 3. Modes of payment (manual)

Bank / NEFT / UPI → bank · Cash → cash · Cashfree → clearing (if donations).

---

## 4. Settings to review after migrate

**Volunteering Accounting Settings:** vendor threshold ₹5k, cash limit ₹2k, budget hard-block 25%, max unsettled advances 1.

**Approval and Advance Limits:** per-grade approve / self-advance caps.

**Projects:** Type, Cost Center, department budgets, Budget Status = Active.

**Employees:** Grade, Reports To, Department.

---

## 5. Prod smoke (manual, 10 min)

- [ ] New Employee Advance → save → submit → manager approve → Accounts pays (PE)
- [ ] New Expense Claim → **project required** → receipts → submit → approve (no Account permission error)
- [ ] EC from paid advance (“Expense Claim” / Get Advances) opens without Account error
- [ ] PO → approve → PI → supplier PE
- [ ] Home todo links use `/desk/employee-advance/...` (hyphens), not underscores

---

## 6. Do not copy from E2E site

`_E2E Test Project`, `_Test Accounting Supplier`, `_Test Accounting Expense`, seeded personas — dev only.

---

## 7. Issue → config mapping (from dev feedback)

| Symptom | Prod fix |
|---------|----------|
| Account permission on EA / EC | §1 migrate (hide + ignore_user_permissions + server GL) |
| Accounts cannot pick another employee on EA | §1 migrate (`employee` link ignores user permissions) |
| Project permission on EC | §1 migrate (Employee→Project) |
| Currency permission on EA | §1 migrate (Employee→Currency) |
| Purpose/amount on wrong tab | §1 migrate (tab placement) |
| EC from advance fails | §1 + Expense Claim Type default account |
| Todo link 404 `employee_advance` | App fix (hyphen routes) — redeploy SPA + migrate |
| “Set default account for Expense Claim Type” | §2 Expense Claim Type accounts table |

---

*Code: `accounting_setup.py`, `employee_spending_permissions.py`, `accounting_controls.py`*
