# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Accounting SPA links + My Expenses wiring (Desk Page UIs retired)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import formatdate, now_datetime

from volunteering.volunteering.accounting_dashboard.pending_approvals import (
	_can_user_act,
	_enrich_action,
	_fetch_pending_rows,
)

PENDING_SIDEBAR_SECTION = "Approvals"
ACCOUNTS_OPS_SIDEBAR_SECTION = "Accounts Ops"
BUDGET_SIDEBAR_SECTION = "Budgets"

# Retired desk pages — delete if still on site
RETIRED_PENDING_PAGES = (
	"pending-my-approval",
	"pending-reimburse",
	"pending-vendor-pay",
	"project-budget-health",
	"advance-portal",
)

# No longer create accounting Desk Pages (SPA owns these UIs)
ACCOUNTING_PAGE_SPECS = ()
BUDGET_PAGE_SPECS = ()

SPA_ADVANCE_PORTAL = {
	"label": "Advance Portal",
	"url": "/volunteering/advances",
	"icon": "money-coins-1",
}
SPA_BUDGET_HEALTH = {
	"label": "Budget Health",
	"url": "/volunteering/budget-health",
	"icon": "pie-chart",
}


def ensure_accounting_pages():
	_retire_pending_pages()
	from volunteering.volunteering.accounts_workspace_setup import ensure_accounts_workspace

	ensure_accounts_workspace()


def _retire_pending_pages():
	for name in RETIRED_PENDING_PAGES:
		if frappe.db.exists("Page", name):
			frappe.delete_doc("Page", name, force=True, ignore_permissions=True)


def _ensure_page(spec):
	"""Kept for tests / callers; Desk pages are no longer provisioned."""
	return


def ensure_accounting_sidebar_links():
	from volunteering.volunteering.accounts_workspace_setup import ensure_accounts_workspace

	ensure_accounts_workspace()


def _approvals_sidebar_block():
	"""DocType links for filtered approval queues (filters live on workspace shortcuts)."""
	items = [_section_item(PENDING_SIDEBAR_SECTION, "inbox")]
	for label, doctype, icon in (
		("Expense Claims Pending Me", "Expense Claim", "expense"),
		("Advances Pending Me", "Employee Advance", "money-coins-1"),
		("Purchase Orders Pending Me", "Purchase Order", "buying"),
	):
		if frappe.db.exists("DocType", doctype):
			items.append(_doctype_sidebar_item(label, doctype, icon))
	return items


def _accounts_ops_sidebar_block():
	items = [_section_item(ACCOUNTS_OPS_SIDEBAR_SECTION, "wallet")]
	for label, doctype, icon in (
		("Claims to Reimburse", "Expense Claim", "expense"),
		("Vendor Invoices to Pay", "Purchase Invoice", "file"),
	):
		if frappe.db.exists("DocType", doctype):
			items.append(_doctype_sidebar_item(label, doctype, icon))
	return items


def _pending_sidebar_block():
	"""Back-compat name used by accounts_workspace_setup."""
	return _approvals_sidebar_block()


def _budget_sidebar_block():
	items = [_section_item(BUDGET_SIDEBAR_SECTION, "pie-chart")]
	items.append(_url_sidebar_item(SPA_BUDGET_HEALTH))
	return items


def _section_item(label, icon):
	return {
		"type": "Section Break",
		"label": label,
		"icon": icon,
		"collapsible": 1,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 1,
		"child": 0,
	}


def _page_item(spec):
	return {
		"type": "Link",
		"label": spec["sidebar_label"],
		"link_to": spec["name"],
		"link_type": "Page",
		"icon": spec["icon"],
		"child": 1,
		"collapsible": 0,
		"indent": 1,
		"keep_closed": 0,
		"show_arrow": 0,
	}


def _url_sidebar_item(spec):
	return {
		"type": "Link",
		"label": spec["label"],
		"link_type": "URL",
		"url": spec["url"],
		"icon": spec.get("icon") or "external-link",
		"child": 1,
		"collapsible": 0,
		"indent": 1,
		"keep_closed": 0,
		"show_arrow": 0,
	}


def _doctype_sidebar_item(label, doctype, icon):
	return {
		"type": "Link",
		"label": label,
		"link_to": doctype,
		"link_type": "DocType",
		"icon": icon,
		"child": 1,
		"collapsible": 0,
		"indent": 1,
		"keep_closed": 0,
		"show_arrow": 0,
	}


def _is_valid_sidebar_link(item):
	if item.type in ("Section Break", "Sidebar Item Group", "Spacer"):
		return True
	if item.link_type == "URL":
		return bool(item.get("url") or item.get("link_to"))
	if not item.link_to:
		return False
	return frappe.db.exists(item.link_type, item.link_to)


def send_weekly_pending_approval_reminder():
	"""Email each user who has actionable pending workflow approvals."""
	users = _users_with_pending_approvals()
	for user, rows in users.items():
		if not rows:
			continue
		_send_reminder_email(user, rows)


def _users_with_pending_approvals():
	grouped = {}

	for user in frappe.get_all("User", filters={"enabled": 1}, pluck="name"):
		if user in ("Guest", "Administrator"):
			continue
		roles = set(frappe.get_roles(user))
		if not roles:
			continue
		actions = _fetch_pending_rows()
		pending = [
			_enrich_action(row, user, roles)
			for row in actions
			if _can_user_act(row, user, roles)
		]
		if pending:
			grouped[user] = pending

	return grouped


def _send_reminder_email(user, rows):
	email = frappe.db.get_value("User", user, "email")
	if not email:
		return

	lines = []
	for row in rows[:20]:
		lines.append(
			"- {doctype} {name}: {state} ({amount}) — pending {age}".format(
				doctype=row.reference_doctype,
				name=row.reference_name,
				state=row.workflow_state,
				amount=frappe.format_value(row.get("amount"), "Currency"),
				age=row.get("age_label") or "",
			)
		)

	message = _("The following documents are awaiting your approval:") + "<br><br>" + "<br>".join(
		lines
	)
	if len(rows) > 20:
		message += "<br><br>" + _("…and {0} more.").format(len(rows) - 20)

	message += (
		"<br><br>"
		+ _("Open Home: {0}").format(frappe.utils.get_url("/volunteering/home"))
	)

	frappe.sendmail(
		recipients=[email],
		subject=_("Pending approvals reminder — {0}").format(formatdate(now_datetime())),
		message=message,
		now=True,
	)
