# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Seed Frappe Wiki (v3 Wiki Document) help spaces for Accounts + HR.

View pages at /{route} (e.g. /help/hr/home). Edit in Desk: Wiki Document.
Requires the `wiki` app installed on the site.
"""

import frappe
from frappe.utils import cint

from volunteering.volunteering.hr_wiki_content import (
	HR_ATTENDANCE,
	HR_DAILY_WORK_LOG,
	HR_HOME,
	HR_LEAVE,
	HR_MANAGER,
	HR_SETTINGS,
	HR_WFH,
)

SPACE_ROUTE = "help"
SPACE_NAME = "Sevamrita Wiki"

HOW_TO_SPEND = """# How to spend

Every expenditure should follow **one** path. Start from [My Expenses](/app/my-expenses) (advances & claims) or [My Work](/app/my-work) for attendance.

1. **Vendor payment (preferred)** — Purchase Order → Purchase Invoice → Payment Entry
2. **Employee Advance** — float before buying (local purchase, travel, events); settle with Expense Claim
3. **Reimbursement (exception)** — Expense Claim only when advance/vendor was not feasible

## Prefer vendor payment

Above the configured **Vendor Payment Threshold** (default ₹5,000), create a [Purchase Order](/app/purchase-order/new) instead of reimbursing yourself.

**Who creates what**

| Step | Who |
|------|-----|
| Purchase Order | Accounts / procurement (after need is clear) |
| Purchase Invoice | **Either** staff or Accounts — create from the approved PO and attach the supplier bill |
| Payment Entry | **Accounts only** |

### Goods needed now, tax invoice later

If the supplier must be paid before the tax invoice arrives:

1. Get an **approved, submitted** Purchase Order
2. Accounts creates **Payment Entry against that PO** (supplier advance — like Tally advance to creditor)
3. When the invoice arrives, staff or Accounts creates **Purchase Invoice from the PO** and allocates the advance

Credit purchases (pay after invoice) stay: PO → PI → Payment Entry vs PI.

If you must reimburse above the threshold, set **Vendor Payment Override Reason**.

## Employee Advance

- Only Employees may receive advances
- A new advance is blocked while another has residual **above** the replenish threshold (default **10%** of paid amount)
- If residual is **at or below 10%**, you may request a replenishment advance — but you must still claim or return the leftover (not auto-written-off)
- Settle via [Expense Claim](/app/expense-claim/new) linked to the Advance; return unused cash
- Accounts can chase leftovers on [Advances with Residual](/app/query-report/Employee%20Advances%20with%20Residual)

Open: [New Employee Advance](/app/employee-advance/new)

## Reimbursement

Use [Expense Claim](/app/expense-claim/new) for genuine exceptions (you already paid from pocket). Attach receipts before submit.

## Approvals

Approvals follow your **Reports To** chain and **Designation** limits.

- If your designation covers the amount: **Approve** (primary) or **Reject**
- If the amount is above your limit: **Reject** or **Escalate** (not Approve)
- Self-approval is not allowed

## Accounts

Accounts **does not** approve day-to-day spends. After approval they create [Payment Entry](/app/payment-entry) (like a Tally Payment voucher).

See also: [Accounts: Tally → ERPNext](/help/accounts/tally-to-erpnext) · [HR Home](/help/hr/home)
"""

TALLY_GUIDE = """# Accounts: Tally → ERPNext

This guide is for Accounts users comfortable with **Tally**. ERPNext keeps standard voucher names (Payment Entry, Journal Entry) so auditors and CAs recognise them. Use this map instead of renaming screens.

> If you still post in Tally in parallel, **do not double-post** the same payment. Treat ERPNext as the books of record unless leadership says otherwise.

## Mindset

| Tally | ERPNext |
|-------|---------|
| Enter voucher → books update | Staff **request** → manager **approves** → Accounts **pays** (Payment Entry) |
| Alter / Delete | **Cancel** / **Amend** (audit trail preserved) |
| Day Book | [General Ledger](/app/query-report/General%20Ledger) + list of vouchers |

Accounts role here: **weekly/monthly audit + Payment Entry**. Not live spend approval.

Staff hubs: [My Expenses](/app/my-expenses) for claims/advances/PI; Payment Entry stays with Accounts.

## Three spend paths

| Path | Flow | Tally analogue |
|------|------|----------------|
| Credit vendor | PO → PI → PE vs PI | Purchase + Payment |
| Pay before invoice | Approved PO → **PE vs PO** (supplier advance) → later PI clears advance | Advance to creditor vs order |
| Staff float / pocket | Advance or Expense Claim → PE vs employee | Payment to staff / imprest |

Every Purchase Invoice line must still link an **approved, submitted** PO. Staff or Accounts may create the PI; only Accounts pays.

## Voucher map

| Tally | ERPNext | When |
|-------|---------|------|
| Payment voucher | [Payment Entry](/app/payment-entry) (Pay) | Pay supplier (vs PI or approved PO) / employee after approval |
| Receipt voucher | Payment Entry (Receive) | Donations (Cashfree) / receipts |
| Journal | [Journal Entry](/app/journal-entry) | Settlements, clearing, adjustments |
| Purchase | [Purchase Invoice](/app/purchase-invoice) | Vendor bill (must link approved PO) |
| — (indent) | [Purchase Order](/app/purchase-order) | Commitment before invoice |
| — | [Expense Claim](/app/expense-claim) | Staff reimbursement (exception) |
| — | [Employee Advance](/app/employee-advance) | Staff float; settle later; replenish allowed if residual ≤10% |

## Master map

| Tally | ERPNext |
|-------|---------|
| Ledger / Group | [Chart of Accounts](/app/chart-of-accounts) |
| Sundry Creditor | [Supplier](/app/supplier) |
| Sundry Debtor | [Customer](/app/customer) |
| Cost Centre | [Cost Center](/app/cost-center) |
| Job / cost category | [Project](/app/project) (Campaign / Event / Admin) |
| Cash / Bank ledger | Account + [Mode of Payment](/app/mode-of-payment) |

## Day-to-day ops

1. [My Expenses](/app/my-expenses) — Vendor Invoices to Pay, Claims to Reimburse
2. [Employee Advances with Residual](/app/query-report/Employee%20Advances%20with%20Residual)
3. [Bank Reconciliation](/app/bank-reconciliation-tool)
4. [Budget Health](/app/project-budget-health)
5. [General Ledger](/app/query-report/General%20Ledger)

## Cashfree Clearing

Inbound donations land in **Cashfree Clearing**. When settlement hits your real bank, post a Journal Entry: Debit Bank / Credit Clearing (fees per CA advice).

## What Accounts does not do

No live spend approval — operations approve; Accounts pays and audits.

## Related

- [How to spend](/help/accounts/how-to-spend)
- [HR Home](/help/hr/home)
"""

# (group_title, slug, [(page_title, page_slug, content_getter)])
HELP_TREE = (
	(
		"HR",
		"hr",
		(
			("HR & Attendance", "home", lambda: HR_HOME),
			("Daily Work Log", "daily-work-log", lambda: HR_DAILY_WORK_LOG),
			("Attendance", "attendance", lambda: HR_ATTENDANCE),
			("Work From Home", "work-from-home", lambda: HR_WFH),
			("Leave Application", "leave", lambda: HR_LEAVE),
			("Manager Guide", "manager-guide", lambda: HR_MANAGER),
			("HR Settings & Ops", "settings", lambda: HR_SETTINGS),
		),
	),
	(
		"Accounts",
		"accounts",
		(
			("How to Spend", "how-to-spend", lambda: HOW_TO_SPEND),
			("Tally → ERPNext", "tally-to-erpnext", lambda: TALLY_GUIDE),
		),
	),
)


def ensure_help_wikis():
	"""Seed Sevamrita Wiki wiki space + pages. No-op if wiki app / Wiki Document missing."""
	if not frappe.db.exists("DocType", "Wiki Document"):
		frappe.log_error(
			title="Wiki seed skipped",
			message="Wiki Document doctype missing. Install and migrate the wiki app on this site.",
		)
		return

	_remove_legacy_org_help_page()
	space = _ensure_wiki_space()
	if not space or not space.root_group:
		return

	for sort_order, (group_title, group_slug, pages) in enumerate(HELP_TREE):
		group = _ensure_group(space, group_title, group_slug, sort_order)
		for page_order, (page_title, page_slug, content_fn) in enumerate(pages):
			_ensure_page(
				space=space,
				parent=group.name,
				title=page_title,
				slug=page_slug,
				route=f"{SPACE_ROUTE}/{group_slug}/{page_slug}",
				content=_rewrite_legacy_links(content_fn()),
				sort_order=page_order,
			)


# Keep old names as aliases for after_migrate callers
ensure_accounting_wikis = ensure_help_wikis
ensure_hr_wikis = ensure_help_wikis


def _ensure_wiki_space():
	existing = frappe.db.get_value("Wiki Space", {"route": SPACE_ROUTE}, "name")
	if existing:
		space = frappe.get_doc("Wiki Space", existing)
		changed = False
		if not cint(space.get("is_published")):
			space.is_published = 1
			changed = True
		if _ensure_space_read_roles(space):
			changed = True
		if changed:
			space.save(ignore_permissions=True)
		return space

	space = frappe.get_doc(
		{
			"doctype": "Wiki Space",
			"space_name": SPACE_NAME,
			"route": SPACE_ROUTE,
			"is_published": 1,
			"allow_contributions": 1,
		}
	)
	_ensure_space_read_roles(space)
	space.insert(ignore_permissions=True)
	return space


def _ensure_space_read_roles(space) -> bool:
	"""
	Wiki v3: empty role table = logged-in users only; Guest gets 404 on /help/...

	Grant Guest Read so Desk hyperlinks work in a new tab, plus common staff roles.
	"""
	if not frappe.db.exists("DocType", "Wiki Space Role"):
		return False

	wanted = [
		("Guest", "Read"),
		("All", "Read"),
		("Employee", "Read"),
		("System Manager", "Write"),
		("Wiki Manager", "Write"),
		("Wiki Approver", "Write"),
		("HR Manager", "Write"),
		("Accounts Manager", "Write"),
	]
	existing = {(row.role, row.permission_level) for row in (space.get("roles") or [])}
	changed = False
	for role, level in wanted:
		if not frappe.db.exists("Role", role):
			continue
		if (role, level) in existing:
			continue
		# Prefer Write over duplicate Read for same role
		if any(r == role and l == "Write" for r, l in existing) and level == "Read":
			continue
		space.append("roles", {"role": role, "permission_level": level})
		existing.add((role, level))
		changed = True
	return changed


def _ensure_group(space, title, slug, sort_order):
	route = f"{SPACE_ROUTE}/{slug}"
	name = frappe.db.get_value(
		"Wiki Document",
		{"route": route, "is_group": 1, "wiki_space": space.name},
		"name",
	)
	if name:
		return frappe.get_doc("Wiki Document", name)

	# Fallback match by title under root
	name = frappe.db.get_value(
		"Wiki Document",
		{
			"parent_wiki_document": space.root_group,
			"is_group": 1,
			"title": title,
		},
		"name",
	)
	if name:
		doc = frappe.get_doc("Wiki Document", name)
		if doc.route != route:
			doc.route = route
			doc.slug = slug
			doc.save(ignore_permissions=True)
		return doc

	doc = frappe.get_doc(
		{
			"doctype": "Wiki Document",
			"title": title,
			"slug": slug,
			"route": route,
			"is_group": 1,
			"is_published": 1,
			"parent_wiki_document": space.root_group,
			"wiki_space": space.name,
			"sort_order": sort_order,
			"content": "",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _ensure_page(space, parent, title, slug, route, content, sort_order):
	name = frappe.db.get_value(
		"Wiki Document",
		{"route": route, "is_group": 0},
		"name",
	)
	if name:
		doc = frappe.get_doc("Wiki Document", name)
		doc.title = title
		doc.content = content
		doc.is_published = 1
		doc.parent_wiki_document = parent
		doc.wiki_space = space.name
		doc.slug = slug
		doc.sort_order = sort_order
		doc.save(ignore_permissions=True)
		return doc

	doc = frappe.get_doc(
		{
			"doctype": "Wiki Document",
			"title": title,
			"slug": slug,
			"route": route,
			"content": content,
			"is_group": 0,
			"is_published": 1,
			"parent_wiki_document": parent,
			"wiki_space": space.name,
			"sort_order": sort_order,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _rewrite_legacy_links(markdown: str) -> str:
	"""Point old /app/wiki and /app/org-help links at stable /help/... routes."""
	replacements = {
		"/app/wiki/HR-Home": "/help/hr/home",
		"/app/wiki/HR-Daily-Work-Log": "/help/hr/daily-work-log",
		"/app/wiki/HR-Attendance": "/help/hr/attendance",
		"/app/wiki/HR-Work-From-Home": "/help/hr/work-from-home",
		"/app/wiki/HR-Leave": "/help/hr/leave",
		"/app/wiki/HR-Manager-Guide": "/help/hr/manager-guide",
		"/app/wiki/HR-Settings": "/help/hr/settings",
		"/app/wiki/How-to-Spend": "/help/accounts/how-to-spend",
		"/app/wiki/Accounts-Tally-to-ERPNext": "/help/accounts/tally-to-erpnext",
		"/app/org-help/hr-home": "/help/hr/home",
		"/app/org-help/hr-daily-work-log": "/help/hr/daily-work-log",
		"/app/org-help/hr-attendance": "/help/hr/attendance",
		"/app/org-help/hr-work-from-home": "/help/hr/work-from-home",
		"/app/org-help/hr-leave": "/help/hr/leave",
		"/app/org-help/hr-manager-guide": "/help/hr/manager-guide",
		"/app/org-help/hr-settings": "/help/hr/settings",
		"/app/org-help/how-to-spend": "/help/accounts/how-to-spend",
		"/app/org-help/accounts-tally": "/help/accounts/tally-to-erpnext",
		"/app/pending-vendor-pay": "/app/my-expenses",
		"/app/pending-reimburse": "/app/my-expenses",
		"/app/pending-my-approval": "/app/my-expenses",
	}
	out = markdown
	for old, new in replacements.items():
		out = out.replace(old, new)
	return out


def _remove_legacy_org_help_page():
	"""Drop the temporary Desk Help Centre page if it was synced."""
	if frappe.db.exists("Page", "org-help"):
		try:
			frappe.delete_doc("Page", "org-help", force=True, ignore_permissions=True)
		except Exception:
			frappe.log_error(title="Could not delete legacy Page org-help")
