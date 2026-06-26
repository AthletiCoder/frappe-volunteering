import frappe
from frappe import _
from frappe.utils import formatdate, now_datetime

from volunteering.volunteering.accounting_dashboard.pending_approvals import (
	_can_user_act,
	_enrich_action,
	_fetch_pending_rows,
)


PENDING_SIDEBAR_SECTION = "Pending Approvals"
BUDGET_SIDEBAR_SECTION = "Budgets"

ACCOUNTING_PAGE_SPECS = (
	{
		"name": "pending-my-approval",
		"title": "My Approval",
		"sidebar_label": "My Approval",
		"icon": "inbox",
		"roles": [
			"Employee",
			"Accounts User",
			"Accounts Manager",
			"NGO Department Head",
			"NGO Board Member",
			"NGO Board Chairperson",
		],
	},
	{
		"name": "pending-reimburse",
		"title": "Reimbursements",
		"sidebar_label": "Reimbursements",
		"icon": "wallet",
		"roles": ["Accounts User", "Accounts Manager"],
	},
	{
		"name": "pending-vendor-pay",
		"title": "Vendor Payments",
		"sidebar_label": "Vendor Payments",
		"icon": "credit-card",
		"roles": ["Accounts User", "Accounts Manager"],
	},
)

BUDGET_PAGE_SPECS = (
	{
		"name": "project-budget-health",
		"title": "Budget Health",
		"sidebar_label": "Budget Health",
		"icon": "pie-chart",
		"roles": ["Accounts User", "Accounts Manager", "NGO Coordinator"],
	},
)


def ensure_accounting_pages():
	for spec in ACCOUNTING_PAGE_SPECS + BUDGET_PAGE_SPECS:
		_ensure_page(spec)
	ensure_accounting_sidebar_links()


def _ensure_page(spec):
	if frappe.db.exists("Page", spec["name"]):
		frappe.db.set_value("Page", spec["name"], "title", spec["title"])
		return

	page = frappe.get_doc(
		{
			"doctype": "Page",
			"module": "Volunteering",
			"page_name": spec["name"],
			"title": spec["title"],
			"standard": "Yes",
			"roles": [{"role": role} for role in spec["roles"]],
		}
	)
	page.insert(ignore_permissions=True)


def ensure_accounting_sidebar_links():
	"""Add accounting dashboard links under Pending Approvals in Volunteering sidebar."""
	from volunteering.volunteering.workspace_setup import ensure_volunteering_workspace

	if not frappe.db.exists("Workspace Sidebar", "Volunteering"):
		return

	ensure_volunteering_workspace()

	sidebar = frappe.get_doc("Workspace Sidebar", "Volunteering")
	pending_page_names = {spec["name"] for spec in ACCOUNTING_PAGE_SPECS}
	budget_page_names = {spec["name"] for spec in BUDGET_PAGE_SPECS}
	all_page_names = pending_page_names | budget_page_names

	sidebar.items = [
		item
		for item in sidebar.items
		if _is_valid_sidebar_link(item)
		and not (item.link_type == "Page" and item.link_to in all_page_names)
		and item.label
		not in (PENDING_SIDEBAR_SECTION, BUDGET_SIDEBAR_SECTION)
	]

	for item in _pending_sidebar_block():
		sidebar.append("items", item)
	for item in _budget_sidebar_block():
		sidebar.append("items", item)

	sidebar.save(ignore_permissions=True)


def _pending_sidebar_block():
	items = [_section_item(PENDING_SIDEBAR_SECTION, "folder")]
	for spec in ACCOUNTING_PAGE_SPECS:
		if frappe.db.exists("Page", spec["name"]):
			items.append(_page_item(spec))
	return items


def _budget_sidebar_block():
	items = [_section_item(BUDGET_SIDEBAR_SECTION, "pie-chart")]
	for spec in BUDGET_PAGE_SPECS:
		if frappe.db.exists("Page", spec["name"]):
			items.append(_page_item(spec))
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


def _is_valid_sidebar_link(item):
	if item.type in ("Section Break", "Sidebar Item Group", "Spacer"):
		return True
	if item.link_type == "URL":
		return bool(item.link_to)
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
		+ _("Open your dashboard: {0}").format(
			frappe.utils.get_url("/app/pending-my-approval")
		)
	)

	frappe.sendmail(
		recipients=[email],
		subject=_("Pending approvals reminder — {0}").format(formatdate(now_datetime())),
		message=message,
		now=True,
	)
