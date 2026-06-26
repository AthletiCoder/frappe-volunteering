# Sevamrita ERP — Volunteering App

**Live site:** [https://erp.sevamrita.org](https://erp.sevamrita.org)  
**Branch:** `accounts` (accounting controls + merged attendance/ratings from `main`)  
**Last updated:** 13 June 2026

This document serves two purposes:

1. **Employee guide** — how to use features (with links)
2. **Development plan** — what is done, planned, and notes for the team

---

## Part 1 — Employee user guide

> **Tip:** Bookmark [https://erp.sevamrita.org/app](https://erp.sevamrita.org/app) as your home page. Use the search bar (Ctrl/Cmd + K) to jump to any document type.

### Departments in the system

Procurement · Operations · Admin · HR · Media · Accounts · Donor Relations

Each department has a **Department Head** (user login on the Department master) who approves low-value expense claims for staff in that department. ✅ *(Sprint 1 — live after migrate)*

---

### A. Accounting & payments

#### A1. Purchase Order (vendor commitment)

**What it is:** Formal approval to buy goods/services from a vendor against a project.

**When to use:** Before placing an order (preferred). Post-facto PO will be supported later with extra checks.

**URL:** [Purchase Order list](https://erp.sevamrita.org/app/purchase-order) · [New Purchase Order](https://erp.sevamrita.org/app/purchase-order/new-purchase-order-1)

**Steps:**

1. Create PO → select **Supplier**, **Project** (required), items and amounts (tax-inclusive).
2. **Cost Center** fills automatically from the project — do not change it.
3. **Submit** → status moves to **Pending** approval (tier-specific pending state).
4. Approver acts based on amount:
   - **≤ ₹2,000** — Accounts Manager *(Pending Accounts Review)*
   - **₹2,001 – ₹10,000** — NGO Board Member
   - **> ₹10,000** — NGO Board Chairperson
5. When **Approved**, PO is submitted and ready for invoicing.

**Rules:** You cannot approve your own request. Department Heads and Board Members who create a PO are routed to the next higher tier automatically. Board Chairperson cannot create POs. ✅

---

#### A2. Purchase Invoice (vendor bill)

**What it is:** Records the vendor’s invoice against an approved PO.

**URL:** [Purchase Invoice list](https://erp.sevamrita.org/app/purchase-invoice) · [New Purchase Invoice](https://erp.sevamrita.org/app/purchase-invoice/new-purchase-invoice-1)

**Steps:**

1. Create PI → select **Supplier** and **Project**.
2. **Every line must link to an approved, submitted Purchase Order.**
3. Submit → **Pending** → **Accounts Manager** approves.
4. After approval, Accounts creates a **Payment Entry** (one payment per invoice).

**Preferred flow:** PO approved first → goods/services received → invoice → payment.

---

#### A3. Expense Claim (staff reimbursement)

**What it is:** Claim money spent on behalf of the organisation (travel, materials, etc.).

**URL:** [Expense Claim list](https://erp.sevamrita.org/app/expense-claim) · [New Expense Claim](https://erp.sevamrita.org/app/expense-claim/new-expense-claim-1)

**Steps:**

1. Create claim → select **Employee**, **Project** (required), expense lines (tax-inclusive).
2. **Attach receipt(s)** for every expense — mandatory.
3. Submit → approval by tier:
   - **≤ ₹2,000** — Department Head *(auto-assigned from your department)*
   - **₹2,001 – ₹10,000** — NGO Board Member
   - **> ₹10,000** — NGO Board Chairperson
4. **Escalate** to a higher approver anytime if unsure — a reason is required. ✅
5. After **Approved**, Accounts reimburses via **Payment Entry** within one week.

**Rejected claims** stay in **Rejected** status. Edit if needed and use **Re-submit**.

**Settings:** [Volunteering Accounting Settings](https://erp.sevamrita.org/app/volunteering-accounting-settings/Volunteering%20Accounting%20Settings) — tier limits (default ₹2,000 / ₹10,000), post-facto PO defaults.

---

#### A4. Payment Entry (bank payment)

**What it is:** Actual bank payment to a supplier or employee reimbursement.

**URL:** [Payment Entry list](https://erp.sevamrita.org/app/payment-entry) · [New Payment Entry](https://erp.sevamrita.org/app/payment-entry/new-payment-entry-1)

**Who uses it:** Accounts team (Accounts User prepares, Accounts Manager submits — *workflow planned when team grows*).

**Rules (enforced today):**

- Can only pay **Approved** Purchase Invoices or Expense Claims.
- **Supplier** payments → Purchase Invoice references only.
- **Employee** payments → Expense Claim references only.
- One payment per invoice.

---

#### A5. Projects & cost centers

**What it is:** Every spend must be tied to a **Project**, which maps to a **Cost Center** for accounts.

**URL:** [Project list](https://erp.sevamrita.org/app/project) · [Cost Center list](https://erp.sevamrita.org/app/cost-center)

**Who creates projects:** Coordinators. Ensure each project has a **Cost Center** set before any PO, PI, or Expense Claim is raised.

**Fund type (Domestic / FCRA):** Will be tagged on projects for future bank segregation *(planned — Sprint 6)*.

---

#### A6. Budgets ✅

Per-project and per-department budget limits with utilisation dashboard. Soft warnings when a department exceeds its allocated budget on Expense Claims, Purchase Orders, or Purchase Invoices.

**URL:** [Budget Health](https://erp.sevamrita.org/app/project-budget-health)

**Steps:**

1. Open a **Project** → set **Department Budgets** (department + allocated amount).
2. When raising EC / PO / PI, **Department** auto-fills from the employee or document owner.
3. If consumed + this document exceeds allocation, an orange **Budget Exceeded** warning appears (save is not blocked).
4. Toggle warnings in [Volunteering Accounting Settings](https://erp.sevamrita.org/app/volunteering-accounting-settings/Volunteering%20Accounting%20Settings) → **Enable Budget Warnings**.

---

#### A7. Donations & 80G receipts *(planned)*

Donor tracking and tax exemption certificates inside ERPNext.

**URL (planned):** [Donation list](https://erp.sevamrita.org/app/donation)

---

### B. Volunteers & events

#### B1. Volunteers

**URL:** [Volunteer list](https://erp.sevamrita.org/app/volunteer) · [New Volunteer](https://erp.sevamrita.org/app/volunteer/new-volunteer-1)

Store volunteer details. Mobile numbers are normalised automatically (e.g. `+91-9876543210`).

---

#### B2. NGO Events

**URL:** [NGO Event list](https://erp.sevamrita.org/app/ngo-event) · [New NGO Event](https://erp.sevamrita.org/app/ngo-event/new-ngo-event-1)

Lifecycle: Planned → Registrations → Shipping → Followup → Closed.

Link each event to a **Project** for hours-per-kit and rating calculations.

---

#### B3. Participation (event registration & follow-up)

**URL:** [Participation list](https://erp.sevamrita.org/app/participation) · Public registration via published **Web Forms**

Phone number can auto-link or create a Volunteer. Relationship Managers rate volunteers after logging is complete.

---

#### B4. Event participation report

**URL:** [Generic Event Participation Report](https://erp.sevamrita.org/app/query-report/Generic%20Event%20Participation%20Report)

Dynamic columns from event-specific questions.

---

### C. HR, leave & attendance

#### C1. Daily Work Log

**URL:** [Daily Work Log list](https://erp.sevamrita.org/app/daily-work-log) · [New Daily Work Log](https://erp.sevamrita.org/app/daily-work-log/new-daily-work-log-1)

Staff log daily work hours. Submitted logs feed into automatic attendance marking.

**Settings:** [Daily Work Log Settings](https://erp.sevamrita.org/app/daily-work-log-settings/Daily%20Work%20Log%20Settings)

---

#### C2. Leave Application

**URL:** [Leave Application list](https://erp.sevamrita.org/app/leave-application) · [New Leave Application](https://erp.sevamrita.org/app/leave-application/new-leave-application-1)

Categories: Planned, Emergency, Sick — with validation rules (backdating limits, justification for short-notice planned leave, etc.).

**Settings:** [Leave Policy Settings](https://erp.sevamrita.org/app/leave-policy-settings/Leave%20Policy%20Settings)

---

#### C3. Attendance

Attendance is processed daily from work logs, approved leave, and work-from-home requests. View in [Attendance list](https://erp.sevamrita.org/app/attendance).

**Report:** [Missing Daily Logs Report](https://erp.sevamrita.org/app/query-report/Missing%20Daily%20Logs%20Report)

---

### D. Approvals — quick reference

| Document | Tier 1 (≤ ₹2,000) | Tier 2 (₹2,001 – 10,000) | Tier 3 (> ₹10,000) |
|----------|-------------------|--------------------------|---------------------|
| Purchase Order | Accounts Manager | NGO Board Member | NGO Board Chairperson |
| Expense Claim | Department Head | NGO Board Member | NGO Board Chairperson |
| Purchase Invoice | Accounts Manager only (no amount tiers) | — | — |
| Payment Entry | Accounts team *(no workflow yet)* | — | — |

**Escalation:** Any approver can send a document to the next tier with a mandatory reason. Email alerts go to pending approvers. ✅

**Self-approval:** Not allowed.

---

### E. Dashboards *(planned)*

| Dashboard | Purpose | URL |
|-----------|---------|-----|
| Pending My Approval | One list for your workflow actions | `/app/pending-my-approval` |
| Pending Reimbursements | Approved expense claims awaiting payment | `/app/pending-reimburse` |
| Pending Vendor Payments | Approved invoices awaiting payment | `/app/pending-vendor-pay` |
| Project Budget Health | Budget vs spent by project and department | `/app/project-budget-health` *(planned)* |

---

## Part 2 — Development plan

### Status legend

| Status | Meaning |
|--------|---------|
| ✅ Done | Live on `accounts` branch (may need migrate/fixtures sync on site) |
| 🚧 In progress | Actively being built |
| 📋 Planned | Agreed scope, not started |
| ⏸ Deferred | Agreed to postpone |

---

### Policy decisions (locked)

| Decision | Value | Date |
|----------|-------|------|
| Entity | One Section 8 company | Jun 2026 |
| Fund tracking | Projects → Cost Centers | Jun 2026 |
| Approval thresholds | ₹2,000 / ₹10,000 (tax-inclusive) | Jun 2026 |
| Departments | Procurement, Operations, Admin, HR, Media, Accounts, Donor Relations | Jun 2026 |
| Department Head | User login required on Department master | Jun 2026 |
| Self-approval | Never allowed | Jun 2026 |
| Receipts on expense claims | Mandatory (all amounts) | Jun 2026 |
| Rejected documents | Stay in Rejected; re-submit to retry | Jun 2026 |
| Post-facto PO defaults | 7-day window, max 2 per employee/month | Jun 2026 |
| Payment model | 1 payment per invoice; accounts team executes | Jun 2026 |
| GST registration | Not yet — defer implementation | Jun 2026 |
| Threshold settings | Configurable via Accounting Settings page | Jun 2026 |

---

### Feature tracker

#### Accounting — core controls

| Feature | Status | Comments |
|---------|--------|----------|
| Project required on PO / PI / Expense Claim | ✅ Done | Property setters + validation |
| Auto cost center from project | ✅ Done | `accounting_controls.py` |
| Block save if project has no cost center | ✅ Done | |
| PO amount-tier approval workflow | ✅ Done | Accounts Mgr / Board Member / Chair |
| Expense Claim amount-tier approval workflow | ✅ Done | Tier 1 → Department Head; tier 2/3 → Board Member / Chair |
| Purchase Invoice approval (Accounts Manager) | ✅ Done | No board tiers on PI |
| Every PI line must link to approved PO | ✅ Done | Stricter than original server script |
| Payment only against approved PI / EC | ✅ Done | `validate_payment_entry` |
| Employee payments → EC only; Supplier → PI only | ✅ Done | |
| Server Script → Python migration | ✅ Done | Patch disables legacy scripts |
| Merge `main` into `accounts` | ✅ Done | Commit `88540ce`, 46 tests passing |

#### Accounting — Sprint 1 (approval routing & escalation) ✅ Complete

| Feature | Status | Comments |
|---------|--------|----------|
| `department_head` field on Department (User link) | ✅ Done | Custom field + `ensure_departments()` seeds 7 departments |
| Auto-assign expense approver to department head | ✅ Done | `assign_expense_approver()` on EC save |
| Tier 1 EC approver = Department Head | ✅ Done | Workflow: Pending Department Head; condition `expense_approver` |
| Tier 1 PO approver = Accounts Manager | ✅ Done | Workflow: Pending Accounts Review |
| Escalate workflow action (all tiers) | ✅ Done | Mandatory `escalation_reason`; Escalate → next tier |
| Requester-based routing (no self-approval) | ✅ Done | Dept head / board member requesters → min tier 2 |
| Block Board Chair from creating PO/EC | ✅ Done | Validation in `get_requester_minimum_level()` |
| Volunteering Accounting Settings (thresholds) | ✅ Done | Single DocType; tier_1=2000, tier_2=10000 |
| Email notification on pending approval | ✅ Done | `notify_pending_approvers()` on workflow state change |
| `approval_level` routing on Submit/Re-submit | ✅ Done | Conditional workflow transitions |
| Sync `approval_status` on approve (permlevel fix) | ✅ Done | `before_submit` hook for EC |
| Cost center on EC expense lines from project | ✅ Done | Required for GL on approve |
| Unit tests: routing, escalation, tiers | ✅ Done | 7 tests in `test_approval_routing.py` |
| Integration tests: EC approval scenarios | ✅ Done | 10 tests in `test_accounting_approval.py` |

**Sprint 1 exit criteria met:** 63 automated tests green (11 unit + 52 integration). Site migrate syncs workflows, custom fields, departments, and settings.

**Not in Sprint 1 scope (deferred):** PO integration tests, board-member-as-requester PO happy path, Frappe Notification DocType (using `frappe.sendmail` instead).

#### Accounting — Sprint 2 (UX & visibility) — **Complete**

| Feature | Status | Comments |
|---------|--------|----------|
| Pending My Approval desk page | ✅ Done | `/app/pending-my-approval`; scans pending workflow states + open Workflow Actions |
| Pending Reimbursements dashboard | ✅ Done | `/app/pending-reimburse`; approved unpaid ECs |
| Pending Vendor Payments dashboard | ✅ Done | `/app/pending-vendor-pay`; PIs with outstanding balance |
| Prominent workflow actions on forms | ✅ Done | `accounting_workflow.js` — Approve / Reject / Escalate on EC & PO |
| Department-based list permissions | ✅ Done | `expense_claim_permissions.py` hooks on EC list/read |
| Weekly pending approvals email/report | ✅ Done | Weekly scheduler + ageing in email body |
| PO integration tests (tier routing) | ✅ Done | 6 tests in `test_accounting_po_approval.py` (scenarios 8–9) |
| Dashboard integration tests | ✅ Done | 10 tests in `test_accounting_dashboard.py` |

#### Accounting — Sprint 3 (budgets) — **Complete**

| Feature | Status | Comments |
|---------|--------|----------|
| Project department budget child table | ✅ Done | `Project Department Budget` on Project |
| Budget warn on exceed (soft) | ✅ Done | `budget_service.py`; toggle via Accounting Settings |
| Department field on PO / EC / PI | ✅ Done | Auto from employee (EC) or owner (PO/PI) |
| Project Budget Health dashboard | ✅ Done | `/app/project-budget-health`; sidebar under **Budgets** |
| Budget tests | ✅ Done | 3 unit + 4 integration in `test_budget_service.py`, `test_accounting_budget.py` |

#### Accounting — Sprint 4 (post-facto PO)

| Feature | Status | Comments |
|---------|--------|----------|
| Post-facto PO flag and guardrails | 📋 Planned | 7-day window, 2/month cap |
| Mandatory vendor invoice attachment | 📋 Planned | |
| Minimum Board Member approval for post-facto | 📋 Planned | |
| Accounts “post-facto verified” on PI | 📋 Planned | |
| Post-facto audit report | 📋 Planned | |
| Tests | 📋 Planned | |

#### Accounting — Sprint 5 (donations)

| Feature | Status | Comments |
|---------|--------|----------|
| Donor → Donation → Project linkage | 📋 Planned | ERPNext standard doctypes |
| 80G certificate template | 📋 Planned | When tax config ready |

#### Accounting — Sprint 6 (FCRA)

| Feature | Status | Comments |
|---------|--------|----------|
| Project `fund_type` (Domestic / FCRA) | 📋 Planned | |
| Payment warning / block by fund type | 📋 Planned | Hard block when 2nd bank added |

#### Accounting — Sprint 7 (payment workflow)

| Feature | Status | Comments |
|---------|--------|----------|
| Payment Entry maker-checker | 📋 Planned | Accounts User drafts, Manager submits |
| Payment Entry approval workflow | 📋 Planned | Only if team grows beyond 2 people |

#### Accounting — Sprint 8 (GST / TDS)

| Feature | Status | Comments |
|---------|--------|----------|
| GST registration & India Compliance setup | ⏸ Deferred | Org not registered yet |
| TDS on vendor payments | ⏸ Deferred | Use ERPNext native when liable |
| Design note: tax-inclusive amounts throughout | ✅ Done | Policy locked |

#### Accounting — hygiene

| Feature | Status | Comments |
|---------|--------|----------|
| Remove site-specific data from `workflow_action.json` fixture | 📋 Planned | Causes noise on fresh installs |
| Board / Accounts role fixtures or setup doc | 📋 Planned | Roles assumed from ERPNext/HRMS |
| Accounting section in README | 📋 Planned | Link to this document |
| Full scenario test matrix (23+ cases) | 📋 Planned | Grow each sprint |

---

### Volunteers, events & HR (from `main` merge)

| Feature | Status | Comments |
|---------|--------|----------|
| Volunteer mobile normalisation | ✅ Done | |
| Participation rating & rollup | ✅ Done | RM-only rating |
| Daily Work Log + attendance service | ✅ Done | Scheduled daily job |
| Leave policy validation | ✅ Done | Planned / Emergency / Sick |
| Missing Daily Logs report | ✅ Done | |
| 46 automated tests | ✅ Done | Pre-Sprint 1 baseline |
| 63 automated tests | ✅ Done | +17 accounting tests (Sprint 1) |
| 73 automated tests | ✅ Done | +10 dashboard tests (Sprint 2) |
| 86 automated tests | ✅ Done | +6 PO + 7 budget tests (Sprint 2–3) |

---

### Sprint goals review

#### Sprint 1 — Approval routing & escalation ✅ **Complete**

**Goal:** Make amount-based approval tiers work end-to-end for Expense Claims (and PO workflows), with department heads, escalation, and configurable thresholds.

**Delivered:**

- **Settings:** Volunteering Accounting Settings (tier limits, post-facto defaults for later sprints).
- **Master data:** `department_head` on Department; seven departments seeded on migrate.
- **Routing logic:** `approval_routing.py` — amount tiers, requester minimum tier, pending state mapping, receipt validation, escalation reason, approver emails.
- **Workflows:** Updated EC/PO fixtures — tier-specific pending states, Escalate action, conditional Submit/Re-submit by `approval_level`.
- **Hooks:** EC/PO `before_save` + `on_update`; EC `before_submit` for `approval_status` and cost center on lines.
- **Tests:** 7 unit + 10 integration tests covering EC scenarios 1–7 and 10.

**Ops checklist (one-time on site):**

1. `bench --site sevamrita.local migrate` — syncs custom fields, workflows, departments, settings.
2. Set **Department Head** on each Department master (Operations, HR, etc.).
3. Assign users to roles: NGO Department Head, NGO Board Member, NGO Board Chairperson.
4. Configure outgoing Email Account for production approval alerts (optional in dev; tests mock email).

---

#### Sprint 2 — UX & visibility ✅ **Complete**

**Goal:** Approvers and Accounts staff can see what needs action without hunting through lists.

**Delivered:**

1. **Pending My Approval** — desk page with amount, project, age, and available actions.
2. **Pending Reimbursements** — approved expense claims not yet paid.
3. **Pending Vendor Payments** — purchase invoices with outstanding balance.
4. **Department scoping** — dept heads see only their department's expense claims in lists.
5. **Weekly nudge** — scheduled email for stale pending approvals (links to dashboard).
6. **Form UX** — Approve / Reject / Escalate buttons on EC & PO forms when in pending workflow states.
7. **PO integration tests** — tier routing and accounts-manager approval (scenarios 8–9).
8. **Tests** — 10 dashboard + 6 PO integration tests.

**Success criteria:** Accounts and approvers can answer “what do I need to act on today?” from the desk — **met**.

---

#### Sprint 3 — Budgets ✅ **Complete**

**Goal:** Track per-project department budgets and surface utilisation before overspend.

**Delivered:**

1. **Project Department Budget** child table on Project (department + allocated amount).
2. **Department** field on EC, PO, PI — auto-assigned from employee or document owner.
3. **Soft budget warnings** on save when consumed + document exceeds allocation (`enable_budget_warnings` in Accounting Settings).
4. **Budget Health** desk page — allocated / consumed / remaining / utilisation % by project and department.
5. **Tests** — 3 unit + 4 integration tests for budget service and end-to-end EC consumption.

**Success criteria:** Coordinators and Accounts can see budget health at a glance; users get warned on overspend without blocking saves — **met**.

---

#### Sprints 4–8 (unchanged priority)

| Sprint | Theme | Key outcome |
|--------|-------|-------------|
| 3 | Budgets | ✅ Complete | Project/dept budget limits + Budget Health dashboard |
| 4 | Post-facto PO | 7-day / 2-per-month guardrails + board minimum approval |
| 5 | Donations | Donor → Donation → Project + 80G template |
| 6 | FCRA | `fund_type` on Project; payment warnings by fund |
| 7 | Payment workflow | Maker-checker on Payment Entry (when team grows) |
| 8 | GST / TDS | Deferred until registration |

---

### Sprint priority order (agreed)

1. GST/TDS design *(deferred implementation)*
2. Board escalation on large PI *(already N/A — accounts only by design)*
3. Donation accounting
4. Post-facto PO
5. Budget enforcement
6. Test cases & documentation
7. Payment Entry workflow

*Note: Execution order follows Sprint 1 → 8 above; priority list reflects business urgency for planning.*

---

### Test scenario matrix

| # | Scenario | Status |
|---|----------|--------|
| 1 | EC ₹1,500 → Dept Head approves | ✅ Done | `test_department_head_can_approve_low_value_claim` |
| 2 | EC ₹1,500, requester is Dept Head → Board Member | ✅ Done | `test_dept_head_requester_routes_to_board_member` |
| 3 | EC ₹5,000 → Board Member approves | ✅ Done | `test_mid_value_claim_routes_to_board_member` |
| 4 | EC ₹15,000 → Board Chair approves | ✅ Done | `test_high_value_claim_routes_to_board_chair` |
| 5 | EC escalate Dept Head → Board Member | ✅ Done | `test_escalation_moves_to_board_member` |
| 6 | EC rejected → stays Rejected → re-submit | ✅ Done | `test_rejected_claim_stays_rejected_until_resubmit` |
| 7 | EC without receipt → blocked | ✅ Done | `test_claim_without_receipt_cannot_submit` |
| 8 | PO tier rules mirror EC | ✅ Done | `test_accounting_po_approval.py` |
| 9 | Board Member PO → another Board Member approves | ✅ Done | `test_board_member_requester_routes_to_board_member` |
| 10 | Board Chair cannot create PO/EC | ✅ Done | EC tested; PO validation same hook |
| 11 | PI every line needs approved PO | ✅ Done | Covered by `accounting_controls` |
| 12 | Post-facto PO within 7 days + invoice → allowed | 📋 Planned |
| 13 | Post-facto without invoice → blocked | 📋 Planned |
| 14 | Post-facto 3rd in month → blocked | 📋 Planned |
| 15 | PI against unapproved PO → blocked | ✅ Done | |
| 16 | Payment against unapproved PI → blocked | ✅ Done | |
| 17 | Employee payment with PI ref → blocked | ✅ Done | |
| 18 | Supplier payment with EC ref → blocked | ✅ Done | |
| 19 | Project without cost center → blocked | ✅ Done | |
| 20 | Budget soft warn / hard block | ✅ Done | Soft warn on save; hard block deferred |
| 21 | Dept Head sees only own department docs | ✅ Done | EC list/read scoped in Sprint 2 |
| 22 | Coordinator sees all | 📋 Planned |
| 23 | FCRA project payment warning | 📋 Planned |

---

### Changelog

| Date | Change | Author |
|------|--------|--------|
| 12 Jun 2026 | Merged `origin/main` into `accounts`; resolved 5 conflict files; 46 tests green | Dev team |
| 12 Jun 2026 | Requirements interview completed; agile sprint plan agreed | Management |
| 12 Jun 2026 | Created `DEVELOPMENT_PLAN.md` (this document) | Dev team |
| 13 Jun 2026 | **Sprint 1 complete:** approval routing, escalation, Accounting Settings, EC workflows, 63 tests green | Dev team |
| 13 Jun 2026 | **Sprint 2 (mostly):** accounting dashboards, EC dept permissions, weekly reminder, 73 tests green | Dev team |
| 13 Jun 2026 | **Sprint 2 complete:** workflow form UX, PO integration tests | Dev team |
| 13 Jun 2026 | **Sprint 3 complete:** dept budgets, soft warnings, Budget Health page, 86 tests green | Dev team |

---

### How to update this document

1. When a feature ships, change **Status** to ✅ Done and add a **Changelog** row.
2. When scope changes, update **Comments** and **Policy decisions**.
3. Keep employee URLs in sync if routes or desk pages are renamed.
4. After each sprint, tick off test matrix rows.

---

### Related files

| File | Purpose |
|------|---------|
| `volunteering/volunteering/accounting_controls.py` | Core validation hooks (project, cost center, payment) |
| `volunteering/volunteering/approval_routing.py` | Tier routing, escalation, receipts, notifications |
| `volunteering/volunteering/accounting_setup.py` | after_migrate: fields, roles, departments, workflows |
| `volunteering/volunteering/budget_service.py` | Budget allocation, consumption, soft warnings, Budget Health API |
| `volunteering/volunteering/accounting_dashboard/` | Pending approvals/payments pages, sidebar setup, weekly reminder |
| `volunteering/public/js/accounting_workflow.js` | Prominent Approve/Reject/Escalate on EC & PO forms |
| `volunteering/volunteering/test_accounting_po_approval.py` | Integration tests for PO tier routing |
| `volunteering/volunteering/test_budget_service.py` | Unit tests for budget helpers |
| `volunteering/volunteering/test_accounting_budget.py` | Integration tests for budget model |
| `volunteering/volunteering/test_approval_routing.py` | Unit tests for routing logic |
| `volunteering/volunteering/test_accounting_approval.py` | Integration tests for EC approval |
| `volunteering/doctype/volunteering_accounting_settings/` | Configurable tier thresholds |
| `volunteering/hooks.py` | Doc events, fixtures, scheduler |
| `volunteering/fixtures/workflow.json` | EC/PO/PI approval workflows |
| `volunteering/fixtures/workflow_state.json` | Pending tier states |
| `volunteering/fixtures/property_setter.json` | Required project, read-only cost center |
| `README.md` | Volunteer, ratings, leave, attendance guide |
