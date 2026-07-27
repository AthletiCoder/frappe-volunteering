# Volunteering

An ERPNext app for NGO day-to-day work: volunteer events, staff attendance and leave, and controlled spending (advances, claims, and budgets).

---

## What it covers

### Volunteers and events

- Keep a clean volunteer directory (phone matching avoids duplicates).
- Run campaigns through clear stages: plan → register → ship → follow up → close.
- Public signup form for events (WhatsApp confirmation, kit count, delivery options, referrals).
- Coordinators can update attendance and logistics in a spreadsheet-style table for an event — no need to open every record.
- Relationship Managers rate volunteers after logging (1–5 for communication ease); each volunteer gets a rolling score from their last three rated events.

### My Work (for staff)

One home for self-service and approvals:

- **Self service** — daily work logs, attendance, leave, and regularization requests (with live counts of what’s still open).
- **Awaiting my approval** — leaves and attendance requests from people who report to you (hidden if you have no reportees).

Managers can leave private remarks when reviewing a work log. Approvers can approve or reject leave in one click from the leave form.

### My Expenses (for spend)

One home for personal spend and money waiting on you:

- Your expense claims, advances, and purchase orders — with pending counts.
- Approvals waiting on you (claims, advances, orders).
- Accounts queues: claims ready to reimburse, vendor invoices to pay.
- **Advance Portal** — see each advance’s status, how much is claimed vs still unused, linked bills, and shortcuts to claim or request a new advance.
- **Budget Health** — a clear view of project budget status with health colours and links into the detail.
- **Advances with leftover** — report for chasing unsettled advance balances.

Staff can only raise advances for themselves. Project and bank account details are filled in behind the scenes. Prefer vendor payment for larger spends; reimbursement is for when you already paid out of pocket.

### Approval and advance limits

Accounts (and System Managers) configure how much each **designation** may:

1. **Approve for others** — the largest amount they can clear on someone else’s request.
2. **Hold as a personal advance** — the largest float they can request for themselves.

Board-level roles have unlimited approval authority. Open the page from **My Expenses → Approval & Advance Limits**. HR and Board members can view the limits; only Accounts Managers and System Managers can change them.

Approvals follow the **Reports To** chain on the employee record until someone with enough authority is reached. Managers below the limit can reject or escalate (with a reason), not approve above their level.

### Daily work log summary email

On **Daily Work Log Settings** you can turn on an email summary of everyone’s work logs:

- **Who** — by role (e.g. board), plus optional extra addresses
- **From** — optional sender address (otherwise the system default)
- **How often** — daily, weekly, or monthly

Daily emails show yesterday in detail; weekly/monthly show hours and days logged. Use **Preview Summary** and **Send Summary Now** on the settings page to check the look before going live.

### Help in the system

In-app help pages cover “how to spend” and day-to-day accounts ops (vendor vs advance vs reimbursement, and when Get Advances will list an advance — it must be approved **and paid**).

---

## Release notes (recent)

### Spend and approvals

- Dedicated **Approval & Advance Limits** page (by designation), moved out of the general accounting settings dump.
- **My Work** and **My Expenses** cleaned up: shortcut cards with live counts; sidebars slimmed so everything important lives on the workspace.
- Advance Portal and Budget Health as polished web pages (build the frontend once after install — see below).
- Employees restricted to their own advances; leftover-advance report fixed.
- Approve / Reject (+ submit) on leave applications for approvers.
- Optional “already paid outside the system” action on vendor invoices for Accounts.
- Optional monthly reimbursement cap in accounting settings.
- Safer advance payments (blocks using a customer Debtors account for employee advances).
- Company expense-claim payable account auto-repaired if it was pointed at cash instead of a proper payable account.

### Attendance and work logs

- Manager-only remarks on daily work logs.
- Configurable work-log summary email (recipients, sender, daily / weekly / monthly).
- People who manage others use the existing Leave Approver path from **Reports To** — no extra custom manager role to maintain.

### Fixes and housekeeping

- Clearer messages when an advance can’t be linked to a claim yet (not paid / not submitted).
- Budget Health no longer fails for Accounts users missing project read access.
- Duplicate “available advances” hints on expense claims removed.

---

## Getting started (operators)

1. Set each employee’s **Reports To** and **Designation** — that drives leave approval and spend approval limits.
2. Open **Approval & Advance Limits** and confirm the amounts match your policy (or Reset to Defaults).
3. Set **Daily Work Log Settings** if you want the summary email.
4. Point staff to **My Work** and **My Expenses** from the desk home.

After install or upgrade, run a migrate so workspaces and settings seed correctly. For Advance Portal and Budget Health, build the frontend once:

```bash
cd apps/volunteering/frontend
yarn install && yarn build
```

Then clear cache / reload the site.

---

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app volunteering
```

---

## Contributing

This app uses [pre-commit](https://pre-commit.com/#installation) for formatting and linting:

```bash
cd apps/volunteering
pre-commit install
```

Tools: ruff, eslint, prettier, pyupgrade.

---

## License

MIT
